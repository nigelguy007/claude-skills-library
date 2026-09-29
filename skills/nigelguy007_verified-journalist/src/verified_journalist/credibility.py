"""Source ranking: URL canonicalisation, de-duplication, domain tiers and diversity caps.

The tiers are a starting point, not a truth oracle. Override them with
`rank_sources(..., extra_tiers={"example.com": "primary"})`.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import SearchResult

TIER_SCORES = {
    "primary": 1.0,
    "wire": 0.95,
    "major": 0.85,
    "reference": 0.75,
    "general": 0.55,
    "low": 0.25,
}

PRIMARY_SUFFIXES = (".gov", ".mil", ".edu", ".int", ".gov.uk", ".ac.uk", ".gc.ca", ".europa.eu")
DOMAIN_TIERS = {
    # Primary documents, research and official data
    "who.int": "primary",
    "un.org": "primary",
    "oecd.org": "primary",
    "imf.org": "primary",
    "worldbank.org": "primary",
    "nature.com": "primary",
    "science.org": "primary",
    "thelancet.com": "primary",
    "nejm.org": "primary",
    "arxiv.org": "primary",
    "pubmed.ncbi.nlm.nih.gov": "primary",
    "courtlistener.com": "primary",
    # Wire services and investigative outfits
    "reuters.com": "wire",
    "apnews.com": "wire",
    "afp.com": "wire",
    "bloomberg.com": "wire",
    "propublica.org": "wire",
    "icij.org": "wire",
    "bellingcat.com": "wire",
    # Major news organisations
    "nytimes.com": "major",
    "wsj.com": "major",
    "washingtonpost.com": "major",
    "ft.com": "major",
    "economist.com": "major",
    "bbc.co.uk": "major",
    "bbc.com": "major",
    "theguardian.com": "major",
    "npr.org": "major",
    "latimes.com": "major",
    "axios.com": "major",
    "politico.com": "major",
    "cnbc.com": "major",
    "aljazeera.com": "major",
    "theatlantic.com": "major",
    "newyorker.com": "major",
    "statnews.com": "major",
    "arstechnica.com": "major",
    "wired.com": "major",
    "theverge.com": "major",
    "techcrunch.com": "major",
    "nikkei.com": "major",
    "spiegel.de": "major",
    "lemonde.fr": "major",
    # Reference
    "wikipedia.org": "reference",
    "britannica.com": "reference",
    # User-generated, aggregators and content farms
    "medium.com": "low",
    "substack.com": "low",
    "reddit.com": "low",
    "quora.com": "low",
    "pinterest.com": "low",
    "facebook.com": "low",
    "x.com": "low",
    "twitter.com": "low",
    "tiktok.com": "low",
    "instagram.com": "low",
    "linkedin.com": "low",
    "youtube.com": "low",
    "msn.com": "low",
    "yahoo.com": "low",
    "blogspot.com": "low",
    "wordpress.com": "low",
}
TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "cmpid",
    "smid",
    "ocid",
    "igshid",
    "si",
}


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def tier_for(domain: str, extra_tiers: dict[str, str] | None = None) -> str:
    table = {**DOMAIN_TIERS, **(extra_tiers or {})}
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in table:
            return table[candidate]
    if domain.endswith(PRIMARY_SUFFIXES):
        return "primary"
    return "general"


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%b %d, %Y",
    ):
        try:
            parsed = datetime.strptime(value.strip().replace("Z", "+0000")[:25], fmt)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def score(result: SearchResult, tier: str, recency_days: int | None, hits: int) -> float:
    value = TIER_SCORES[tier]
    value += min(hits - 1, 2) * 0.05  # appeared for several queries: likely central
    published = _parse_date(result.published)
    if recency_days and published:
        age = (datetime.now(timezone.utc) - published).days
        value += 0.1 if age <= recency_days else -0.2
    return round(value, 3)


def rank_sources(
    results: list[SearchResult],
    limit: int,
    *,
    max_per_domain: int = 2,
    recency_days: int | None = None,
    extra_tiers: dict[str, str] | None = None,
    min_tier_score: float = 0.25,
) -> list[tuple[SearchResult, str, float]]:
    """De-duplicate, score and pick up to `limit` results with a per-domain cap."""
    by_url: dict[str, SearchResult] = {}
    hits: Counter[str] = Counter()
    for r in results:
        key = canonical_url(r.url)
        hits[key] += 1
        by_url.setdefault(key, r)

    scored = []
    for key, r in by_url.items():
        tier = tier_for(domain_of(r.url), extra_tiers)
        if TIER_SCORES[tier] < min_tier_score:
            continue
        scored.append((r, tier, score(r, tier, recency_days, hits[key])))
    scored.sort(key=lambda item: item[2], reverse=True)

    picked, per_domain = [], Counter()
    for r, tier, value in scored:
        domain = domain_of(r.url)
        if per_domain[domain] >= max_per_domain:
            continue
        per_domain[domain] += 1
        picked.append((r, tier, value))
        if len(picked) >= limit:
            break
    return picked
