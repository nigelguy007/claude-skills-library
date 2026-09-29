"""Deterministic checks that don't trust any model: citation ranges, verbatim quotes,
uncited figures and stray URLs. These run after every draft and gate the final status."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .models import Issue, Source

CITATION = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
QUOTE = re.compile(r"[“\"]([^“”\"]{2,1200})[”\"]")
URL = re.compile(r"https?://[^\s)\]>]+")
SOURCES_HEADING = re.compile(
    r"^#{1,6}\s*(sources|references|citations|bibliography|works cited)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[\[A-Z“\"(0-9])")
FIGURE = re.compile(r"\d")
MIN_QUOTE_WORDS = 4


@dataclass
class Sentence:
    text: str
    citations: list[int] = field(default_factory=list)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.translate(
        str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
    )
    text = re.sub(r"[^\w\s']", " ", text)
    return " ".join(text.split())


def strip_model_sources_section(markdown: str) -> str:
    """The Sources list is generated from real fetched URLs, never by the model."""
    match = SOURCES_HEADING.search(markdown)
    return markdown[: match.start()].rstrip() if match else markdown.strip()


def citations_in(text: str) -> list[int]:
    found = []
    for group in CITATION.findall(text):
        found.extend(int(n) for n in re.split(r"\s*[,;]\s*", group))
    return found


def paragraphs(markdown: str) -> list[str]:
    """Body paragraphs with headings dropped and list/blockquote markers stripped."""
    out = []
    for block in re.split(r"\n\s*\n", markdown):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        block = re.sub(r"^\s*(?:[-*>]|\d+\.)\s+", "", block, flags=re.MULTILINE)
        out.append(" ".join(block.split()))
    return out


def split_sentences(markdown: str) -> list[Sentence]:
    sentences: list[Sentence] = []
    for block in paragraphs(markdown):
        for piece in SENTENCE_END.split(block):
            # "claim. [2] Next" -> move the leading marker back onto the previous sentence.
            lead = re.match(r"^((?:\[\d+(?:\s*[,;]\s*\d+)*\]\s*)+)(.*)$", piece)
            if lead and sentences:
                sentences[-1].citations.extend(citations_in(lead.group(1)))
                piece = lead.group(2)
            if piece.strip():
                sentences.append(Sentence(piece.strip(), citations_in(piece)))
    return sentences


def quotes_with_citations(markdown: str) -> list[tuple[str, list[int]]]:
    """Each quotation of MIN_QUOTE_WORDS+ words, with the citations inside it plus the first
    citation marker after it in the same paragraph. Works on whole paragraphs so quotes that
    span several sentences are still checked."""
    found = []
    for block in paragraphs(markdown):
        for match in QUOTE.finditer(block):
            quote = match.group(1)
            if len(quote.split()) < MIN_QUOTE_WORDS:
                continue
            cites = citations_in(quote)
            after = CITATION.search(block, match.end())
            if after:
                cites += citations_in(after.group(0))
            found.append((CITATION.sub("", quote).strip(), cites))
    return found


def quote_in_text(quote: str, text: str) -> bool:
    """True if every ellipsis-separated segment of `quote` appears verbatim (modulo case,
    punctuation and whitespace) in `text`, in order."""
    haystack = normalize(text)
    position = 0
    segments = [normalize(s) for s in re.split(r"\.\.\.|…|\[\.\.\.\]", quote)]
    segments = [s for s in segments if s]
    if not segments:
        return True
    for segment in segments:
        found = haystack.find(segment, position)
        if found == -1:
            return False
        position = found + len(segment)
    return True


def check_article(body: str, sources: list[Source]) -> list[Issue]:
    issues: list[Issue] = []
    by_id = {s.id: s for s in sources}
    source_urls = {s.url for s in sources}

    for sentence in split_sentences(body):
        bad = sorted({c for c in sentence.citations if c not in by_id})
        if bad:
            issues.append(
                Issue(
                    severity="critical",
                    kind="bad_citation",
                    detail=f"Cites nonexistent source(s) {bad}: {sentence.text[:200]}",
                )
            )

        uncited_text = CITATION.sub("", sentence.text)
        if not sentence.citations and FIGURE.search(uncited_text) and len(uncited_text) > 30:
            issues.append(
                Issue(
                    severity="warning",
                    kind="uncited_figure",
                    detail=f"Sentence with a figure has no citation: {sentence.text[:200]}",
                )
            )

    for quote, cites in quotes_with_citations(body):
        cited = [by_id[c] for c in cites if c in by_id]
        if any(quote_in_text(quote, s.text) for s in cited):
            continue
        elsewhere = [s.id for s in sources if quote_in_text(quote, s.text)]
        if elsewhere:
            issues.append(
                Issue(
                    severity="critical",
                    kind="misattributed_quote",
                    detail=f'Quote "{quote[:160]}" is in source(s) {elsewhere}, '
                    f"not the cited {cites or 'none'}",
                )
            )
        else:
            issues.append(
                Issue(
                    severity="critical",
                    kind="unverified_quote",
                    detail=f'Quote not found verbatim in any source: "{quote[:160]}"',
                )
            )

    for url in URL.findall(body):
        if url.rstrip(".,;") not in source_urls:
            issues.append(
                Issue(
                    severity="warning",
                    kind="stray_url",
                    detail=f"Body links to a URL that is not a fetched source: {url}",
                )
            )
    return issues


def render_sources(sources: list[Source], used: set[int]) -> str:
    lines = ["## Sources", ""]
    for s in sources:
        if s.id not in used:
            continue
        date = f", {s.published}" if s.published else ""
        lines.append(f"- **[{s.id}]** [{s.title}]({s.url}) ({s.domain}{date})")
    return "\n".join(lines)
