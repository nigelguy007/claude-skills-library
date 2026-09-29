"""The newsroom pipeline: plan -> search -> rank -> fetch -> notes -> draft -> check -> revise.

Orchestration is plain Python rather than an LLM "team leader", so every run takes the same
path, costs a predictable number of calls, and each stage can be tested on its own."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Protocol

from . import prompts
from .cache import DiskCache
from .config import ARTICLE_STYLES, Settings
from .credibility import domain_of, rank_sources
from .fetch import FetchedPage, Fetcher
from .llm import LLM, LLMError, complete_json, make_llm
from .models import (
    Article,
    ClaimCheck,
    FactCheckReport,
    Issue,
    ResearchPlan,
    SearchResult,
    Source,
    SourceNotes,
)
from .search import SearchError, make_search
from .style import lint
from .verify import (
    check_article,
    citations_in,
    quote_in_text,
    render_sources,
    split_sentences,
    strip_model_sources_section,
)

log = logging.getLogger(__name__)
Progress = Callable[[str, str], None]
MAX_SOURCE_CHARS = 24_000


class InsufficientSourcesError(RuntimeError):
    pass


class SearchLike(Protocol):
    def search(self, query: str, max_results: int = 8) -> list[SearchResult]: ...


class FetchLike(Protocol):
    def fetch(self, url: str) -> FetchedPage | None: ...


def _noop(stage: str, detail: str) -> None:
    pass


def _source_block(source: Source) -> str:
    text = source.text[:MAX_SOURCE_CHARS].replace("</source", "&lt;/source")
    return (
        f'<source id="{source.id}" domain="{source.domain}" '
        f'published="{source.published or "unknown"}">\n{text}\n</source>'
    )


def _notes_block(notes: list[SourceNotes], sources: dict[int, Source]) -> str:
    parts = []
    for n in notes:
        s = sources[n.source_id]
        facts = "\n".join(f'- [{s.id}] {f.claim}\n  quote: "{f.quote}"' for f in n.facts)
        parts.append(
            f"### Source [{s.id}]: {s.title}\n"
            f"outlet: {s.domain} | tier: {s.tier} | published: {s.published or 'unknown'}"
            f" | author: {s.author or 'unknown'}\n"
            f"perspective: {n.perspective}\nsummary: {n.summary}\nfacts:\n{facts}"
        )
    return "\n\n".join(parts)


class Journalist:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        llm: LLM | None = None,
        search: SearchLike | None = None,
        fetcher: FetchLike | None = None,
    ) -> None:
        self.settings = settings or Settings()
        cache = DiskCache(self.settings.cache_dir if self.settings.use_cache else None)
        self.llm = llm or make_llm(self.settings)
        self.search = search or make_search(self.settings, cache)
        self.fetcher = fetcher or Fetcher(cache)

    # -- stages -------------------------------------------------------------------------

    def plan(self, topic: str) -> ResearchPlan:
        plan = complete_json(
            self.llm,
            prompts.PLANNER.format(today=date.today().isoformat()),
            f"Topic: {topic}",
            ResearchPlan,
            tier="fast",
            max_tokens=1500,
        )
        queries = list(dict.fromkeys(q.strip() for q in plan.queries if q.strip()))[:5]
        plan.queries = queries or [topic]
        return plan

    def gather(self, queries: list[str]) -> list[SearchResult]:
        def run(q: str) -> list[SearchResult]:
            try:
                return self.search.search(q, max_results=8)
            except SearchError as exc:
                log.warning("%s", exc)
                return []

        with ThreadPoolExecutor(self.settings.concurrency) as pool:
            batches = list(pool.map(run, queries))
        results = [r for batch in batches for r in batch]
        if not results:
            raise InsufficientSourcesError("Search returned no results for any query.")
        return results

    def fetch_sources(self, results: list[SearchResult]) -> list[Source]:
        s = self.settings
        ranked = rank_sources(
            results, s.max_sources * 2, max_per_domain=s.max_per_domain, recency_days=s.recency_days
        )
        with ThreadPoolExecutor(s.concurrency) as pool:
            pages = list(pool.map(lambda item: self.fetcher.fetch(item[0].url), ranked))
        sources: list[Source] = []
        seen_text: set[str] = set()
        for (result, tier, score), page in zip(ranked, pages, strict=True):
            if page is None:
                continue
            fingerprint = page.text[:500]
            if fingerprint in seen_text:  # syndicated copies of the same wire story
                continue
            seen_text.add(fingerprint)
            sources.append(
                Source(
                    id=len(sources) + 1,
                    url=page.url,
                    title=page.title or result.title or page.url,
                    domain=domain_of(page.url),
                    text=page.text,
                    published=page.published or result.published,
                    author=page.author,
                    tier=tier,
                    credibility=score,
                )
            )
            if len(sources) >= s.max_sources:
                break
        return sources

    def take_notes(self, topic: str, angle: str, sources: list[Source]) -> list[SourceNotes]:
        def run(source: Source) -> SourceNotes | None:
            try:
                notes = complete_json(
                    self.llm,
                    prompts.NOTES,
                    f"Topic: {topic}\nAngle: {angle}\n\n{_source_block(source)}",
                    SourceNotes,
                    tier="fast",
                    max_tokens=4000,
                )
            except LLMError as exc:
                log.warning("notes failed for source %s: %s", source.id, exc)
                return None
            notes.source_id = source.id
            # Keep only facts whose supporting quote really is in the page.
            notes.facts = [f for f in notes.facts if quote_in_text(f.quote, source.text)]
            return notes if notes.relevant and notes.facts else None

        with ThreadPoolExecutor(self.settings.concurrency) as pool:
            results = list(pool.map(run, sources))
        return [n for n in results if n]

    def draft(self, topic: str, plan: ResearchPlan, notes_text: str) -> str:
        s = self.settings
        system = prompts.WRITER.format(
            today=date.today().isoformat(), style=ARTICLE_STYLES[s.style], words=s.target_words
        )
        questions = "\n".join(f"- {q}" for q in plan.key_questions)
        prompt = (
            f"Topic: {topic}\nAngle: {plan.angle}\nQuestions readers will have:\n"
            f"{questions}\n\nResearch notes:\n\n{notes_text}"
        )
        return self.llm.complete(
            system, prompt, tier="smart", max_tokens=max(4000, s.target_words * 4)
        )

    def fact_check(self, body: str, notes_text: str) -> list[ClaimCheck]:
        sentences = split_sentences(body)
        if not sentences:
            return []
        numbered = "\n".join(f"{i}. {s.text}" for i, s in enumerate(sentences, 1))
        report = complete_json(
            self.llm,
            prompts.FACT_CHECKER,
            f"Research notes:\n\n{notes_text}\n\nDraft sentences:\n{numbered}",
            FactCheckReport,
            tier="smart",
            max_tokens=8000,
        )
        return report.checks

    def revise(self, body: str, notes_text: str, problems: list[str]) -> str:
        listed = "\n".join(f"- {p}" for p in problems)
        prompt = (
            f"Research notes:\n\n{notes_text}\n\nProblems to fix:\n{listed}\n\nDraft:\n\n{body}"
        )
        return self.llm.complete(
            prompts.EDITOR.format(today=date.today().isoformat()),
            prompt,
            tier="smart",
            max_tokens=max(4000, self.settings.target_words * 4),
        )

    # -- orchestration ------------------------------------------------------------------

    def run(self, topic: str, on_progress: Progress = _noop) -> Article:
        topic = topic.strip()
        if not topic:
            raise ValueError("topic is empty")
        s = self.settings

        on_progress("plan", "Planning the angle and search queries")
        plan = self.plan(topic)

        on_progress("search", f"Searching: {'; '.join(plan.queries)}")
        results = self.gather(plan.queries)

        on_progress("fetch", f"Ranking {len(results)} results and reading the best ones")
        sources = self.fetch_sources(results)
        if not sources:
            raise InsufficientSourcesError(
                "None of the search results could be read (paywalls, blocks or non-article pages)."
            )

        on_progress("notes", f"Extracting verifiable facts from {len(sources)} sources")
        notes = self.take_notes(topic, plan.angle, sources)
        if not notes:
            raise InsufficientSourcesError("No source contained usable, verifiable facts.")
        by_id = {src.id: src for src in sources}
        notes_text = prompts.UNTRUSTED + "\n\n" + _notes_block(notes, by_id)

        on_progress("draft", "Writing the draft")
        body = strip_model_sources_section(self.draft(topic, plan, notes_text))

        revisions, checks, issues = 0, [], []
        while True:
            on_progress("check", f"Fact-checking draft {revisions + 1}")
            issues = check_article(body, sources)
            checks = self.fact_check(body, notes_text)
            style_hits = lint(body)
            problems = [
                f"[{c.verdict}] {c.sentence} -- {c.note}"
                for c in checks
                if c.verdict != "supported"
            ]
            problems += [f"[{i.kind}] {i.detail}" for i in issues]
            problems += [
                f"[style] '{h.phrase}' in: {h.excerpt} -> {h.suggestion}" for h in style_hits
            ]
            if not problems or revisions >= s.max_revisions:
                break
            revisions += 1
            on_progress("revise", f"Revising: {len(problems)} problems (round {revisions})")
            body = strip_model_sources_section(self.revise(body, notes_text, problems))

        issues += self._final_issues(body, checks, notes, lint(body))
        return self._assemble(topic, plan, body, sources, issues, checks, revisions)

    def _final_issues(self, body, checks, notes, style_hits) -> list[Issue]:
        issues = []
        for c in checks:
            if c.verdict in ("unsupported", "contradicted"):
                issues.append(
                    Issue(
                        severity="critical",
                        kind=f"claim_{c.verdict}",
                        detail=f"{c.sentence} -- {c.note}",
                    )
                )
            elif c.verdict == "partially_supported":
                issues.append(
                    Issue(
                        severity="warning", kind="claim_partial", detail=f"{c.sentence} -- {c.note}"
                    )
                )
        for h in style_hits:
            issues.append(Issue(severity="info", kind="style", detail=f"'{h.phrase}': {h.excerpt}"))

        used = Counter(citations_in(body))
        independent = {n.source_id for n in notes if n.source_id in used}
        if len(independent) < self.settings.min_sources:
            issues.append(
                Issue(
                    severity="critical",
                    kind="thin_sourcing",
                    detail=f"Article cites {len(independent)} source(s); "
                    f"minimum is {self.settings.min_sources}.",
                )
            )
        total = sum(used.values())
        if total >= 5:
            top, count = used.most_common(1)[0]
            if count / total > 0.6:
                issues.append(
                    Issue(
                        severity="warning",
                        kind="single_source_dependence",
                        detail=f"{count} of {total} citations point to source [{top}].",
                    )
                )
        return issues

    def _assemble(self, topic, plan, body, sources, issues, checks, revisions) -> Article:
        lines = body.strip().splitlines()
        if lines and lines[0].startswith("# "):
            headline = lines[0][2:].strip()
        else:
            headline = topic
            body = f"# {headline}\n\n{body.strip()}"
        used = set(citations_in(body))
        markdown = f"{body.strip()}\n\n{render_sources(sources, used)}\n"
        status = "needs_review" if any(i.severity == "critical" for i in issues) else "ready"
        return Article(
            topic=topic,
            angle=plan.angle,
            headline=headline,
            markdown=markdown,
            body=body,
            sources=[src for src in sources if src.id in used],
            issues=issues,
            fact_checks=checks,
            revisions=revisions,
            usage=self.llm.usage(),
            status=status,
        )
