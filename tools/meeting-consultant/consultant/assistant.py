"""Standalone assistant: the same brain outside meetings. Talk to it from the /assistant
voice page (or the API). It can search the web, load skills, ask other AI services,
send research agents, join meetings and read back meeting notes."""
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agents import Researcher, ResearchJob
from .brain import STYLE, Consultant
from .config import Settings
from .llm import LLM
from .providers import Providers
from .skills import SkillLibrary, load_skill_block, select_skills

TOOLS = [
    {"name": "start_research",
     "description": "Send parallel research agents after a question that needs several searches or a careful answer. "
                    "Returns immediately with a job id; findings arrive later in the assistant feed.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}, "context": {"type": "string"}},
                      "required": ["question"]}},
    {"name": "ask_other_ais",
     "description": "Ask other AI services (ChatGPT, Perplexity, any configured custom service) the same question and "
                    "return their answers for comparison. Use for second opinions on contested or fast-moving topics.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"},
                                                       "services": {"type": "array", "items": {"type": "string"}}},
                      "required": ["question"]}},
    {"name": "join_meeting",
     "description": "Send the consultant bot into a Zoom, Google Meet or Teams meeting.",
     "input_schema": {"type": "object", "properties": {
         "meeting_url": {"type": "string"}, "topic": {"type": "string"}, "context": {"type": "string"},
         "mode": {"type": "string", "enum": ["chat", "voice"]}}, "required": ["meeting_url"]}},
    {"name": "list_meetings", "description": "List recent meetings with their status.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_meeting_notes",
     "description": "Read the memo, brief and research notes of a meeting. Use meeting_id 'latest' for the most recent.",
     "input_schema": {"type": "object", "properties": {"meeting_id": {"type": "string"}}, "required": ["meeting_id"]}},
    {"name": "research_status", "description": "List recent research jobs and their summaries.",
     "input_schema": {"type": "object", "properties": {}}},
]


class Assistant:
    def __init__(self, settings: Settings, llm: LLM, skills: SkillLibrary, researcher: Researcher,
                 providers: Providers, consultant: Consultant):
        self.s = settings
        self.llm = llm
        self.skills = skills
        self.researcher = researcher
        self.providers = providers
        self.consultant = consultant
        self.path = Path(settings.data_dir) / "assistant.json"
        state = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.history: List[Dict[str, str]] = state.get("history", [])
        self.feed: List[Dict[str, Any]] = state.get("feed", [])

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"history": self.history[-40:], "feed": self.feed[-100:]}))

    def _post(self, kind: str, text: str, **extra: Any) -> Dict[str, Any]:
        item = {"id": (self.feed[-1]["id"] + 1) if self.feed else 1, "at": time.time(), "kind": kind,
                "text": text, **extra}
        self.feed.append(item)
        self._save()
        return item

    def events_after(self, after: int) -> List[Dict[str, Any]]:
        return [e for e in self.feed if e["id"] > after]

    async def _research_done(self, job: ResearchJob) -> None:
        if job.status == "done":
            self._post("research", f"Research finished: {job.question}. {job.summary}", job_id=job.id,
                       report=job.report)
        else:
            self._post("research", f"Research on \"{job.question}\" failed: {job.error}", job_id=job.id)

    # ---- tool handlers ----
    async def _start_research(self, question: str, context: str = "") -> Dict[str, Any]:
        job = self.researcher.start(question, context, origin="assistant", on_done=self._research_done)
        return {"job_id": job.id, "status": "started"}

    async def _ask_other_ais(self, question: str, services: Optional[List[str]] = None) -> Dict[str, Any]:
        names = [n for n in (services or self.providers.available()) if n != "claude"]
        if not names:
            return {"note": "No other AI services are configured (set OPENAI_API_KEY, PERPLEXITY_API_KEY or CUSTOM_LLM_*)."}
        return await self.providers.ask_all(question, names)

    async def _join_meeting(self, meeting_url: str, topic: str = "", context: str = "", mode: str = "") -> Dict[str, Any]:
        m = await self.consultant.join(meeting_url, topic, context, mode or None)
        return {"meeting_id": m.id, "status": m.status, "mode": m.mode, "note": m.error or ""}

    async def _list_meetings(self) -> List[Dict[str, Any]]:
        ms = sorted(self.consultant.meetings.values(), key=lambda m: -m.created_at)[:10]
        return [{"id": m.id, "topic": m.topic, "status": m.status, "started": time.strftime(
            "%Y-%m-%d %H:%M", time.gmtime(m.created_at))} for m in ms]

    async def _get_meeting_notes(self, meeting_id: str) -> Dict[str, Any]:
        ms = sorted(self.consultant.meetings.values(), key=lambda m: -m.created_at)
        m = ms[0] if meeting_id == "latest" and ms else self.consultant.meetings.get(meeting_id)
        if not m:
            return {"error": "No such meeting"}
        read = lambda p: Path(p).read_text()[:15000] if p and Path(p).exists() else None  # noqa: E731
        return {"topic": m.topic, "status": m.status, "brief": m.brief, "memo": read(m.report_path),
                "notes": read(m.notes_path)}

    async def _research_status(self) -> List[Dict[str, Any]]:
        return self.researcher.recent()

    # ---- conversation ----
    async def ask(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        recent = " ".join(h["content"] for h in self.history[-4:] if h["role"] == "user")
        try:
            skills = await select_skills(self.llm, self.s.fast_model, self.skills, f"{recent} {text}",
                                         f"The user asked their assistant: {text}", max_skills=3)
        except Exception:  # noqa: BLE001
            skills = []
        name = self.s.short_name
        system = (f"You are {name}, the user's personal AI super-agent and consultant. You can search the web, ask "
                  f"other AI services for second opinions, send research agents, join meetings and read meeting notes.\n\n"
                  f"{STYLE}\n\nYour replies are usually read aloud: keep them under 80 words unless the user asks for "
                  "detail, and don't use Markdown tables. When something needs real research, start research agents and "
                  "tell the user you'll report back rather than guessing.")
        block = load_skill_block(skills)
        if block:
            system += f"\n\nPlaybooks that may help (apply where they fit):\n\n{block}"
        messages = self.history[-20:] + [{"role": "user", "content": text}]
        handlers = {"start_research": self._start_research, "ask_other_ais": self._ask_other_ais,
                    "join_meeting": self._join_meeting, "list_meetings": self._list_meetings,
                    "get_meeting_notes": self._get_meeting_notes, "research_status": self._research_status}
        try:
            reply = await self.llm.agent("assistant", self.s.live_model, messages, TOOLS, handlers,
                                         cached_system=system, max_tokens=1500)
        except Exception as e:  # noqa: BLE001
            reply = f"Sorry, my AI service returned an error ({type(e).__name__})."
        reply = reply or "Done."
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        self._post("reply", reply, question=text, skills=[s["name"] for s in skills])
        return reply
