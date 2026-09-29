"""Data models shared across the pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    published: str | None = None
    query: str = ""


class Source(BaseModel):
    id: int
    url: str
    title: str
    domain: str
    text: str
    published: str | None = None
    author: str | None = None
    tier: str
    credibility: float


class ResearchPlan(BaseModel):
    angle: str = Field(description="One sentence: the specific question the article answers")
    queries: list[str] = Field(description="3 to 5 distinct web search queries")
    key_questions: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    claim: str = Field(description="A single factual statement, in your own words")
    quote: str = Field(description="Verbatim excerpt from the source that supports the claim")


class SourceNotes(BaseModel):
    source_id: int
    relevant: bool
    summary: str = ""
    perspective: str = Field(default="", description="Whose view the source mainly represents")
    facts: list[Fact] = Field(default_factory=list)


class ClaimCheck(BaseModel):
    sentence: str
    citations: list[int] = Field(default_factory=list)
    verdict: Literal["supported", "partially_supported", "unsupported", "contradicted"]
    note: str = ""


class FactCheckReport(BaseModel):
    checks: list[ClaimCheck] = Field(default_factory=list)


class Issue(BaseModel):
    severity: Literal["critical", "warning", "info"]
    kind: str
    detail: str


class Article(BaseModel):
    topic: str
    angle: str = ""
    headline: str
    markdown: str
    body: str
    sources: list[Source]
    issues: list[Issue] = Field(default_factory=list)
    fact_checks: list[ClaimCheck] = Field(default_factory=list)
    revisions: int = 0
    usage: dict = Field(default_factory=dict)
    status: Literal["ready", "needs_review"]

    @property
    def critical_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "critical"]
