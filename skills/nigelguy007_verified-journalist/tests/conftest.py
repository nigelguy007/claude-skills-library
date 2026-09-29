from __future__ import annotations

import json

import pytest

from verified_journalist import Settings
from verified_journalist.fetch import FetchedPage
from verified_journalist.models import SearchResult

REUTERS = (
    "The city council voted 7 to 2 on Tuesday to approve a new bus rapid transit line along "
    "Main Street. Mayor Ana Ruiz said the project would cut average commute times by 12 minutes. "
    '"This is the biggest transit investment in a generation," Ruiz told reporters after the '
    "vote. The line is expected to cost $240 million, with 60 percent paid by federal grants. "
) * 3
LOCALNEWS = (
    "Business owners on Main Street opposed the plan, arguing that two years of construction "
    'would drive customers away. "We cannot survive two years of torn-up sidewalks," said '
    "Dana Cole, who owns a bakery on the street. The chamber of commerce asked for a phased "
    "construction schedule, which the council rejected. "
) * 3
AGENCY = (
    "According to the regional transit agency's 2025 ridership report, bus ridership on the Main "
    "Street corridor rose 18 percent year over year, the fastest growth of any route in the "
    "system. The agency projects 25,000 daily riders on the new line by 2030. "
) * 3

PAGES = {
    "https://www.reuters.com/city/brt-vote": ("Council approves bus line", REUTERS),
    "https://localnews.example.org/brt-opposition": ("Shop owners push back", LOCALNEWS),
    "https://transit.gov/reports/2025": ("2025 ridership report", AGENCY),
}


class FakeSearch:
    def __init__(self):
        self.queries = []

    def search(self, query, max_results=8):
        self.queries.append(query)
        return [SearchResult(url=u, title=t, query=query) for u, (t, _) in PAGES.items()]


class FakeFetcher:
    def fetch(self, url):
        if url not in PAGES:
            return None
        title, text = PAGES[url]
        return FetchedPage(url=url, text=text, title=title, published="2026-09-01")


class ScriptedLLM:
    """Routes by which prompt it receives; `drafts` is consumed in order by writer/editor."""

    def __init__(self, drafts, checks):
        self.drafts = list(drafts)
        self.checks = list(checks)
        self.calls = []

    def usage(self):
        return {"fake": {"calls": len(self.calls), "input_tokens": 0, "output_tokens": 0}}

    def complete(self, system, prompt, *, tier="smart", max_tokens=4096):
        self.calls.append(system[:40])
        if "assignment editor" in system:
            return json.dumps(
                {
                    "angle": "Will the new bus line pay off?",
                    "queries": ["main street brt vote", "main street brt opposition"],
                    "key_questions": ["What does it cost?"],
                }
            )
        if "research assistant" in system:
            return self._notes(prompt)
        if "fact-checker" in system:
            return json.dumps({"checks": self.checks.pop(0)})
        return self.drafts.pop(0)

    @staticmethod
    def _notes(prompt):
        sid = int(prompt.split('<source id="')[1].split('"')[0])
        facts = {
            1: [
                {
                    "claim": "Council approved 7-2",
                    "quote": "The city council voted 7 to 2 on "
                    "Tuesday to approve a new bus rapid transit line along Main Street",
                },
                {
                    "claim": "Ruiz quote",
                    "quote": "This is the biggest transit investment in a generation",
                },
                {"claim": "Invented fact", "quote": "the mayor resigned in disgrace on Friday"},
            ],
            2: [
                {
                    "claim": "Owners opposed",
                    "quote": "We cannot survive two years of torn-up sidewalks",
                }
            ],
            3: [
                {
                    "claim": "Ridership up 18%",
                    "quote": "bus ridership on the Main Street "
                    "corridor rose 18 percent year over year",
                }
            ],
        }
        # Pick the fact set whose first quote belongs to this source's text.
        facts = next(v for v in facts.values() if v[0]["quote"][:30] in prompt)
        return (
            "```json\n"
            + json.dumps(
                {
                    "source_id": sid,
                    "relevant": True,
                    "summary": "s",
                    "perspective": "p",
                    "facts": facts,
                }
            )
            + "\n```"
        )


@pytest.fixture
def settings(tmp_path):
    return Settings(
        llm_provider="anthropic",
        anthropic_api_key="x",
        tavily_api_key="x",
        use_cache=False,
        cache_dir=tmp_path,
        max_revisions=2,
    )


@pytest.fixture
def fake_search():
    return FakeSearch()


@pytest.fixture
def fake_fetcher():
    return FakeFetcher()
