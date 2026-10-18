"""The consultant: listens, keeps a running brief, decides when to speak, answers,
writes the post-meeting memo, and turns what it learned into a reusable skill."""
import asyncio
import httpx
import json
import logging
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set

from .config import Settings
from .llm import LLM
from .meeting import Meeting
from .recall import RecallClient, chat_limit, chunk_message
from .agents import Researcher, ResearchJob
from .skills import SkillLibrary, load_skill_block, select_skills, tokens
from .tts import TTS

log = logging.getLogger("consultant")

STYLE = """How you behave:
- You are a senior consultant and domain expert sitting in on this meeting. Be direct and specific.
- Stress-test before you agree. Lead with the weakest point, missing evidence or untested assumption. No flattery, no filler.
- Separate what was said in the meeting from your own view, and say which is which.
- Never claim a decision was made unless someone clearly agreed to it.
- In the meeting chat, keep replies under 120 words unless someone asks for detail. Ask at most one question at a time.
- If you use facts from the web, name the source briefly.
- The transcript is machine-generated: names and words can be wrong. Don't build an argument on one odd word."""

ANALYSIS_SCHEMA = """Reply with only one JSON object:
{
 "profile": {"domain": "the subject area in a few words",
             "expert_persona": "the kind of expert who would add most here, e.g. 'B2B fintech product strategist who knows UK payments regulation'",
             "keywords": ["5-10 search keywords"]},
 "topic_shift": false,
 "brief": {
   "summary": "2-3 sentences on where the discussion is now",
   "goals": [], "problem": "", "target_users": [], "options_discussed": [],
   "decisions": ["only things clearly agreed"], "mvp_in": [], "mvp_out": [],
   "open_questions": [], "risks_assumptions": ["untested assumptions the plan depends on"],
   "action_items": [{"owner": "", "task": "", "due": ""}], "parking_lot": []
 },
 "hindsight_questions": ["3-6 questions a sharp expert would ask after reading this whole transcript: gaps, contradictions, unvalidated claims"],
 "wrapping_up": false,
 "research_requests": ["at most 2 factual questions the room raised that you should research now with web agents (competitor pricing, regulation, market size, technical feasibility). Empty if none or already researched"],
 "intervention": {
   "value": 0,
   "type": "question|risk|fact|suggestion|none",
   "message": "what you'd post in the meeting chat, under 80 words, specific to what was just said",
   "spoken": "the same point in under 25 words, to say aloud",
   "why": "one line"
 }
}
Rules: topic_shift = has the core subject changed since your previous profile. wrapping_up = they are clearly closing
the meeting or summarising next steps. intervention.value: 10 = they're about to make a costly mistake or are missing
something critical; 7 = genuinely useful; under 5 = noise. Be stingy: every interruption has a cost, and never repeat
a point you've already made. Keep list items under 20 words. Use empty lists where nothing was said."""

REPORT_SECTIONS = """Write in Markdown with these sections, in order:
## Bottom line
3-5 sentences: where they landed and your honest assessment, leading with the biggest weakness.
## Decisions made
Only things clearly agreed.
## In and out of scope
## Open questions
## Risks and untested assumptions
For each: why it matters and the cheapest way to test it this week.
## Questions I'd ask having read the transcript
## My recommendations
As the domain expert: reasoned and specific. Say where you disagree with the room.
## Next steps
Owner, action, by when. Use '?' where nobody took ownership.
Don't invent facts. Mark anything you inferred as inferred."""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "meeting").lower()).strip("-")[:40] or "meeting"


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


class Consultant:
    def __init__(self, settings: Settings, recall: RecallClient, llm: LLM, skills: SkillLibrary,
                 tts: Optional[TTS] = None, researcher: Optional[Researcher] = None, clock=time.time):
        self.s = settings
        self.researcher = researcher
        self.recall = recall
        self.llm = llm
        self.skills = skills
        self.tts = tts or TTS(settings)
        self.clock = clock
        self.meetings: Dict[str, Meeting] = {m.id: m for m in Meeting.load_all(settings.data_dir)}
        self._tasks: Set[asyncio.Task] = set()
        self._analysing: Set[str] = set()
        self._addressing: Set[str] = set()
        self._skill_text: Dict[str, str] = {}
        self._sent: Dict[str, Deque[str]] = {}
        self._last_save: Dict[str, float] = {}
        self._dirty: Set[str] = set()
        words = [w for w in settings.wake_words if w] or [settings.short_name]
        self._wake = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)

    # ------------------------------------------------------------------ plumbing
    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self) -> None:
        """Wait for background work (used by tests and on shutdown)."""
        while self._tasks or (self.researcher and self.researcher._tasks):
            if self._tasks:
                await asyncio.gather(*list(self._tasks), return_exceptions=True)
            if self.researcher:
                await self.researcher.drain()

    def save(self, m: Meeting) -> None:
        m.save(self.s.data_dir)
        self._last_save[m.id] = self.clock()
        self._dirty.discard(m.id)

    def _maybe_save(self, m: Meeting) -> None:
        if self.clock() - self._last_save.get(m.id, 0) >= 5:
            self.save(m)
        else:
            self._dirty.add(m.id)

    # ------------------------------------------------------------------ joining
    async def join(self, meeting_url: str, topic: str = "", context: str = "", mode: Optional[str] = None) -> Meeting:
        name = self.s.short_name
        join_message = (
            f"Hi, I'm {name}, an AI consultant. I'm transcribing this meeting so I can take notes and offer input. "
            f"Say \"{name}\" or type @{name} to ask me something. Commands: /brief /questions /research <question> "
            f"/quiet /help. Ask the host to remove me if you'd rather I wasn't here."
        )
        bot = await self.recall.create_bot(meeting_url, self.s.bot_name, self.s.realtime_webhook_url,
                                           join_message, metadata={"topic": (topic or "")[:200]})
        m = Meeting(id=bot["id"], meeting_url=meeting_url, topic=topic, context=context,
                    mode=(mode or self.s.default_mode))
        if m.mode == "voice" and not self.tts.available:
            m.mode = "chat"
            m.error = "Voice was requested but no text-to-speech provider is configured, so the bot uses chat."
        self.meetings[m.id] = m
        self.save(m)
        return m

    # ------------------------------------------------------------------ inbound events
    async def on_realtime(self, payload: Dict[str, Any]) -> None:
        event = payload.get("event", "")
        data = payload.get("data") or {}
        m = self.meetings.get((data.get("bot") or {}).get("id", ""))
        if not m or m.status in ("finishing", "done"):
            return
        if m.status == "joining":
            m.status = "live"
        inner = data.get("data") or {}
        if event == "transcript.data":
            await self._on_transcript(m, inner)
        elif event == "participant_events.chat_message":
            await self._on_chat(m, inner)
        elif event in ("participant_events.join", "participant_events.leave"):
            p = inner.get("participant") or {}
            if p.get("name"):
                m.participants[str(p.get("id"))] = p["name"]
            self._maybe_save(m)

    async def on_status(self, payload: Dict[str, Any]) -> None:
        event = payload.get("event", "")
        data = payload.get("data") or {}
        m = self.meetings.get((data.get("bot") or {}).get("id", ""))
        if not m:
            return
        if event in ("bot.in_call_recording", "bot.in_call_not_recording") and m.status == "joining":
            m.status = "live"
            self.save(m)
        elif event in ("bot.call_ended", "bot.done"):
            self._spawn(self.finish(m))
        elif event == "bot.fatal":
            m.error = f"Recall reported a fatal error: {(data.get('data') or {}).get('sub_code')}"
            if m.utterances:
                self._spawn(self.finish(m))
            else:
                m.status = "failed"
                self.save(m)

    async def _on_transcript(self, m: Meeting, inner: Dict[str, Any]) -> None:
        words = inner.get("words") or []
        text = " ".join((w.get("text") or "").strip() for w in words).strip()
        if not text:
            return
        p = inner.get("participant") or {}
        speaker = p.get("name") or f"Speaker {p.get('id', '?')}"
        if p.get("name"):
            m.participants[str(p.get("id"))] = p["name"]
        start = (words[0].get("start_timestamp") or {}).get("relative") or 0.0
        now = self.clock()
        m.utterances.append({"speaker": speaker, "text": text, "t": float(start), "wall": now})
        m.last_utterance_wall = now
        self._maybe_save(m)
        if self._wake.search(text) and m.id not in self._addressing:
            self._addressing.add(m.id)
            self._spawn(self._answer_after_pause(m, speaker, len(m.utterances) - 1))

    async def _answer_after_pause(self, m: Meeting, speaker: str, start_idx: int) -> None:
        """Someone said the bot's name: wait until they stop talking, then answer the whole question."""
        started = self.clock()
        step = max(min(0.25, self.s.address_pause_s / 2), 0.01)
        try:
            while True:
                await asyncio.sleep(step)
                now = self.clock()
                if now - m.last_utterance_wall >= self.s.address_pause_s or now - started >= self.s.address_max_wait_s:
                    break
            question = " ".join(u["text"] for u in m.utterances[start_idx:] if u["speaker"] == speaker)
            await self.respond(m, question, speaker, via="speech")
        finally:
            self._addressing.discard(m.id)

    async def _on_chat(self, m: Meeting, inner: Dict[str, Any]) -> None:
        p = inner.get("participant") or {}
        text = ((inner.get("data") or {}).get("text") or "").strip()
        name = p.get("name") or "Someone"
        if not text or name == self.s.bot_name or text in self._sent.get(m.id, ()):
            return
        m.chat.append({"speaker": name, "text": text, "wall": self.clock(), "from_bot": False})
        self._maybe_save(m)
        if text.startswith("/"):
            await self.command(m, text, name)
        elif self._wake.search(text) or f"@{self.s.short_name.lower()}" in text.lower():
            self._spawn(self.respond(m, text, name, via="chat"))

    # ------------------------------------------------------------------ chat commands
    async def command(self, m: Meeting, text: str, who: str) -> None:
        cmd, _, arg = text[1:].strip().partition(" ")
        cmd, arg = cmd.lower(), arg.strip()
        if cmd == "brief":
            await self.say(m, self.format_brief(m) or "No brief yet. I need a couple of minutes of discussion first.")
        elif cmd == "questions":
            qs = m.hindsight_questions or (m.brief or {}).get("open_questions") or []
            await self.say(m, "Questions I'd want answered:\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(qs[:6], 1))
                           if qs else "Nothing yet. Give me a few minutes of discussion.")
        elif cmd == "research" and arg:
            if self.researcher:
                self.start_research(m, arg, requested_by=who)
                await self.say(m, f"On it. I've sent research agents after: \"{arg}\". I'll post the findings here "
                                  "and put the full write-up in the notes.")
            else:
                self._spawn(self.respond(m, arg, who, via="chat", force_research=True))
        elif cmd == "agents":
            jobs = [self.researcher.jobs[i] for i in m.research_ids if self.researcher and i in self.researcher.jobs]
            await self.say(m, "Research agents: " + "; ".join(f"{j.question[:60]} ({j.status})" for j in jobs)
                           if jobs else "No research running in this meeting.")
        elif cmd == "quiet":
            m.quiet = True
            await self.say(m, "OK. I'll only speak when someone asks me directly. Type /resume to undo.")
        elif cmd in ("resume", "unquiet"):
            m.quiet = False
            await self.say(m, "OK. I'll speak up again when I have something worth raising.")
        elif cmd == "voice":
            if arg.lower() == "on" and not self.tts.available:
                await self.say(m, "Voice isn't set up on my server, so I'll stay in chat.")
            else:
                m.mode = "voice" if arg.lower() == "on" else "chat"
                await self.say(m, f"Voice is {'on' if m.mode == 'voice' else 'off'}.")
        elif cmd == "skills":
            await self.say(m, "Playbooks I'm using: " + ", ".join(s["name"] for s in m.skills) if m.skills
                           else "I haven't picked any playbooks yet.")
        elif cmd == "leave":
            await self.say(m, "Leaving now. I'll write up the meeting memo.")
            self._spawn(self.finish(m, leave=True))
        else:
            await self.say(m, f"Say \"{self.s.short_name}\" or type @{self.s.short_name} with a question. "
                              "Commands: /brief (running notes), /questions (gaps I'd probe), /research <question>, /agents, "
                              "/quiet, /resume, /voice on|off, /skills, /leave.")
        self._maybe_save(m)

    def format_brief(self, m: Meeting) -> str:
        b = m.brief or {}
        if not b:
            return ""
        parts = [b.get("summary", "")]
        for key, label in (("decisions", "Decided"), ("open_questions", "Open"), ("risks_assumptions", "Untested")):
            items = [str(x) for x in (b.get(key) or [])][:3]
            if items:
                parts.append(f"{label}: " + "; ".join(items))
        return "\n".join(p for p in parts if p)

    # ------------------------------------------------------------------ speaking
    async def say(self, m: Meeting, text: str, spoken: Optional[str] = None) -> None:
        sent = self._sent.setdefault(m.id, deque(maxlen=60))
        sent.extend(chunk_message(text, chat_limit(m.meeting_url)))
        try:
            await self.recall.send_chat(m.id, text, m.meeting_url)
        except Exception as e:  # noqa: BLE001 — a failed post must not kill the meeting loop
            log.warning("chat send failed for %s: %s", m.id, e)
        if spoken and m.mode == "voice" and self.tts.available:
            try:
                mp3 = await self.tts.synth(spoken)
                if mp3:
                    await self.recall.output_audio(m.id, mp3)
            except Exception as e:  # noqa: BLE001
                log.warning("voice output failed for %s: %s", m.id, e)
        m.chat.append({"speaker": self.s.short_name, "text": text, "wall": self.clock(), "from_bot": True})
        self._maybe_save(m)

    async def _spoken_version(self, text: str) -> str:
        try:
            return await self.llm.text(
                "spoken", self.s.fast_model,
                "Turn this into one or two sentences (under 30 words) to say out loud in a meeting. "
                f"The full answer is in the chat, so point there if needed.\n\n{text}", max_tokens=120)
        except Exception:  # noqa: BLE001
            return ""

    def _expert_system(self, m: Meeting) -> str:
        loaded = self._skill_text.get(m.id)
        if loaded is None:
            loaded = load_skill_block(m.skills)
            self._skill_text[m.id] = loaded
        persona = (m.profile or {}).get("expert_persona") or "a senior product and strategy consultant"
        text = f"You are {self.s.bot_name}, attending a live meeting as {persona}.\n\n{STYLE}"
        if loaded:
            text += ("\n\nPlaybooks loaded for this meeting. Apply them where they genuinely fit, "
                     f"without name-dropping them:\n\n{loaded}")
        return text

    def _context_block(self, m: Meeting) -> str:
        return (f"Meeting topic: {m.topic or '(not given)'}\n"
                f"Organiser's context: {m.context or '(none)'}\n\n"
                f"Your running brief:\n{json.dumps(m.brief) if m.brief else '(none yet)'}")

    # ------------------------------------------------------------------ answering
    async def respond(self, m: Meeting, question: str, asker: str, via: str, force_research: bool = False) -> None:
        history = "\n".join(f"{e['asker']}: {e['q']}\nYou: {e['a']}" for e in m.exchanges[-5:]) or "(none)"
        research = ("Research this with web search before answering." if force_research else
                    "Use web search only if the answer depends on current facts, prices, competitors or regulation.")
        prompt = (f"{self._context_block(m)}\n\nRecent transcript:\n{m.recent(40) or '(nothing yet)'}\n\n"
                  f"Your earlier exchanges in this meeting:\n{history}\n\n"
                  f"{asker} just asked you ({'out loud' if via == 'speech' else 'in the chat'}): \"{question}\"\n\n"
                  f"Answer as the expert in the room. {research} Reply with the chat message only.")
        try:
            answer = await self.llm.text("respond", self.s.live_model, prompt, cached_system=self._expert_system(m),
                                         max_tokens=1200, web_search=True)
        except Exception as e:  # noqa: BLE001
            log.exception("respond failed")
            answer = f"I couldn't answer that just now: my AI service returned an error ({type(e).__name__})."
        if not answer:
            return
        m.exchanges.append({"asker": asker, "q": question, "a": answer})
        m.interventions.append({"wall": self.clock(), "kind": "answer", "text": answer, "trigger": question})
        spoken = await self._spoken_version(answer) if m.mode == "voice" else None
        await self.say(m, answer, spoken)

    # ------------------------------------------------------------------ the periodic loop
    async def tick(self) -> None:
        now = self.clock()
        for m in list(self.meetings.values()):
            if m.id in self._dirty:
                self.save(m)
            if m.status != "live":
                continue
            if m.pending_voice:
                await self._try_pending_voice(m)
            new_chars = m.transcript_len() - m.last_analysis_len
            if (new_chars >= self.s.min_new_chars and now - m.last_analysis_wall >= self.s.analysis_interval_s
                    and m.id not in self._analysing):
                self._spawn(self.analyze(m))
            if m.utterances and now - m.last_utterance_wall >= self.s.inactivity_finish_s:
                self._spawn(self.finish(m, leave=True))

    async def analyze(self, m: Meeting) -> None:
        if m.id in self._analysing:
            return
        self._analysing.add(m.id)
        now = self.clock()
        try:
            snapshot_len = m.transcript_len()
            said = "\n".join(f"- {i['text'][:300]}" for i in m.interventions[-10:]) or "(nothing yet)"
            since = int(now - m.last_proactive_wall) if m.last_proactive_wall else "never"
            prompt = (f"You are listening to a live meeting. Update your notes and decide whether to speak.\n\n"
                      f"{self._context_block(m)}\n\n"
                      f"Minutes elapsed: {int((now - m.created_at) / 60)}\n"
                      f"Your current profile of the discussion: {json.dumps(m.profile) if m.profile else '(none yet)'}\n"
                      f"What you've already said (don't repeat it):\n{said}\n"
                      f"Seconds since you last spoke up unprompted: {since}\n\n"
                      f"Transcript so far:\n{m.transcript_text()}\n\n{ANALYSIS_SCHEMA}")
            result = await self.llm.json("analysis", self.s.live_model, prompt,
                                         cached_system=self._expert_system(m), max_tokens=3500)
            m.last_analysis_wall, m.last_analysis_len = now, snapshot_len
            profile = result.get("profile")
            topic_changed = False
            if isinstance(profile, dict) and profile.get("domain"):
                topic_changed = m.profile is None or bool(result.get("topic_shift"))
                m.profile = profile
            if isinstance(result.get("brief"), dict):
                m.brief = result["brief"]
            if isinstance(result.get("hindsight_questions"), list):
                m.hindsight_questions = [str(q) for q in result["hindsight_questions"]][:8]
            if m.profile and (not m.skills or topic_changed or now - m.last_skill_pick_wall >= self.s.skill_refresh_s):
                await self.pick_skills(m)
            if self.researcher and m.status == "live":
                for q in (result.get("research_requests") or [])[:2]:
                    q = str(q).strip()
                    done = [self.researcher.jobs[i].question for i in m.research_ids if i in self.researcher.jobs]
                    if (q and len(m.research_ids) < self.s.max_auto_research
                            and not any(_jaccard(q, d) > 0.5 for d in done)):
                        self.start_research(m, q, requested_by="auto")
            if m.status == "live":
                if result.get("wrapping_up") and not m.posted_hindsight and m.hindsight_questions:
                    await self._post_hindsight(m)
                else:
                    await self._consider(m, result.get("intervention") or {})
            self.save(m)
        except Exception:  # noqa: BLE001
            log.exception("analysis failed for %s", m.id)
            m.last_analysis_wall = now  # back off until the next interval
        finally:
            self._analysing.discard(m.id)

    async def _post_hindsight(self, m: Meeting) -> None:
        m.posted_hindsight = True
        text = ("Before you wrap up, these are the questions I'd ask after reading the transcript:\n"
                + "\n".join(f"{i}. {q}" for i, q in enumerate(m.hindsight_questions[:3], 1)))
        m.interventions.append({"wall": self.clock(), "kind": "hindsight", "text": text})
        spoken = "Before you wrap up, I've put three questions in the chat that I think still need answers."
        await self.say(m, text, spoken if m.mode == "voice" else None)

    async def _consider(self, m: Meeting, iv: Dict[str, Any]) -> None:
        try:
            value = float(iv.get("value") or 0)
        except (TypeError, ValueError):
            value = 0.0
        message = (iv.get("message") or "").strip()
        now = self.clock()
        if (not message or iv.get("type") == "none" or m.quiet or value < self.s.proactive_threshold
                or m.proactive_count() >= self.s.max_proactive
                or (m.last_proactive_wall and now - m.last_proactive_wall < self.s.proactive_min_gap_s)
                or any(_jaccard(message, i["text"]) > 0.5 for i in m.interventions)):
            return
        if m.mode == "voice":
            m.pending_voice = {"text": message, "spoken": iv.get("spoken") or message, "value": value, "created": now}
            await self._try_pending_voice(m)
        else:
            await self._post_proactive(m, message, None, value)

    async def _try_pending_voice(self, m: Meeting) -> None:
        pv, now = m.pending_voice, self.clock()
        if not pv:
            return
        if now - pv["created"] > 60:  # the moment has passed
            m.pending_voice = None
        elif now - m.last_utterance_wall >= self.s.voice_silence_s:  # don't talk over people
            m.pending_voice = None
            await self._post_proactive(m, pv["text"], pv["spoken"], pv["value"])

    async def _post_proactive(self, m: Meeting, text: str, spoken: Optional[str], value: float) -> None:
        m.last_proactive_wall = self.clock()
        m.interventions.append({"wall": m.last_proactive_wall, "kind": "proactive", "text": text, "value": value})
        await self.say(m, text, spoken)

    # ------------------------------------------------------------------ skills
    async def pick_skills(self, m: Meeting) -> None:
        prof = m.profile or {}
        query = " ".join([m.topic, m.context[:300], prof.get("domain", ""), " ".join(prof.get("keywords") or [])])
        situation = (f"Meeting topic: {m.topic or '(not given)'}\nDomain: {prof.get('domain', '')}\n"
                     f"Expert persona: {prof.get('expert_persona', '')}\n"
                     f"Where the discussion is: {(m.brief or {}).get('summary', '')}")
        m.last_skill_pick_wall = self.clock()
        try:
            picked = await select_skills(self.llm, self.s.fast_model, self.skills, query, situation, self.s.max_skills)
        except Exception:  # noqa: BLE001
            log.exception("skill selection failed")
            return
        if picked:
            m.skills = picked
            self._skill_text.pop(m.id, None)

    # ------------------------------------------------------------------ research agents and notes
    def start_research(self, m: Meeting, question: str, requested_by: str = "auto") -> ResearchJob:
        context = f"Meeting topic: {m.topic}. {(m.brief or {}).get('summary', '')}"[:1500]
        job = self.researcher.start(question, context, origin=f"meeting:{m.id}",
                                    on_done=lambda j: self._research_done(m, j))
        m.research_ids.append(job.id)
        m.interventions.append({"wall": self.clock(), "kind": "research", "text": f"Research started: {question}",
                                "trigger": requested_by})
        self._maybe_save(m)
        return job

    async def _research_done(self, m: Meeting, job: ResearchJob) -> None:
        self.append_notes(m, Researcher.as_markdown(job))
        if m.status == "live" and job.status == "done" and not m.quiet:
            await self.say(m, f"Research back on \"{job.question[:120]}\": {job.summary}\n(Full findings are in the notes.)")

    def append_notes(self, m: Meeting, markdown: str) -> None:
        if not m.notes_path:
            when = datetime.fromtimestamp(m.created_at, timezone.utc)
            path = Path(self.s.data_dir) / "notes" / f"{when:%Y-%m-%d}-{_slug(m.topic)}-{m.id[:8]}-notes.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# Research and follow-up notes: {m.topic or 'Meeting'}\n\n"
                            "_Kept separate from the meeting memo. Written by research agents during and after the meeting._\n\n")
            m.notes_path = str(path)
        with open(m.notes_path, "a") as f:
            f.write(markdown.rstrip() + "\n\n")
        self._maybe_save(m)

    async def follow_up(self, m: Meeting, report: str) -> None:
        """After the meeting: a follow-up pack per action, plus research agents for open factual questions."""
        actions = (m.brief or {}).get("action_items") or []
        prompt = (f"The meeting is over. Prepare follow-ups.\n\n{self._context_block(m)}\n\nYour memo:\n{report[:15000]}\n\n"
                  "For each action item, write: what done looks like, the first concrete step, anything blocking it, and "
                  "a short draft message the owner could send (if one would help). Then list up to 3 factual questions "
                  "worth researching before the next meeting.\n"
                  'Reply with only JSON: {"followups_markdown": "Markdown, one ### section per action", '
                  '"research_questions": ["..."]}')
        result = await self.llm.json("follow_up", self.s.deep_model, prompt, cached_system=self._expert_system(m),
                                     max_tokens=5000)
        if result.get("followups_markdown") and actions is not None:
            self.append_notes(m, "## Follow-ups on actions\n\n" + str(result["followups_markdown"]))
        if self.researcher:
            for q in (result.get("research_questions") or [])[:3]:
                if str(q).strip():
                    self.start_research(m, str(q), requested_by="follow-up")

    async def notify(self, m: Meeting) -> None:
        if not self.s.notify_webhook_url:
            return
        base = self.s.public_base_url.rstrip("/")
        text = (f"Meeting notes ready: {m.topic or m.meeting_url}\n"
                f"Memo: {base}/meetings/{m.id}/report\nResearch and follow-ups: {base}/meetings/{m.id}/notes")
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                await http.post(self.s.notify_webhook_url, json={"text": text})
        except Exception as e:  # noqa: BLE001
            log.warning("notify failed: %s", e)

    # ------------------------------------------------------------------ wrap-up
    async def finish(self, m: Meeting, leave: bool = False) -> None:
        if m.status in ("finishing", "done"):
            return
        m.status = "finishing"
        self.save(m)
        if leave:
            try:
                await self.recall.leave(m.id)
            except Exception as e:  # noqa: BLE001
                log.warning("leave failed for %s: %s", m.id, e)
        try:
            if m.utterances:
                if m.transcript_len() > m.last_analysis_len:
                    await self.analyze(m)
                report = await self.write_report(m)
                await self.learn(m, report)
                try:
                    await self.follow_up(m, report)
                except Exception:  # noqa: BLE001
                    log.exception("follow-up failed for %s", m.id)
        except Exception as e:  # noqa: BLE001
            log.exception("finish failed for %s", m.id)
            m.error = f"Wrap-up failed: {e}"
        m.status = "done"
        self.save(m)
        await self.notify(m)

    async def write_report(self, m: Meeting) -> str:
        exchanges = "\n".join(f"Q ({e['asker']}): {e['q']}\nA: {e['a']}" for e in m.exchanges) or "(none)"
        prompt = (f"The meeting has ended. Write your consultant's memo for the attendees.\n\n"
                  f"{self._context_block(m)}\n\nQuestions you'd ask after reading the transcript: "
                  f"{json.dumps(m.hindsight_questions)}\n\nWhat people asked you during the meeting:\n{exchanges}\n\n"
                  f"Full transcript:\n{m.transcript_text(150000)}\n\n{REPORT_SECTIONS}")
        report = await self.llm.text("report", self.s.deep_model, prompt, cached_system=self._expert_system(m),
                                     max_tokens=6000)
        when = datetime.fromtimestamp(m.created_at, timezone.utc)
        attendees = ", ".join(sorted(set(m.participants.values()))) or "unknown"
        skills = ", ".join(s["name"] for s in m.skills) or "none"
        path = Path(self.s.data_dir) / "reports" / f"{when:%Y-%m-%d}-{_slug(m.topic)}-{m.id[:8]}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Consultant memo: {m.topic or 'Meeting'}\n\n"
                        f"{when:%d %b %Y %H:%M} UTC · Attendees: {attendees} · Playbooks used: {skills}\n\n"
                        f"{report}\n")
        m.report_path = str(path)
        self.save(m)
        return report

    async def learn(self, m: Meeting, report: str) -> None:
        prof = m.profile or {}
        query = " ".join([m.topic, prof.get("domain", ""), " ".join(prof.get("keywords") or [])])
        related = [s for s in self.skills.search(query, 15) if s.source == "learned"][:3]
        existing = "\n\n".join(f'<existing slug="{s.path.parent.name}" name="{s.name}">\n{SkillLibrary.load(s, 8000)}\n</existing>'
                               for s in related) or "(none)"
        prompt = (
            "You attended a meeting as an AI consultant. Turn what you learned into a reusable skill: a playbook "
            "another AI consultant can load before a similar meeting.\n\n"
            f"Domain: {prof.get('domain', '')}\nExpert persona: {prof.get('expert_persona', '')}\n"
            f"Library playbooks you used: {', '.join(s['name'] for s in m.skills) or 'none'}\n\n"
            f"Your memo from this meeting:\n{report[:20000]}\n\n"
            f"Existing learned skills that may cover this domain:\n{existing}\n\n"
            "Decide: \"update\" an existing learned skill if this meeting deepens the same domain (merge it, keep what is "
            "still true, don't drop useful content); \"create\" a new one for a different domain; or \"none\" if nothing "
            "generalisable was learned.\n"
            "The skill must be general: no attendee names, confidential figures or meeting-specific decisions. Capture "
            "domain knowledge, the questions that exposed real gaps, common pitfalls, frameworks that helped, and signals "
            "to watch for.\n\nReply with only JSON: "
            '{"action": "create|update|none", "slug": "kebab-case (the existing slug if updating)", "name": "...", '
            '"description": "one sentence starting \'Use when\' that says when to load it", '
            '"body": "Markdown with sections: ## When to use, ## Domain knowledge, ## Questions that expose gaps, '
            '## Common pitfalls, ## Frameworks that help, ## Signals to watch for", "reason": "one line"}')
        try:
            result = await self.llm.json("learn", self.s.deep_model, prompt, max_tokens=5000)
        except Exception:  # noqa: BLE001
            log.exception("learning step failed")
            return
        if result.get("action") in ("create", "update") and result.get("body") and result.get("name"):
            path = self.skills.write_learned(str(result.get("slug") or result["name"]), str(result["name"]),
                                             str(result.get("description", "")), str(result["body"]),
                                             meeting_ref=f"meeting {m.id[:8]}")
            m.learned_skill_path = str(path)
            self.save(m)
