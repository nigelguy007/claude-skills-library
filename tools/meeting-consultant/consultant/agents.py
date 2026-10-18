"""Research agents: break a question into sub-questions, send a web-searching sub-agent
after each one in parallel, get second opinions from other AI services, then synthesise."""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from .config import Settings
from .llm import LLM
from .providers import Providers

log = logging.getLogger("consultant.agents")


@dataclass
class ResearchJob:
    question: str
    context: str = ""
    origin: str = "assistant"  # assistant | meeting:<id>
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: str = "running"  # running | done | failed
    created: float = field(default_factory=time.time)
    finished: Optional[float] = None
    sub_questions: List[str] = field(default_factory=list)
    findings: List[Dict[str, str]] = field(default_factory=list)
    opinions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    summary: str = ""  # short, chat-ready
    report: str = ""  # full Markdown
    error: Optional[str] = None


DoneCallback = Callable[[ResearchJob], Awaitable[None]]


class Researcher:
    def __init__(self, settings: Settings, llm: LLM, providers: Providers):
        self.s = settings
        self.llm = llm
        self.providers = providers
        self.jobs: Dict[str, ResearchJob] = {}
        self._tasks: Set[asyncio.Task] = set()

    def start(self, question: str, context: str = "", origin: str = "assistant",
              on_done: Optional[DoneCallback] = None) -> ResearchJob:
        job = ResearchJob(question=question.strip(), context=context, origin=origin)
        self.jobs[job.id] = job
        task = asyncio.create_task(self._run(job, on_done))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        jobs = sorted(self.jobs.values(), key=lambda j: -j.created)[:n]
        return [{"id": j.id, "question": j.question, "status": j.status, "summary": j.summary} for j in jobs]

    async def _run(self, job: ResearchJob, on_done: Optional[DoneCallback]) -> None:
        try:
            plan = await self.llm.json(
                "research_plan", self.s.fast_model,
                f"Break this research question into at most {self.s.max_sub_agents} focused sub-questions that can "
                f"each be answered with a web search. Fewer is fine for simple questions.\n\n"
                f"Question: {job.question}\nContext: {job.context or '(none)'}\n\n"
                'Reply with only JSON: {"sub_questions": ["..."]}', max_tokens=500)
            job.sub_questions = [str(q) for q in plan.get("sub_questions") or []][: self.s.max_sub_agents] or [job.question]

            async def investigate(sq: str) -> Dict[str, str]:
                answer = await self.llm.text(
                    "sub_agent", self.s.live_model,
                    f"You are a research sub-agent. Answer this precisely using web search. Give concrete facts, "
                    f"figures and dates, name your sources, and say clearly when evidence is thin or conflicting.\n\n"
                    f"Sub-question: {sq}\nOverall question: {job.question}\nContext: {job.context or '(none)'}",
                    web_search=True, max_tokens=1200)
                return {"question": sq, "answer": answer}

            others = [n for n in self.providers.available() if n != "claude"] if self.s.cross_check else []
            sub_results, opinions = await asyncio.gather(
                asyncio.gather(*(investigate(q) for q in job.sub_questions), return_exceptions=True),
                self.providers.ask_all(f"{job.question}\n\nContext: {job.context}" if job.context else job.question,
                                       others) if others else _empty(),
            )
            job.findings = [r for r in sub_results if isinstance(r, dict)]
            job.opinions = opinions
            if not job.findings:
                raise RuntimeError("every research sub-agent failed")

            synth = await self.llm.json(
                "research_synthesis", self.s.deep_model,
                f"Synthesise this research for a busy team.\n\nQuestion: {job.question}\nContext: {job.context or '(none)'}\n\n"
                f"Sub-agent findings:\n{json.dumps(job.findings)[:40000]}\n\n"
                f"Answers from other AI services (second opinions; may be wrong or out of date):\n"
                f"{json.dumps(job.opinions)[:20000] if job.opinions else '(none)'}\n\n"
                "Lead with the answer. Flag where sources or services disagree and which you trust more and why. "
                "Give a confidence level. Don't invent facts.\n"
                'Reply with only JSON: {"summary": "under 70 words, chat-ready", '
                '"report": "Markdown: answer, key facts with sources, disagreements, confidence, what to check next"}',
                max_tokens=4000)
            job.summary = str(synth.get("summary", "")).strip()
            job.report = str(synth.get("report", "")).strip()
            job.status = "done"
        except Exception as e:  # noqa: BLE001
            log.exception("research job %s failed", job.id)
            job.status, job.error = "failed", f"{type(e).__name__}: {e}"[:300]
        job.finished = time.time()
        if on_done:
            try:
                await on_done(job)
            except Exception:  # noqa: BLE001
                log.exception("research callback failed for %s", job.id)

    @staticmethod
    def as_markdown(job: ResearchJob) -> str:
        if job.status != "done":
            return f"### Research: {job.question}\n\nFailed: {job.error}\n"
        others = ", ".join(n for n, o in job.opinions.items() if "answer" in o)
        return (f"### Research: {job.question}\n\n{job.report or job.summary}\n\n"
                f"_Sub-agents: {len(job.findings)}. Second opinions from: {others or 'none'}._\n")

    def to_dict(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        return asdict(job) if job else None


async def _empty() -> Dict[str, Any]:
    return {}
