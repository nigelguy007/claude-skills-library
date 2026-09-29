"""Web search providers. Each returns plain SearchResult objects; the first configured wins,
and later providers are used as fallbacks when one errors out."""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from .cache import DiskCache
from .config import Settings
from .models import SearchResult

log = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(20.0)
SEARCH_TTL = 6 * 3600


class SearchError(RuntimeError):
    pass


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]: ...


class TavilySearch:
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query, max_results=8):
        resp = httpx.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"query": query, "max_results": max_results, "search_depth": "advanced"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return [
            SearchResult(
                url=r["url"],
                title=r.get("title", ""),
                snippet=r.get("content", ""),
                published=r.get("published_date"),
                query=query,
            )
            for r in resp.json().get("results", [])
            if r.get("url")
        ]


class BraveSearch:
    name = "brave"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query, max_results=8):
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            params={"q": query, "count": min(max_results, 20)},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return [
            SearchResult(
                url=r["url"],
                title=r.get("title", ""),
                snippet=r.get("description", ""),
                published=r.get("page_age") or r.get("age"),
                query=query,
            )
            for r in resp.json().get("web", {}).get("results", [])
            if r.get("url")
        ]


class SerpApiSearch:
    name = "serpapi"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query, max_results=8):
        resp = httpx.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "num": max_results, "api_key": self.api_key},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return [
            SearchResult(
                url=r["link"],
                title=r.get("title", ""),
                snippet=r.get("snippet", ""),
                published=r.get("date"),
                query=query,
            )
            for r in resp.json().get("organic_results", [])
            if r.get("link")
        ]


class FallbackSearch:
    """Tries providers in order; caches successful responses."""

    def __init__(self, providers: list[SearchProvider], cache: DiskCache | None = None) -> None:
        if not providers:
            raise SearchError("No search provider configured")
        self.providers = providers
        self.cache = cache
        self.name = "+".join(p.name for p in providers)

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        key = f"{query}\0{max_results}"
        if self.cache:
            hit = self.cache.get("search", key, SEARCH_TTL)
            if hit is not None:
                return [SearchResult.model_validate(r) for r in hit]
        errors = []
        for provider in self.providers:
            try:
                results = provider.search(query, max_results)
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                # Never log the exception's request URL: SerpAPI puts the key in it.
                errors.append(f"{provider.name}: {type(exc).__name__}")
                log.warning("search provider %s failed: %s", provider.name, type(exc).__name__)
                continue
            if self.cache:
                self.cache.set("search", key, [r.model_dump() for r in results])
            return results
        raise SearchError(f"All search providers failed for {query!r}: {'; '.join(errors)}")


def make_search(settings: Settings, cache: DiskCache | None = None) -> FallbackSearch:
    providers: list[SearchProvider] = []
    if settings.tavily_api_key:
        providers.append(TavilySearch(settings.tavily_api_key))
    if settings.brave_api_key:
        providers.append(BraveSearch(settings.brave_api_key))
    if settings.serpapi_api_key:
        providers.append(SerpApiSearch(settings.serpapi_api_key))
    return FallbackSearch(providers, cache)
