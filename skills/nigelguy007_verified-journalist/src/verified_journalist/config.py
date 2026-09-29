"""Runtime settings, read from environment variables with explicit overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODELS = {
    "anthropic": {"smart": "claude-sonnet-5-5", "fast": "claude-haiku-4-5-20251001"},
    "openai": {"smart": "gpt-5", "fast": "gpt-5-mini"},
}

ARTICLE_STYLES = {
    "news": "a straight news story: inverted pyramid, most important facts first, neutral tone",
    "feature": "a long-form feature: open on a concrete, sourced example, then context and stakes",
    "explainer": "an explainer: answer what happened, why it matters, and what is still unknown",
    "analysis": "a news analysis: facts first, then signposted, source-backed interpretation",
}


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


@dataclass
class Settings:
    llm_provider: str | None = None
    anthropic_api_key: str | None = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: str | None = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    smart_model: str | None = field(default_factory=lambda: _env("VJ_SMART_MODEL"))
    fast_model: str | None = field(default_factory=lambda: _env("VJ_FAST_MODEL"))

    tavily_api_key: str | None = field(default_factory=lambda: _env("TAVILY_API_KEY"))
    brave_api_key: str | None = field(default_factory=lambda: _env("BRAVE_API_KEY"))
    serpapi_api_key: str | None = field(default_factory=lambda: _env("SERPAPI_API_KEY"))

    max_sources: int = 8
    min_sources: int = 3
    max_per_domain: int = 2
    target_words: int = 1200
    max_revisions: int = 2
    style: str = "news"
    recency_days: int | None = None
    concurrency: int = 6
    use_cache: bool = True
    cache_dir: Path = field(
        default_factory=lambda: Path(
            _env("VJ_CACHE_DIR") or Path.home() / ".cache" / "verified-journalist"
        )
    )

    def __post_init__(self) -> None:
        self.llm_provider = self.llm_provider or _env("VJ_LLM_PROVIDER")
        if not self.llm_provider:
            if self.anthropic_api_key:
                self.llm_provider = "anthropic"
            elif self.openai_api_key:
                self.llm_provider = "openai"
        if self.llm_provider and self.llm_provider not in DEFAULT_MODELS:
            raise ValueError(f"Unknown LLM provider {self.llm_provider!r}")
        if self.llm_provider:
            defaults = DEFAULT_MODELS[self.llm_provider]
            self.smart_model = self.smart_model or defaults["smart"]
            self.fast_model = self.fast_model or defaults["fast"]
        if self.style not in ARTICLE_STYLES:
            raise ValueError(f"style must be one of {sorted(ARTICLE_STYLES)}")
        if not 1 <= self.min_sources <= self.max_sources:
            raise ValueError("need 1 <= min_sources <= max_sources")
        self.cache_dir = Path(self.cache_dir)

    def missing(self) -> list[str]:
        """Human-readable list of what is missing before a run can start."""
        problems = []
        if not self.llm_provider:
            problems.append("an LLM key (ANTHROPIC_API_KEY or OPENAI_API_KEY)")
        if not (self.tavily_api_key or self.brave_api_key or self.serpapi_api_key):
            problems.append("a search key (TAVILY_API_KEY, BRAVE_API_KEY or SERPAPI_API_KEY)")
        return problems
