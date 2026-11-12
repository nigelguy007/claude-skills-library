#!/usr/bin/env python3
"""Rank the advertisers found in an ad-library pull.

Reads the ads.jsonl written by adlib.py, groups the ads by advertiser and
scores each advertiser on signals that can be read straight off the ads:

  company_paid     a company paid for the ad (not one person boosting a post)
  multi_ad         two or more different ads: a steady budget, not a one-off
  number_or_claim  an ad carries a number or a concrete claim worth quoting
  named_owner      a post's author is shown as an owner of the business
  long_running     an ad has been live 30+ days (Meta only: LinkedIn hides dates)

It cannot judge fit with what you sell or company size. The qualifier agent
does that next.

    python3 score.py --ads outbound/runs/<run>/ads.jsonl \
        --out outbound/runs/<run>/advertisers.json --md --top 30
"""
import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from ob_common import atomic_write, fold, normalize_name, out, read_jsonl

Ad = Dict[str, Any]
Row = Dict[str, Any]

LONG_RUNNING_DAYS = 30
MAX_QUOTE_CHARS = 200
MAX_HOOKS = 5

MAX_CLAIM_SCAN_CHARS = 2000

_OWNER = re.compile(
    r"\b(?:co ?founder|founder|owner|ceo|chief executive(?: officer)?|president"
    r"|managing (?:director|partner)|proprietor)\b"
)
# Words that, directly before an owner word, mean the person is not the owner.
_NOT_OWNER = re.compile(
    r"(?:\bvice|\bformer|\bex|\bproduct|\bassistant to(?: the)?|\badvis[eo]r to(?: the)?"
    r"|\boffice of(?: the)?)\s*$"
)
_UNITS = (
    "leads|customers|clients|users|teams|companies|businesses|brands"
    "|meetings|calls|demos|deals|owners|developers|engineers|employees|people"
    "|downloads|reviews|countries|locations|stores|recipes|students|members|subscribers|orders"
    "|sales|integrations|templates|stars"
)
# A number may only start where no digit, comma or dot comes before it. That keeps each
# alternative from re-scanning a long run of digits and commas from every position.
_NUM = r"(?<![\d,.])\d+(?:[,.]\d+)*"
_CLAIM = re.compile(
    r"[$\u20ac\u00a3]\s?\d"                                                 # money
    r"|\d\s?%"                                                               # percent
    r"|(?<![\d.])\d+(?:\.\d+)?x\b"                                          # 3x, 2.5x
    r"|" + _NUM + r"(?:[kmb]|bn)\b"                                           # 10k, 12M
    r"|" + _NUM + r"\s?(?:million|billion)\b"
    r"|(?<![\d.])\d\.\d\s?(?:/|of|out of)\s?5\b|(?<![\d.])\d\s?out of\s?5\b"  # 4.9 of 5, 4 out of 5
    r"|\b(?:save|saves|saved|saving|cut|cuts)\s+(?:up to\s+)?" + _NUM + r"\+?\s+(?:hours|minutes|days|weeks)\b"
    r"|" + _NUM + r"\+?\s+(?:[a-z-]+\s+){0,2}(?:" + _UNITS + r")\b",
    re.I,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_HIRING = re.compile(
    r"\b(?:we(?:'|\u2019)re hiring|we are hiring|now hiring|hiring now|join our team|apply now|apply today"
    r"|open (?:roles?|positions?)|job openings?|careers? (?:at|with))\b",
    re.I,
)
_HIRING_BUTTONS = frozenset(("apply", "apply now", "view jobs", "see jobs"))


def classify_ad(ad: Ad) -> str:
    """'company', 'boosted_by_company' (a person's post a company paid to boost) or 'self_promoted'."""
    is_person = bool(_job_title(ad)) or _is_profile(ad.get("advertiser_url"))
    promoted = (ad.get("promoted_by") or "").strip().lower()
    if is_person and promoted.startswith("promoted by"):
        return "boosted_by_company"
    if is_person or promoted == "promoted":
        return "self_promoted"
    return "company"


def _job_title(ad: Ad) -> str:
    """The poster's job title. LinkedIn's "Promoted" label sometimes arrives in this field: that is not a title."""
    title = (ad.get("poster_title") or "").strip()
    return "" if title.lower().startswith("promoted") else title


def _is_profile(url: Optional[str]) -> bool:
    """True for a person's LinkedIn profile link (as opposed to a company page)."""
    return "linkedin.com/in/" in (url or "")


def owner_role(title: Optional[str]) -> bool:
    """True when a job title reads as a current owner of the business."""
    text = " ".join(re.sub(r"[-\u2010-\u2015]", " ", (title or "").lower()).split())
    return any(not _NOT_OWNER.search(text[:match.start()]) for match in _OWNER.finditer(text))


def contact_hint(ad: Ad) -> Optional[Dict[str, str]]:
    """The post's author, when the ad itself shows them as an owner of the advertiser."""
    title = _job_title(ad)
    if not owner_role(title):
        return None
    kind = classify_ad(ad)
    if kind == "self_promoted":
        basis = "boosted their own post; title shows an owner role"
    elif kind == "boosted_by_company":
        advertiser = normalize_name(ad.get("advertiser"))
        whole_words = r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(advertiser)
        if not advertiser or not re.search(whole_words, normalize_name(title)):
            return None
        basis = "title names the advertiser and an owner role"
    else:
        return None
    profile = ad.get("advertiser_url") if _is_profile(ad.get("advertiser_url")) else None
    return {"name": ad.get("poster") or "", "title": title, "basis": basis, "ad_id": str(ad.get("id")),
            "profile_url": profile}


def has_claim(text: Optional[str]) -> bool:
    return bool(_CLAIM.search((text or "")[:MAX_CLAIM_SCAN_CHARS]))


def _sentences(text: Optional[str]) -> List[str]:
    parts: List[str] = []
    for line in (text or "").splitlines():
        parts.extend(piece.strip() for piece in _SENTENCE_END.split(line))
    return [piece for piece in parts if piece]


def find_claims(text: Optional[str]) -> List[str]:
    """Sentences that carry a number or concrete claim, exactly as written in the ad."""
    return [s for s in _sentences(text) if len(s) <= MAX_QUOTE_CHARS and has_claim(s)]


def hook_candidates(ad: Ad, limit: int = MAX_HOOKS) -> List[Dict[str, Any]]:
    """Lines from the ad worth quoting, best first. Every one is a verbatim substring of the ad."""
    ad_id = str(ad.get("id"))
    headline = (ad.get("headline") or "").strip()

    def hook(text: str, source: str, numbered: bool) -> Dict[str, Any]:
        return {"ad_id": ad_id, "source": source, "has_number": numbered, "text": text}

    hooks: List[Dict[str, Any]] = []
    if headline and has_claim(headline):
        hooks.append(hook(headline, "headline", True))
    hooks.extend(hook(s, "description", True) for s in find_claims(ad.get("description")) if s != headline)
    if headline and not has_claim(headline):
        hooks.append(hook(headline, "headline", False))
    if not hooks:
        first = next((s for s in _sentences(ad.get("description")) if len(s) <= MAX_QUOTE_CHARS), None)
        if first:
            hooks.append(hook(first, "description", False))
    return hooks[:limit]


def _name_key(ad: Ad) -> Tuple[str, str]:
    return (ad.get("library") or "linkedin", normalize_name(ad.get("advertiser")))


def _group(ads: List[Ad]) -> List[List[Ad]]:
    """Group ads by advertiser id. An ad that arrived without its id joins the one company of that name."""
    ids_by_name: Dict[Tuple[str, str], Set[str]] = {}
    for ad in ads:
        if ad.get("advertiser_id"):
            ids_by_name.setdefault(_name_key(ad), set()).add(str(ad["advertiser_id"]))
    groups: Dict[str, List[Ad]] = OrderedDict()
    for ad in ads:
        library, name = _name_key(ad)
        known = ids_by_name.get((library, name), set()) if name else set()
        advertiser_id = ad.get("advertiser_id") or (next(iter(known)) if len(known) == 1 else None)
        if advertiser_id:
            key = "%s:id:%s" % (library, advertiser_id)
        elif name:
            key = "%s:name:%s" % (library, name)
        else:
            key = "%s:ad:%s" % (library, ad.get("id"))  # no usable name: never merge on an empty one
        groups.setdefault(key, []).append(ad)
    return list(groups.values())


def _tags(ads: List[Ad]) -> List[str]:
    """Facts about the ads that are not quality signals but change how you would open."""
    hiring = any(_HIRING.search("%s\n%s" % (ad.get("headline") or "", ad.get("description") or ""))
                 or (ad.get("cta") or "").strip().lower() in _HIRING_BUTTONS for ad in ads)
    return ["hiring"] if hiring else []


def _days_live(ad: Ad, today: date) -> Optional[int]:
    start = ad.get("start_date")
    if not start:
        return None
    try:
        return (today - date.fromisoformat(str(start)[:10])).days
    except ValueError:
        return None


def _unique(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = OrderedDict()
    for item in items:
        seen.setdefault(fold(str(item.get(key))), item)
    return list(seen.values())


def _signals(ads: List[Ad], kinds: Counter, hooks: List[Dict[str, Any]], contacts: List[Dict[str, str]],
             distinct: int, today: date) -> List[str]:
    signals: List[str] = []
    if kinds["company"] or kinds["boosted_by_company"]:
        signals.append("company_paid")
    if distinct >= 2 or any((ad.get("duplicates") or 0) >= 2 for ad in ads):
        signals.append("multi_ad")
    if any(h["has_number"] for h in hooks):
        signals.append("number_or_claim")
    if contacts:
        signals.append("named_owner")
    if any((_days_live(ad, today) or 0) >= LONG_RUNNING_DAYS for ad in ads):
        signals.append("long_running")
    return signals


def _tier(score: int) -> str:
    if score >= 3:
        return "strong"
    return {2: "good", 1: "maybe"}.get(score, "weak")


def _score_group(ads: List[Ad], today: date) -> Row:
    first = next((ad for ad in ads if ad.get("advertiser_id")), ads[0])
    kinds = Counter(classify_ad(ad) for ad in ads)
    hooks = _unique([h for ad in ads for h in hook_candidates(ad)], "text")
    hooks = sorted(hooks, key=lambda h: not h["has_number"])[:MAX_HOOKS]
    contacts = _unique([c for c in (contact_hint(ad) for ad in ads) if c], "name")
    distinct = len({fold("%s\n%s" % (ad.get("headline") or "", ad.get("description") or "")) for ad in ads})
    own_name = normalize_name(first.get("advertiser"))
    businesses = sorted({ad["paid_for_by"] for ad in ads
                         if ad.get("paid_for_by") and normalize_name(ad["paid_for_by"]) != own_name})
    signals = _signals(ads, kinds, hooks, contacts, distinct, today)
    only_personal = kinds["self_promoted"] == len(ads)
    skip = "personal post: the poster is not shown as an owner" if only_personal and not contacts else None
    return {
        "advertiser": str(first.get("advertiser") or ""),
        "library": first.get("library") or "linkedin",
        "advertiser_id": first.get("advertiser_id"),
        "advertiser_url": first.get("advertiser_url"),
        "business_names": businesses,
        "ad_count": len(ads),
        "distinct_creatives": distinct,
        "kinds": dict(kinds),
        "signals": signals,
        "score": len(signals),
        "tier": _tier(len(signals)),
        "tags": _tags(ads),
        "skip_reason": skip,
        "hook_candidates": hooks,
        "contact_hints": contacts,
        "ads": [{"id": str(ad.get("id")), "url": ad.get("url"), "kind": classify_ad(ad),
                 "headline": ad.get("headline"), "cta": ad.get("cta"), "start_date": ad.get("start_date"),
                 "destination_url": ad.get("destination_url")} for ad in ads],
    }


def rank(ads: List[Ad], today: Optional[date] = None) -> List[Row]:
    """Group ads by advertiser and return the advertisers best first, skipped ones last."""
    today = today or date.today()
    rows = [_score_group(group, today) for group in _group(ads)]
    ordered = sorted(rows, key=lambda r: (r["skip_reason"] is not None, -r["score"], -r["ad_count"],
                                          str(r["advertiser"]).lower()))
    return [dict(row, rank=position) for position, row in enumerate(ordered, 1)]


def _cell(text: Any, width: int = 90) -> str:
    flat = " ".join(str(text or "").split()).replace("|", "\\|")
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def to_markdown(ranked: List[Row], limit: Optional[int] = None) -> str:
    """A table for reading. Lines are shortened here: quote from advertisers.json, not from this table."""
    lines = ["| # | Advertiser | Ads | Tier | Signals | Best line | Contact hint | Note |",
             "|---|---|---|---|---|---|---|---|"]
    for index, row in enumerate(ranked[:limit] if limit and limit > 0 else ranked, 1):
        hook = row["hook_candidates"][0]["text"] if row["hook_candidates"] else ""
        contact = row["contact_hints"][0] if row["contact_hints"] else None
        hint = "%s (%s)" % (contact["name"], contact["title"]) if contact else ""
        name = row["advertiser"]
        if row["business_names"]:
            name += " / " + ", ".join(row["business_names"])
        note = "; ".join(part for part in (row["skip_reason"], "hiring ad" if "hiring" in row["tags"] else "") if part)
        lines.append("| %d | %s | %d | %s | %s | %s | %s | %s |" % (
            index, _cell(name, 50), row["ad_count"], row["tier"], _cell(", ".join(row["signals"]), 70),
            _cell(hook), _cell(hint, 70), _cell(note, 70)))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ads", required=True, help="ads.jsonl written by adlib.py")
    parser.add_argument("--out", help="where to write the ranked advertisers as JSON")
    parser.add_argument("--md", action="store_true", help="print a Markdown table")
    parser.add_argument("--top", type=int, default=None, help="only show this many rows in the table")
    args = parser.parse_args(argv)

    try:
        ads = read_jsonl(args.ads)
    except (OSError, ValueError) as err:
        sys.stderr.write("error: %s\n" % err)
        return 1
    if not ads:
        sys.stderr.write("error: no ads in %s\n" % args.ads)
        return 1
    ranked = rank(ads)
    if args.out:
        atomic_write(args.out, json.dumps(ranked, indent=2, ensure_ascii=False) + "\n")
    if args.md:
        out(to_markdown(ranked, args.top))
    usable = [row for row in ranked if row["skip_reason"] is None]
    out(json.dumps({"ads": len(ads), "advertisers": len(ranked), "usable": len(usable),
                    "by_tier": dict(Counter(row["tier"] for row in usable)), "out": args.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
