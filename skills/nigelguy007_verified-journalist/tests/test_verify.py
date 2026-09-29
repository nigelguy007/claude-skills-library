from verified_journalist.models import Source
from verified_journalist.verify import (
    check_article,
    quote_in_text,
    split_sentences,
    strip_model_sources_section,
)

TEXT = "The minister said: “We will not raise taxes this year, full stop.” Critics disagreed."
SRC = [
    Source(
        id=1,
        url="https://a.gov/x",
        title="t",
        domain="a.gov",
        text=TEXT,
        tier="primary",
        credibility=1.0,
    ),
    Source(
        id=2,
        url="https://b.com/y",
        title="t",
        domain="b.com",
        text="Other text entirely.",
        tier="general",
        credibility=0.5,
    ),
]


def test_quote_matching_ignores_case_punctuation_and_curly_quotes():
    assert quote_in_text("we will NOT raise taxes this year full stop", TEXT)
    assert quote_in_text("We will not raise taxes ... full stop", TEXT)
    assert not quote_in_text("We will never raise taxes", TEXT)
    assert not quote_in_text("full stop ... We will not", TEXT)  # order matters


def test_detects_fabricated_misattributed_and_out_of_range():
    body = (
        'She said "we will not raise taxes this year" [2]. '
        'He said "we will cut every tax next month" [1]. '
        "It was a big year [7]. Growth hit 4.5 percent in the third quarter."
    )
    kinds = [i.kind for i in check_article(body, SRC)]
    assert "misattributed_quote" in kinds
    assert "unverified_quote" in kinds
    assert "bad_citation" in kinds
    assert "uncited_figure" in kinds


def test_citation_after_full_stop_attaches_to_previous_sentence():
    sentences = split_sentences("Taxes stay flat. [1] Critics disagreed [2].")
    assert sentences[0].citations == [1]
    assert sentences[1].citations == [2]


def test_short_scare_quotes_are_not_checked():
    assert check_article('Officials called it a "reset" [1].', SRC) == []


def test_model_written_sources_section_is_removed():
    md = "# H\n\nBody [1].\n\n## References\n- https://made.up/url\n"
    assert strip_model_sources_section(md) == "# H\n\nBody [1]."


def test_stray_urls_flagged():
    issues = check_article("See https://evil.example/x for more [1].", SRC)
    assert [i.kind for i in issues] == ["stray_url"]


def test_multi_sentence_quote_is_still_checked():
    body = "The minister said: “We will not raise taxes. We will double them next year.” [1]"
    kinds = [i.kind for i in check_article(body, SRC)]
    assert "unverified_quote" in kinds


def test_real_multi_sentence_quote_passes():
    src = [SRC[0].model_copy(update={"text": "He said: “We won. Now we rebuild the town.”"})]
    assert check_article("“We won. Now we rebuild the town,” he said [1].", src) == []
