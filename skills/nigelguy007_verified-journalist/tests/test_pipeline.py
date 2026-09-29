from conftest import ScriptedLLM

from verified_journalist import Journalist

# Ranking puts transit.gov (primary) first, then reuters (wire), then the local paper.
GOOD = (
    "# Council approves Main Street bus line\n\n"
    "The city council voted 7 to 2 to approve a bus rapid transit line [2]. "
    "\u201cThis is the biggest transit investment in a generation,\u201d Mayor Ana Ruiz said [2].\n\n"
    "Ridership on the corridor rose 18 percent last year, according to the agency [1]. "
    "Shop owners objected: \u201cWe cannot survive two years of torn-up sidewalks\u201d [3].\n\n"
    "## Sources\n1. https://hallucinated.example.com\n"
)
BAD = GOOD.replace(
    "the agency [1].",
    "the agency [1]. Ruiz said \u201cwe will finish the line by 2027 no matter what\u201d [2]. "
    "The line will be free to ride [9].",
)
ALL_OK = [{"sentence": "x", "citations": [1], "verdict": "supported", "note": ""}]


def run(drafts, checks, settings, fake_search, fake_fetcher):
    llm = ScriptedLLM(drafts, checks)
    j = Journalist(settings, llm=llm, search=fake_search, fetcher=fake_fetcher)
    return j.run("Main Street bus rapid transit vote"), llm


def test_clean_draft_is_ready(settings, fake_search, fake_fetcher):
    article, llm = run([GOOD], [ALL_OK], settings, fake_search, fake_fetcher)
    assert article.status == "ready", article.issues
    assert article.revisions == 0
    assert article.headline == "Council approves Main Street bus line"
    assert "hallucinated.example.com" not in article.markdown
    assert "https://www.reuters.com/city/brt-vote" in article.markdown
    assert {s.id for s in article.sources} == {1, 2, 3}


def test_fabricated_quote_and_bad_citation_trigger_revision(settings, fake_search, fake_fetcher):
    unsupported = [
        {
            "sentence": "free to ride",
            "citations": [9],
            "verdict": "unsupported",
            "note": "not in notes",
        }
    ]
    article, llm = run([BAD, GOOD], [unsupported, ALL_OK], settings, fake_search, fake_fetcher)
    assert article.revisions == 1
    assert article.status == "ready"
    assert "no matter what" not in article.markdown


def test_unfixable_draft_is_flagged_not_published_as_ready(settings, fake_search, fake_fetcher):
    unsupported = [{"sentence": "free", "citations": [9], "verdict": "unsupported", "note": "n"}]
    article, _ = run([BAD, BAD, BAD], [unsupported] * 3, settings, fake_search, fake_fetcher)
    assert article.status == "needs_review"
    kinds = {i.kind for i in article.issues if i.severity == "critical"}
    assert {"unverified_quote", "bad_citation", "claim_unsupported"} <= kinds
    assert article.revisions == settings.max_revisions


def test_invented_note_quotes_are_dropped(settings, fake_search, fake_fetcher):
    llm = ScriptedLLM([], [])
    j = Journalist(settings, llm=llm, search=fake_search, fetcher=fake_fetcher)
    sources = j.fetch_sources(fake_search.search("q"))
    notes = j.take_notes("topic", "angle", sources)
    quotes = [f.quote for n in notes for f in n.facts]
    assert not any("resigned in disgrace" in q for q in quotes)
    assert len(quotes) == 4


def test_thin_sourcing_blocks_ready(settings, fake_search, fake_fetcher):
    settings.min_sources = 3
    one_source = "# H\n\nThe city council voted 7 to 2 to approve a bus rapid transit line [1].\n"
    article, _ = run([one_source], [ALL_OK], settings, fake_search, fake_fetcher)
    assert article.status == "needs_review"
    assert any(i.kind == "thin_sourcing" for i in article.issues)
