"""End-to-end flow with fake Recall and fake Claude: no network, no keys."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from consultant.agents import Researcher
from consultant.app import create_app
from consultant.assistant import Assistant
from consultant.brain import Consultant
from consultant.config import REPO_ROOT, Settings
from consultant.llm import LLM
from consultant.providers import Providers
from consultant.recall import chunk_message
from consultant.skills import SkillLibrary


class FakeRecall:
    def __init__(self):
        self.created, self.chats, self.audio, self.left = [], [], [], []

    async def create_bot(self, meeting_url, bot_name, webhook_url, join_message, metadata=None):
        self.created.append({"url": meeting_url, "name": bot_name, "webhook": webhook_url, "join": join_message})
        return {"id": f"bot-{len(self.created)}"}

    async def send_chat(self, bot_id, message, meeting_url=""):
        self.chats.append(message)

    async def output_audio(self, bot_id, mp3):
        self.audio.append(mp3)

    async def leave(self, bot_id):
        self.left.append(bot_id)

    status = "in_call_recording"

    async def get_bot(self, bot_id):
        return {"id": bot_id, "status_changes": [{"code": "joining_call"}, {"code": self.status}]}


ANALYSIS = {
    "profile": {"domain": "B2B invoicing SaaS", "expert_persona": "fintech product strategist",
                "keywords": ["mvp", "invoice", "pricing"]},
    "topic_shift": False,
    "brief": {"summary": "Scoping an invoice-chasing MVP.", "decisions": ["Web app first"],
              "open_questions": ["Who pays?"], "risks_assumptions": ["SMBs will connect Xero"],
              "action_items": [{"owner": "Sam", "task": "Price check", "due": "Fri"}]},
    "hindsight_questions": ["What evidence says SMBs will pay?", "Why web before email?", "Who owns churn?"],
    "wrapping_up": False,
    "research_requests": ["What do Chaser and Upflow charge?"],
    "intervention": {"value": 9, "type": "risk", "message": "Nobody has tested whether SMBs will connect Xero.",
                     "spoken": "Has anyone tested Xero connection rates?", "why": "core risk"},
}


class FakeLLM:
    def __init__(self):
        self.calls = []
        self.analysis = dict(ANALYSIS)

    async def text(self, purpose, model, prompt, system=None, cached_system=None, max_tokens=0, web_search=False):
        self.calls.append(purpose)
        return {"respond": "Lead with the weakest point: you have no pricing evidence.",
                "spoken": "No pricing evidence yet; details in chat.",
                "report": "## Bottom line\nNot validated yet.",
                "sub_agent": "Chaser starts around £40/month (chaser.io).",
                "provider_claude": "claude view"}.get(purpose, "ok")

    async def json(self, purpose, model, prompt, system=None, cached_system=None, max_tokens=0):
        self.calls.append(purpose)
        if purpose == "analysis":
            return json.loads(json.dumps(self.analysis))
        if purpose == "select_skills":
            return {"skills": [{"name": "pricing-playbook", "why": "pricing is open"}]}
        if purpose == "research_plan":
            return {"sub_questions": ["Chaser pricing", "Upflow pricing"]}
        if purpose == "research_synthesis":
            return {"summary": "Chaser ~£40/mo; Upflow is sales-led.", "report": "## Answer\nChaser ~£40/mo."}
        if purpose == "learn":
            return {"action": "create", "slug": "invoicing-saas-mvp", "name": "invoicing-saas-mvp",
                    "description": "Use when scoping B2B invoicing products.", "body": "## When to use\nInvoicing MVPs."}
        if purpose == "follow_up":
            return {"followups_markdown": "### Sam: price check\nFirst step: list 5 competitors.",
                    "research_questions": ["Xero app marketplace connection rates"]}
        return {}


def make(tmp_path, **overrides):
    skills_dir = tmp_path / "skills"
    for name, desc in [("pricing-playbook", "Pricing strategy for SaaS invoice products"),
                       ("mvp-scoping", "Scope an MVP"), ("gif-maker", "Make gifs")]:
        d = skills_dir / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n# {name}\nBody.")
    s = Settings(skills_dirs=[str(skills_dir)], learned_skills_dir=str(tmp_path / "learned"),
                 data_dir=str(tmp_path / "data"), webhook_token="tok", public_base_url="https://bot.example",
                 address_pause_s=0.05, address_max_wait_s=1, analysis_interval_s=0, min_new_chars=10,
                 proactive_min_gap_s=240, admin_token=None, notify_webhook_url=None)
    for k, v in overrides.items():
        setattr(s, k, v)
    llm, recall = FakeLLM(), FakeRecall()
    library = SkillLibrary(s.skills_dirs, s.learned_skills_dir)
    library.index()
    providers = Providers(s, llm)
    researcher = Researcher(s, llm, providers)
    c = Consultant(s, recall, llm, library, researcher=researcher)
    return s, c, llm, recall


def utter(bot, name, text):
    return {"event": "transcript.data", "data": {"bot": {"id": bot}, "data": {
        "participant": {"id": 1, "name": name},
        "words": [{"text": w, "start_timestamp": {"relative": 1.0}} for w in text.split()]}}}


def chat(bot, name, text):
    return {"event": "participant_events.chat_message",
            "data": {"bot": {"id": bot}, "data": {"participant": {"id": 2, "name": name}, "data": {"text": text}}}}


@pytest.mark.asyncio
async def test_join_configures_bot(tmp_path):
    s, c, llm, recall = make(tmp_path)
    m = await c.join("https://meet.google.com/abc", "MVP", "ctx")
    assert m.id == "bot-1" and m.mode == "chat"
    assert recall.created[0]["webhook"] == "https://bot.example/webhook/recall/realtime?token=tok"
    assert "transcribing" in recall.created[0]["join"]


@pytest.mark.asyncio
async def test_answers_when_named_by_voice_and_in_chat(tmp_path):
    s, c, llm, recall = make(tmp_path)
    m = await c.join("https://zoom.us/j/1", "MVP")
    await c.on_realtime(utter(m.id, "Nigel", "Atlas what do you think about"))
    await c.on_realtime(utter(m.id, "Nigel", "our pricing"))
    await c.drain()
    assert m.status == "live" and len(m.utterances) == 2
    assert recall.chats[-1].startswith("Lead with the weakest point")
    assert "our pricing" in m.exchanges[-1]["q"]
    await c.on_realtime(chat(m.id, "Sam", "@atlas is this viable?"))
    await c.drain()
    assert llm.calls.count("respond") == 2


@pytest.mark.asyncio
async def test_analysis_picks_skills_intervenes_once_and_researches(tmp_path):
    s, c, llm, recall = make(tmp_path)
    m = await c.join("https://zoom.us/j/1", "Invoice MVP pricing")
    await c.on_realtime(utter(m.id, "Nigel", "we think SMBs will connect Xero and pay monthly for chasing invoices"))
    await c.tick()
    await c.drain()
    assert m.brief["decisions"] == ["Web app first"]
    assert m.skills and m.skills[0]["name"] == "pricing-playbook"
    assert any("Xero" in t for t in recall.chats)  # proactive point posted
    assert any(t.startswith("Research back on") for t in recall.chats)  # research agent reported back
    assert Path(m.notes_path).read_text().count("Chaser") >= 1
    proactive_before = m.proactive_count()
    await c.on_realtime(utter(m.id, "Sam", "more discussion about onboarding and the web app layout"))
    await c.tick()
    await c.drain()
    assert m.proactive_count() == proactive_before  # min gap respected, no repeat
    assert len(m.research_ids) == 1  # same research question not repeated


@pytest.mark.asyncio
async def test_commands_quiet_and_brief(tmp_path):
    s, c, llm, recall = make(tmp_path)
    m = await c.join("https://zoom.us/j/1", "MVP")
    await c.on_realtime(chat(m.id, "Sam", "/quiet"))
    assert m.quiet
    await c.on_realtime(utter(m.id, "Nigel", "we think SMBs will connect Xero and pay monthly for chasing"))
    await c.tick()
    await c.drain()
    assert m.proactive_count() == 0
    await c.on_realtime(chat(m.id, "Sam", "/brief"))
    assert "Scoping an invoice-chasing MVP." in recall.chats[-1]
    await c.on_realtime(chat(m.id, "Sam", "/research Upflow pricing"))
    await c.drain()
    assert len(m.research_ids) == 2


@pytest.mark.asyncio
async def test_hindsight_questions_when_wrapping_up(tmp_path):
    s, c, llm, recall = make(tmp_path)
    llm.analysis["wrapping_up"] = True
    m = await c.join("https://zoom.us/j/1", "MVP")
    await c.on_realtime(utter(m.id, "Nigel", "ok let's wrap up and agree next steps for everyone"))
    await c.tick()
    await c.drain()
    hindsight = [t for t in recall.chats if t.startswith("Before you wrap up")]
    assert len(hindsight) == 1 and "What evidence says SMBs will pay?" in hindsight[0]


@pytest.mark.asyncio
async def test_finish_writes_memo_notes_and_learned_skill(tmp_path):
    s, c, llm, recall = make(tmp_path)
    m = await c.join("https://zoom.us/j/1", "Invoice MVP")
    await c.on_realtime(utter(m.id, "Nigel", "we decided web app first and Sam will check prices"))
    await c.finish(m, leave=True)
    await c.drain()
    assert m.status == "done" and recall.left == [m.id]
    assert "Bottom line" in Path(m.report_path).read_text()
    notes = Path(m.notes_path).read_text()
    assert "Follow-ups on actions" in notes and "Research:" in notes
    learned = Path(m.learned_skill_path)
    assert learned.exists() and "Auto-generated" in learned.read_text()
    assert any(sk.source == "learned" for sk in c.skills.skills)


@pytest.mark.asyncio
async def test_status_webhook_ends_meeting(tmp_path):
    s, c, llm, recall = make(tmp_path)
    m = await c.join("https://zoom.us/j/1", "MVP")
    await c.on_realtime(utter(m.id, "Nigel", "hello everyone"))
    await c.on_status({"event": "bot.done", "data": {"bot": {"id": m.id}, "data": {"code": "done"}}})
    await c.drain()
    assert m.status == "done" and recall.left == []


def test_meet_chat_is_chunked_under_limit():
    text = ("This is a long sentence about pricing strategy. " * 40).strip()
    parts = chunk_message(text, 480)
    assert len(parts) > 1 and all(len(p) <= 480 for p in parts)
    assert " ".join(parts).replace("\n", " ").split() == text.split()


def test_indexes_the_real_skill_library():
    lib = SkillLibrary([str(REPO_ROOT / "skills")], "/nonexistent")
    assert lib.index() > 2000
    names = [s.name for s in lib.search("mvp product scope prioritisation", 20)]
    assert names, "expected matches for an MVP query"


def test_webhook_token_and_admin_guard(tmp_path):
    s, c, llm, recall = make(tmp_path, admin_token="secret")
    a = Assistant(s, llm, c.skills, c.researcher, c.researcher.providers, c)
    client = TestClient(create_app(s, c, a))
    with client:
        assert client.post("/webhook/recall/realtime?token=wrong", json={}).status_code == 403
        assert client.post("/webhook/recall/realtime?token=tok", json={"event": "x", "data": {}}).status_code == 200
        assert client.get("/").status_code == 401
        assert client.get("/?key=secret").status_code == 200
        assert client.get("/healthz").json()["skills_indexed"] == 3


# ---- the real tool-use loop in LLM.agent, against a fake Anthropic client ----
class FakeAnthropic:
    def __init__(self):
        self.requests = []
        outer = self

        class Messages:
            async def create(self, **kw):
                outer.requests.append(kw)
                if len(outer.requests) == 1:
                    return SimpleNamespace(stop_reason="tool_use", content=[
                        SimpleNamespace(type="tool_use", id="t1", name="start_research",
                                        input={"question": "UK open banking rules"})])
                return SimpleNamespace(stop_reason="end_turn",
                                       content=[SimpleNamespace(type="text", text="I've started research.")])

        self.messages = Messages()


@pytest.mark.asyncio
async def test_assistant_agent_loop_calls_tools(tmp_path):
    s, c, llm, recall = make(tmp_path)
    real = LLM(s, client=FakeAnthropic())
    started = []

    async def start_research(question, context=""):
        started.append(question)
        return {"job_id": "j1"}

    out = await real.agent("assistant", "m", [{"role": "user", "content": "research open banking"}],
                           [{"name": "start_research", "description": "d", "input_schema": {"type": "object"}}],
                           {"start_research": start_research}, cached_system="sys")
    assert out == "I've started research." and started == ["UK open banking rules"]
    second = real.client.requests[1]["messages"]
    assert second[-1]["content"][0]["type"] == "tool_result"
    assert real.client.requests[0]["tools"][0]["name"] == "web_search"
    assert real.client.requests[0]["system"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_assistant_join_tool(tmp_path):
    s, c, llm, recall = make(tmp_path)
    a = Assistant(s, llm, c.skills, c.researcher, c.researcher.providers, c)
    out = await a._join_meeting("https://zoom.us/j/9", "Board prep")
    assert out["meeting_id"] == "bot-1" and recall.created
    job = await a._start_research("Chaser pricing")
    await c.researcher.drain()
    assert a.events_after(0)[-1]["kind"] == "research"


@pytest.mark.asyncio
async def test_status_polling_notices_call_end_without_dashboard_webhook(tmp_path):
    s, c, llm, recall = make(tmp_path, status_poll_s=0)
    m = await c.join("https://zoom.us/j/1", "MVP")
    await c.tick()
    await c.drain()
    assert m.status == "live"
    await c.on_realtime(utter(m.id, "Nigel", "hello"))
    recall.status = "call_ended"
    await c.tick()
    await c.drain()
    assert m.status == "done" and m.report_path
