#!/usr/bin/env python3
"""Check outreach drafts before a person reads them.

A draft is a Markdown file with front matter (lead_id, ad_id, ad_quote,
subject, optional test_id) and sections: '## Email A', optional '## Email B',
'## Follow-up 1', '## Follow-up 2', '## LinkedIn note'.

Errors (the draft cannot be sent as it is):
  the email is not exactly 2 lines or runs over the word limit; it does not
  quote the ad, the quote is not word-for-word in the ad that was pulled, or
  it is too short to be a quote; a [placeholder] or a filler opener anywhere
  that gets sent (subject, emails, follow-ups, LinkedIn note); no subject, or
  a fake "Re:"; versions A and B differ in more than one line; more than 2
  follow-ups.
Warnings (a person should look): no question in line 2, a number that is not
  in the ad quote or in the offer's "Proof I can back up", an em dash, a long
  subject or follow-up.

    python3 lint_draft.py outbound/runs/<run>/drafts/*.md \
        --ads outbound/runs/<run>/ads.jsonl --offer outbound/offer.md
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

from ob_common import fold, numeric_tokens, out, parse_front_matter, read_jsonl, split_sections, word_count

DEFAULT_MAX_WORDS = 35
DEFAULT_MAX_LINES = 2
MAX_SUBJECT_WORDS = 6
MAX_FOLLOW_UPS = 2
MIN_QUOTE_WORDS = 3
PROOF_SECTION = "proof i can back up"
MAX_FOLLOW_UP_WORDS = 20
LINKEDIN_NOTE_FREE_LIMIT = 200
LINKEDIN_NOTE_HARD_LIMIT = 300

BANNED_PHRASES = (
    "hope you're well", "hope you are well", "hope this finds you", "hope this email finds you",
    "i wanted to reach out", "just reaching out", "touching base", "i know you're busy", "my name is",
)
_PLACEHOLDER = re.compile(
    r"\[[^\]\n]{1,60}\]|\{\{?[^}\n]{1,60}\}?\}|<[A-Za-z][A-Za-z _-]{0,40}>|%[A-Za-z_]{2,40}%")
_FAKE_THREAD = re.compile(r"\s*(?:re|fwd?)\s*:\s", re.I)
_EMAIL_SECTION = re.compile(r"email(?:\s+([ab]))?$", re.I)


class Finding(NamedTuple):
    level: str  # "error" or "warning"
    code: str
    message: str
    section: str


def _lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _email_sections(sections: Dict[str, str]) -> Dict[str, str]:
    """Map 'A' / 'B' to the email text. A bare '## Email' counts as version A."""
    found: Dict[str, str] = {}
    for name, text in sections.items():
        match = _EMAIL_SECTION.match(name.strip())
        if match:
            found[(match.group(1) or "A").upper()] = text
    return found


def _check_wording(section: str, text: str, quote: str = "") -> List[Finding]:
    """Placeholders and filler openers. Run on everything that reaches the prospect."""
    findings: List[Finding] = []
    if _PLACEHOLDER.search(text.replace(quote, "") if quote else text):
        findings.append(Finding("error", "placeholder", "A [placeholder] is still in the text.", section))
    folded = fold(text)
    for phrase in BANNED_PHRASES:
        if phrase in folded:
            findings.append(Finding("error", "banned-phrase", "Filler opener: %r." % phrase, section))
    return findings


def claims_text(offer_text: Optional[str]) -> Optional[str]:
    """The part of offer.md that may back up a number: the `sell` line and "Proof I can back up".

    The rest of the file (the postal address, the word limit, "Never say") must not count as proof.
    """
    if offer_text is None:
        return None
    meta, body = parse_front_matter(offer_text)
    proof = [text for name, text in split_sections(body).items() if name.strip().lower() == PROOF_SECTION]
    return "%s\n%s" % (meta.get("sell", ""), proof[0] if proof else body)


def _check_subject(subject: str) -> List[Finding]:
    if not subject.strip():
        return [Finding("error", "subject-missing", "No subject in the front matter.", "front matter")]
    findings: List[Finding] = _check_wording("subject", subject)
    if _FAKE_THREAD.match(subject):
        findings.append(Finding("error", "subject-fake-thread",
                                "Subject pretends to be a reply or forward. That is deceptive.", "front matter"))
    if word_count(subject) > MAX_SUBJECT_WORDS:
        findings.append(Finding("warning", "subject-long",
                                "Subject is over %d words." % MAX_SUBJECT_WORDS, "front matter"))
    return findings


def _check_quote_source(meta: Dict[str, str], ads_by_id: Optional[Dict[str, Dict[str, Any]]]) -> List[Finding]:
    quote = meta.get("ad_quote", "")
    if not quote:
        return [Finding("error", "quote-missing", "No ad_quote in the front matter.", "front matter")]
    if ads_by_id is None:
        return [Finding("warning", "quote-unchecked",
                        "No ad records given, so the quote was not checked against the ad.", "front matter")]
    ad = ads_by_id.get(str(meta.get("ad_id", "")))
    if ad is None:
        return [Finding("error", "ad-not-found", "ad_id %r is not in the ad records." % meta.get("ad_id"),
                        "front matter")]
    headline, description = fold(ad.get("headline")), fold(ad.get("description"))
    if fold(quote) not in headline and fold(quote) not in description:
        return [Finding("error", "quote-not-in-ad",
                        "ad_quote is not word-for-word in ad %s. Copy the line from the ad." % ad.get("id"),
                        "front matter")]
    if word_count(quote) < MIN_QUOTE_WORDS and fold(quote) != headline:
        return [Finding("error", "quote-too-short",
                        "ad_quote is under %d words. Quote a whole line of the ad." % MIN_QUOTE_WORDS,
                        "front matter")]
    return []


def _check_numbers(text: str, quote: str, offer_text: Optional[str], section: str) -> List[Finding]:
    if offer_text is None:
        return []
    unbacked = numeric_tokens(text) - numeric_tokens(quote) - numeric_tokens(claims_text(offer_text))
    return [Finding("warning", "unbacked-number",
                    "The number %s is not in the ad quote or the offer file. Can you back it up?" % number,
                    section) for number in sorted(unbacked)]


def _check_email(section: str, text: str, quote: str, offer_text: Optional[str],
                 max_words: int, max_lines: int) -> List[Finding]:
    findings: List[Finding] = []
    lines = _lines(text)
    joined = " ".join(lines)
    folded = fold(joined)
    if len(lines) != max_lines:
        findings.append(Finding("error", "line-count",
                                "%d lines; the email must be exactly %d." % (len(lines), max_lines), section))
    if word_count(joined) > max_words:
        findings.append(Finding("error", "word-count",
                                "%d words; the limit is %d." % (word_count(joined), max_words), section))
    if quote and fold(quote) not in folded:
        findings.append(Finding("error", "quote-missing", "The email does not quote the ad line.", section))
    findings += _check_wording(section, joined, quote)
    if lines and "?" not in lines[-1]:
        findings.append(Finding("warning", "no-question",
                                "The last line has no question. One easy yes/no ask works best.", section))
    if "—" in joined:
        findings.append(Finding("warning", "em-dash", "Em dash: reads as machine-written.", section))
    return findings + _check_numbers(joined, quote, offer_text, section)


def _check_variants(emails: Dict[str, str], meta: Dict[str, str]) -> List[Finding]:
    if "B" not in emails:
        return []
    findings: List[Finding] = []
    if "A" not in emails:
        return [Finding("error", "variant-diff", "Email B exists without an Email A.", "Email B")]
    if not meta.get("test_id"):
        findings.append(Finding("error", "test-id-missing",
                                "Two versions need a test_id in the front matter.", "front matter"))
    a_lines, b_lines = _lines(emails["A"]), _lines(emails["B"])
    changed = sum(1 for a, b in zip(a_lines, b_lines) if fold(a) != fold(b)) + abs(len(a_lines) - len(b_lines))
    if changed == 0:
        findings.append(Finding("error", "variant-diff", "Versions A and B are the same.", "Email B"))
    elif changed > 1:
        findings.append(Finding("error", "variant-diff",
                                "Versions A and B differ in %d lines. Change one thing at a time." % changed,
                                "Email B"))
    return findings


def _check_extras(sections: Dict[str, str]) -> List[Finding]:
    findings: List[Finding] = []
    follow_ups = [(name, text) for name, text in sections.items() if name.lower().startswith("follow")]
    if len(follow_ups) > MAX_FOLLOW_UPS:
        findings.append(Finding("error", "followup-count",
                                "%d follow-ups; the most is %d." % (len(follow_ups), MAX_FOLLOW_UPS),
                                follow_ups[-1][0]))
    for name, text in follow_ups:
        findings += _check_wording(name, text)
        if word_count(text) > MAX_FOLLOW_UP_WORDS:
            findings.append(Finding("warning", "followup-long", "Follow-up should be one short line.", name))
    for name, text in sections.items():
        if not name.lower().startswith("linkedin note"):
            continue
        findings += _check_wording(name, text)
        if len(text) > LINKEDIN_NOTE_HARD_LIMIT:
            findings.append(Finding("error", "li-note-long", "%d characters; LinkedIn cuts notes at %d."
                                    % (len(text), LINKEDIN_NOTE_HARD_LIMIT), name))
        elif len(text) > LINKEDIN_NOTE_FREE_LIMIT:
            findings.append(Finding("warning", "li-note-long", "%d characters; free LinkedIn accounts get %d."
                                    % (len(text), LINKEDIN_NOTE_FREE_LIMIT), name))
    return findings


def lint_draft(text: str, ads_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
               offer_text: Optional[str] = None, max_words: int = DEFAULT_MAX_WORDS,
               max_lines: int = DEFAULT_MAX_LINES) -> List[Finding]:
    """Return every problem found in one draft file."""
    meta, body = parse_front_matter(text)
    sections = split_sections(body)
    emails = _email_sections(sections)
    if not emails:
        return [Finding("error", "no-email", "No '## Email A' section.", "draft")]
    quote = meta.get("ad_quote", "")
    findings = _check_subject(meta.get("subject", "")) + _check_quote_source(meta, ads_by_id)
    for version in sorted(emails):
        findings += _check_email("Email " + version, emails[version], quote, offer_text, max_words, max_lines)
    return findings + _check_variants(emails, meta) + _check_extras(sections)


def passed(findings: List[Finding]) -> bool:
    return not any(finding.level == "error" for finding in findings)


def ads_index(path: Optional[str]) -> Optional[Dict[str, Dict[str, Any]]]:
    """Ad records keyed by id, or None when no file was given."""
    if not path:
        return None
    return {str(ad.get("id")): ad for ad in read_jsonl(path)}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("drafts", nargs="+", help="draft files to check")
    parser.add_argument("--ads", help="ads.jsonl from adlib.py, to check quotes against the real ads")
    parser.add_argument("--offer", help="offer.md, to check numbers and read max_words")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    report: Dict[str, List[Finding]] = {}
    try:
        ads_by_id = ads_index(args.ads)
        offer_text = Path(args.offer).read_text(encoding="utf-8-sig") if args.offer else None
        offer_meta = parse_front_matter(offer_text)[0] if offer_text else {}
        max_words = int(offer_meta.get("max_words") or DEFAULT_MAX_WORDS)
        for name in args.drafts:
            report[name] = lint_draft(Path(name).read_text(encoding="utf-8-sig"), ads_by_id, offer_text, max_words)
    except (OSError, ValueError) as err:
        sys.stderr.write("error: %s\n" % err)
        return 1
    failed = [name for name, findings in report.items() if not passed(findings)]
    if args.json:
        out(json.dumps({name: [finding._asdict() for finding in findings] for name, findings in report.items()},
                       indent=2))
    else:
        for name, findings in report.items():
            out("%s  %s" % ("FAIL" if name in failed else "ok  ", name))
            for finding in findings:
                out("    %-7s %-20s %s (%s)" % (finding.level, finding.code, finding.message, finding.section))
        out("%d of %d drafts pass" % (len(report) - len(failed), len(report)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
