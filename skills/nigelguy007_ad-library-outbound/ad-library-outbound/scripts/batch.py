#!/usr/bin/env python3
"""Build send batches, keep the send log and read the results honestly.

Nothing here sends email. `build` writes a CSV for your sending tool; you
send, then tell the log what happened.

    python3 batch.py init     --suppression outbound/suppression.csv --log outbound/log.csv
    python3 batch.py approve  --run outbound/runs/<run> --lead-id L-261112-01 [...] | --all
    python3 batch.py build    --run outbound/runs/<run> --offer outbound/offer.md \
                              --suppression outbound/suppression.csv --log outbound/log.csv
    python3 batch.py mark-sent --sheet outbound/runs/<run>/send-sheet-<batch>.csv --log outbound/log.csv
    python3 batch.py record   --log outbound/log.csv --suppression outbound/suppression.csv \
                              --lead-id L-261112-01 --event reply
    python3 batch.py suppress --suppression outbound/suppression.csv --value rival.com --reason competitor
    python3 batch.py stats    --log outbound/log.csv [--test-id T1-first-line]

A lead is only put on a send sheet when the company's identity is verified,
the address is verified or published, the country is one the offer allows, it
is not suppressed and not already contacted, its draft was approved with
`approve` and has not changed since, and the draft passes lint.

What this cannot prove: `identity_check`, `email_status` and `country` are
read from the lead file, which the qualifier agent writes. The checks here
stop a lead that is marked unready. They do not re-verify one marked ready.

`approve` records the user's decision. Run it only after the user has read
the draft and said yes. Opt-outs and bounces go on the suppression list the
moment they are recorded, and the list is matched by address and by domain
including subdomains.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date
from math import comb, sqrt
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

import lint_draft
from ob_common import (PathLike, append_csv, atomic_write, bare_address, domain_matches, domain_of, is_domain,
                       normalize_address, out, parse_front_matter, read_csv, read_jsonl, set_front_matter,
                       split_sections, valid_id, write_csv)

EVENTS = ("sent", "reply", "positive", "optout", "bounce")
SUPPRESSING_EVENTS = ("optout", "bounce")
SENDABLE_STATUSES = ("verified", "published")
REQUIRED_OFFER_KEYS = ("sell", "countries", "sender_name", "sending_domain", "postal_address", "opt_out_line")
FREE_MAIL = frozenset("gmail.com googlemail.com outlook.com hotmail.com live.com yahoo.com icloud.com me.com "
                      "aol.com proton.me protonmail.com gmx.com".split())
HONORIFICS = frozenset("dr dr. mr mr. mrs mrs. ms ms. mx mx. prof prof. sir".split())
DEFAULT_BATCH_SIZE = 25
MAX_BATCH_SIZE = 30
MIN_SENDS_PER_VERSION = 50
LEADER_P_VALUE = 0.10
BOUNCE_ALARM_RATE = 0.05
BOUNCE_ALARM_MIN_SENDS = 10
LOG_FIELDS = ("date", "batch_id", "test_id", "variant", "lead_id", "email", "event", "note")
LOG_REQUIRED = ("lead_id", "email", "event")
SUPPRESSION_FIELDS = ("value", "reason", "date")
SHEET_FIELDS = ("batch_id", "test_id", "variant", "lead_id", "email", "first_name", "company", "subject",
                "body", "followup_1", "followup_2", "ad_url")

Lead = Dict[str, str]
Row = Dict[str, str]


class Suppression(NamedTuple):
    emails: Set[str]
    domains: Set[str]


class Contacted(NamedTuple):
    emails: Set[str]
    domains: Set[str]


# ---------------------------------------------------------------- offer

def validate_offer(offer: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings). Errors stop a batch from being built."""
    errors = ["offer.md is missing '%s'" % key for key in REQUIRED_OFFER_KEYS if not (offer.get(key) or "").strip()]
    warnings: List[str] = []
    sending, main = domain_of(offer.get("sending_domain")), domain_of(offer.get("main_domain"))
    if sending and main and sending == main:
        warnings.append("sending_domain is your main domain: cold email from it puts your everyday mail at risk")
    for country in _countries(offer):
        if country != "US":
            warnings.append("%s: cold email rules differ from the US there. Read references/sending-rules.md "
                            "before sending" % country)
    return errors, warnings


def _countries(offer: Dict[str, str]) -> List[str]:
    return [c.strip().upper() for c in (offer.get("countries") or "").split(",") if c.strip()]


def footer(offer: Dict[str, str]) -> str:
    """Who is writing, a real postal address and a way to say no. Goes under every email."""
    identity = [offer.get("sender_name", ""), offer.get("sender_company", ""), offer.get("postal_address", "")]
    return "\n".join(part.strip() for part in identity if part.strip()) + "\n\n" + offer.get("opt_out_line", "").strip()


# ---------------------------------------------------------------- suppression and history

def suppression_entry(value: Optional[str]) -> Tuple[str, str]:
    """('email', address) or ('domain', domain). Anything else is an error, never stored as-is."""
    text = (value or "").strip()
    address = normalize_address(text)
    if address:
        return ("email", address)
    candidate = text.lower()
    for prefix in ("*.", "*@", "@"):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
    domain = domain_of(candidate) if "@" not in candidate else ""
    if is_domain(domain):
        return ("domain", domain)
    raise ValueError("%r is neither an email address nor a domain" % text)


def load_suppression(path: PathLike) -> Suppression:
    """Read the never-contact list. A file that cannot be understood is an error, not an empty list."""
    emails: Set[str] = set()
    domains: Set[str] = set()
    for number, row in enumerate(read_csv(path, required=("value",)), 2):
        value = (row.get("value") or "").strip()
        if not value:
            continue
        try:
            kind, normal = suppression_entry(value)
        except ValueError as err:
            raise ValueError("%s line %d: %s" % (path, number, err)) from err
        (emails if kind == "email" else domains).add(normal)
    return Suppression(emails, domains)


def add_suppression(path: PathLike, value: str, reason: str, day: str) -> str:
    """Add an address or a domain to the never-contact list and return what was stored."""
    _, normal = suppression_entry(value)
    append_csv(path, SUPPRESSION_FIELDS, [{"value": normal, "reason": reason, "date": day}])
    return normal


def contacted_from_log(rows: List[Dict[str, str]]) -> Contacted:
    """Everyone already emailed. Company domains count; free-mail domains do not."""
    emails = {bare_address(row.get("email")) for row in rows if _event(row) == "sent"}
    emails.discard("")
    domains = {domain_of(email) for email in emails} - FREE_MAIL
    return Contacted(emails, domains)


def eligibility(lead: Lead, offer: Dict[str, str], suppression: Suppression, contacted: Contacted) -> Optional[str]:
    """None when the lead may be emailed, otherwise the reason it may not."""
    if (lead.get("identity_check") or "").strip().lower() != "verified":
        return "company identity not verified"
    email = bare_address(lead.get("email"))
    if not email:
        return "no valid email (it must be one plain address)"
    status = (lead.get("email_status") or "none").strip().lower()
    if status not in SENDABLE_STATUSES:
        return "email is %s, not verified or published" % status
    country = (lead.get("country") or "").strip().upper()
    if not country:
        return "country unknown"
    if country not in _countries(offer):
        return "country %s is not in the offer's countries" % country
    domains = {d for d in (domain_of(email), domain_of(lead.get("domain"))) if d}
    if email in suppression.emails or any(domain_matches(d, suppression.domains) for d in domains):
        return "suppressed (opt-out, bounce or exclusion list)"
    if email in contacted.emails or any(domain_matches(d, contacted.domains) for d in domains - FREE_MAIL):
        return "already contacted"
    return None


# ---------------------------------------------------------------- approval

def _draft_parts(draft_text: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """(front matter, sections keyed by lowercased heading)."""
    meta, body = parse_front_matter(draft_text)
    return meta, {name.strip().lower(): text for name, text in split_sections(body).items()}


def _sent_sections(sections: Dict[str, str]) -> List[Tuple[str, str]]:
    """The sections that end up in someone's inbox, as (name, text with tidy whitespace)."""
    return [(name, "\n".join(line.strip() for line in text.splitlines() if line.strip()))
            for name, text in sorted(sections.items()) if name.startswith(("email", "follow"))]


def approval_hash(lead: Lead, draft_text: str) -> str:
    """A fingerprint of exactly what the user approved: who it goes to and every word that is sent."""
    meta, sections = _draft_parts(draft_text)
    parts = [meta.get("lead_id", ""), bare_address(lead.get("email")), meta.get("ad_id", ""),
             meta.get("ad_quote", ""), meta.get("subject", ""), meta.get("test_id", "")]
    for name, text in _sent_sections(sections):
        parts.extend((name, text))
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def approve_draft(draft_text: str, lead: Lead) -> str:
    """Return the draft marked as approved by the user for this lead's address."""
    return set_front_matter(draft_text, {"approved": "yes", "approved_sha256": approval_hash(lead, draft_text)})


def _approval_problem(draft_text: str, lead: Lead) -> Optional[str]:
    meta = parse_front_matter(draft_text)[0]
    if meta.get("approved", "").strip().lower() not in ("yes", "true") or not meta.get("approved_sha256"):
        return "draft not approved yet: once the user has read it, run `batch.py approve`"
    if meta["approved_sha256"] != approval_hash(lead, draft_text):
        return "draft or address changed after approval: show it to the user and approve it again"
    return None


# ---------------------------------------------------------------- building a batch

def assign_variants(lead_ids: List[str]) -> Dict[str, str]:
    """Split leads evenly between A and B in an order unrelated to how the leads were ranked."""
    shuffled = sorted(lead_ids, key=lambda lead_id: hashlib.sha256(lead_id.encode("utf-8")).hexdigest())
    return {lead_id: "AB"[index % 2] for index, lead_id in enumerate(shuffled)}


def _lint_errors(draft_text: str, ads_by_id: Optional[Dict[str, Dict[str, Any]]], offer_text: Optional[str],
                 offer: Dict[str, str]) -> List[str]:
    max_words = int(offer.get("max_words") or lint_draft.DEFAULT_MAX_WORDS)
    findings = lint_draft.lint_draft(draft_text, ads_by_id, offer_text, max_words)
    return sorted({finding.code for finding in findings if finding.level == "error"})


def _first_name(contact_name: Optional[str]) -> str:
    names = [part for part in (contact_name or "").split() if part.lower() not in HONORIFICS]
    return names[0] if names else ""


def _sheet_row(lead: Lead, draft_text: str, variant: str, offer: Dict[str, str], batch_id: str) -> Row:
    meta, sections = _draft_parts(draft_text)
    email_text = sections.get("email b") if variant == "B" else (sections.get("email a") or sections.get("email"))
    lines = [line.strip() for line in (email_text or "").splitlines() if line.strip()]
    follow_ups = [text for name, text in sections.items() if name.startswith("follow")]
    ad_url = (lead.get("ad_url") or "").strip()
    return {
        "batch_id": batch_id,
        "test_id": meta.get("test_id", "") if "email b" in sections else "",
        "variant": variant,
        "lead_id": lead.get("lead_id", ""),
        "email": bare_address(lead.get("email")),
        "first_name": _first_name(lead.get("contact_name")),
        "company": lead.get("company", ""),
        "subject": meta.get("subject", ""),
        "body": "\n\n".join(lines) + "\n\n" + footer(offer),
        "followup_1": follow_ups[0] if follow_ups else "",
        "followup_2": follow_ups[1] if len(follow_ups) > 1 else "",
        "ad_url": ad_url if ad_url.startswith(("https://", "http://")) else "",
    }


def _draft_problem(lead: Lead, drafts: Dict[str, str], ads_by_id: Optional[Dict[str, Dict[str, Any]]],
                   offer_text: Optional[str], offer: Dict[str, str]) -> Optional[str]:
    """Why this lead's draft cannot be sent, or None."""
    draft_text = drafts.get(lead.get("lead_id", ""))
    if draft_text is None:
        return "no draft"
    problem = _approval_problem(draft_text, lead)
    if problem:
        return problem
    draft_ad = parse_front_matter(draft_text)[0].get("ad_id", "").strip()
    if (lead.get("ad_id") or "").strip() and draft_ad != lead["ad_id"].strip():
        return "draft quotes a different ad than the lead file names"
    errors = _lint_errors(draft_text, ads_by_id, offer_text, offer)
    return "draft fails lint: " + ", ".join(errors) if errors else None


def build_rows(leads: List[Lead], drafts: Dict[str, str], offer: Dict[str, str], suppression: Suppression,
               contacted: Contacted, ads_by_id: Optional[Dict[str, Dict[str, Any]]], offer_text: Optional[str],
               size: int = DEFAULT_BATCH_SIZE, batch_id: str = "", allow_large: bool = False,
               ) -> Tuple[List[Row], List[Tuple[str, str]]]:
    """Return (send-sheet rows, [(lead_id, why it was left out)])."""
    if size < 1 or (size > MAX_BATCH_SIZE and not allow_large):
        raise ValueError("batch size must be 1-%d (the guide tests 20-30 at a time)" % MAX_BATCH_SIZE)
    if batch_id and not valid_id(batch_id):
        raise ValueError("batch id may only hold letters, digits, '.', '_' and '-'")
    ready: List[Tuple[Lead, str]] = []
    skipped: List[Tuple[str, str]] = []
    emails_in_batch: Set[str] = set()
    domains_in_batch: Set[str] = set()
    for lead in sorted(leads, key=lambda item: item.get("lead_id", "")):
        lead_id = lead.get("lead_id", "")
        email = bare_address(lead.get("email"))
        company_domains = {d for d in (domain_of(email), domain_of(lead.get("domain"))) if d} - FREE_MAIL
        reason = None if valid_id(lead_id) else "lead_id is not a simple id (letters, digits, '.', '_', '-')"
        reason = reason or eligibility(lead, offer, suppression, contacted)
        reason = reason or _draft_problem(lead, drafts, ads_by_id, offer_text, offer)
        if reason is None and email in emails_in_batch:
            reason = "this address is already in the batch"
        if reason is None and any(domain_matches(d, domains_in_batch) for d in company_domains):
            reason = "another contact at this company is already in the batch"
        if reason is None and len(ready) >= size:
            reason = "held for the next batch"
        if reason is not None:
            skipped.append((lead_id, reason))
            continue
        ready.append((lead, drafts[lead_id]))
        emails_in_batch.add(email)
        domains_in_batch |= company_domains
    two_versions = [lead["lead_id"] for lead, text in ready if "email b" in _draft_parts(text)[1]]
    variants = assign_variants(two_versions)
    rows = [_sheet_row(lead, text, variants.get(lead["lead_id"], "A"), offer, batch_id) for lead, text in ready]
    return rows, skipped


# ---------------------------------------------------------------- log

def _event(row: Dict[str, str]) -> str:
    return (row.get("event") or "").strip().lower()


def read_log(path: PathLike) -> List[Dict[str, str]]:
    return read_csv(path, required=LOG_REQUIRED)


def mark_sent(rows: List[Row], log_path: PathLike, day: str) -> int:
    """Record the rows of a send sheet as sent on `day`. A lead already logged as sent is not logged twice."""
    date.fromisoformat(day)
    already = {row.get("lead_id") for row in read_log(log_path) if _event(row) == "sent"}
    fresh = [dict(row, date=day, event="sent", note="") for row in rows if row.get("lead_id") not in already]
    append_csv(log_path, LOG_FIELDS, fresh)
    return len(fresh)


def record_event(log_path: PathLike, suppression_path: PathLike, lead_id: str, email: str, event: str,
                 day: str, batch_id: str = "", test_id: str = "", variant: str = "", note: str = "") -> None:
    """Log a reply, positive reply, opt-out or bounce. Opt-outs and bounces are suppressed first, for good."""
    if event not in EVENTS:
        raise ValueError("event must be one of: %s" % ", ".join(EVENTS))
    date.fromisoformat(day)
    address = normalize_address(email)
    if event in SUPPRESSING_EVENTS:
        if not address:
            raise ValueError("no valid email address to suppress for %s" % lead_id)
        add_suppression(suppression_path, address, event, day)
    append_csv(log_path, LOG_FIELDS, [{"date": day, "batch_id": batch_id, "test_id": test_id, "variant": variant,
                                       "lead_id": lead_id, "email": address, "event": event, "note": note}])


# ---------------------------------------------------------------- results

def wilson(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """95% range for a rate. Honest about how little a small batch tells you."""
    if total == 0:
        return (0.0, 0.0)
    rate = successes / total
    centre = rate + z * z / (2 * total)
    spread = z * sqrt(rate * (1 - rate) / total + z * z / (4 * total * total))
    scale = 1 + z * z / total
    return (max(0.0, (centre - spread) / scale), min(1.0, (centre + spread) / scale))


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p-value for the table [[a, b], [c, d]]."""
    row_one, column_one, total = a + b, a + c, a + b + c + d
    if total == 0:
        return 1.0

    def probability(x: int) -> float:
        return comb(column_one, x) * comb(total - column_one, row_one - x) / comb(total, row_one)

    observed = probability(a)
    low, high = max(0, row_one - (total - column_one)), min(row_one, column_one)
    return min(1.0, sum(p for p in (probability(x) for x in range(low, high + 1)) if p <= observed * (1 + 1e-7)))


def _sent_as(rows: List[Dict[str, str]]) -> Dict[str, Tuple[str, str]]:
    """lead_id -> (test_id, version) from each lead's first 'sent' row."""
    sent: Dict[str, Tuple[str, str]] = {}
    for row in rows:
        if _event(row) == "sent":
            sent.setdefault(row.get("lead_id", ""), ((row.get("test_id") or "").strip(),
                                                     (row.get("variant") or "").strip() or "A"))
    return sent


def stats(rows: List[Dict[str, str]], test_id: Optional[str] = None) -> Dict[str, Any]:
    """Per version of one test: distinct leads sent, replied, positive, opted out, bounced.

    Every event is credited to the version its lead was sent as. Events for leads that were never
    sent are ignored. Sends that were not part of a test are counted apart, never mixed into a version.
    """
    sent = _sent_as(rows)
    tests = sorted({test for test, _ in sent.values() if test})
    if test_id is None:
        if len(tests) > 1:
            raise ValueError("the log holds several tests (%s): pass --test-id" % ", ".join(tests))
        test_id = tests[0] if tests else ""
    buckets: Dict[str, Dict[str, Set[str]]] = {}
    for row in rows:
        lead_id, event = row.get("lead_id", ""), _event(row)
        if event not in EVENTS or lead_id not in sent or sent[lead_id][0] != test_id:
            continue
        buckets.setdefault(sent[lead_id][1], {name: set() for name in EVENTS})[event].add(lead_id)
    variants: Dict[str, Dict[str, Any]] = {}
    for variant in sorted(buckets):
        bucket = buckets[variant]
        total = len(bucket["sent"])
        replies = len(bucket["reply"] | bucket["positive"])
        variants[variant] = {
            "sent": total, "replies": replies, "positive": len(bucket["positive"]),
            "optouts": len(bucket["optout"]), "bounces": len(bucket["bounce"]),
            "reply_rate": replies / total if total else 0.0, "reply_range": list(wilson(replies, total)),
        }
    untested = sum(1 for test, _ in sent.values() if not test) if test_id else 0
    return {"test_id": test_id or None, "tests_in_log": tests, "untested_sends": untested, "variants": variants}


def _describe(name: str, data: Dict[str, Any]) -> str:
    low, high = data["reply_range"]
    return "%s: %d replies from %d sends (%.1f%%, likely range %.1f%%-%.1f%%)" % (
        name, data["replies"], data["sent"], 100 * data["reply_rate"], 100 * low, 100 * high)


def verdict(result: Dict[str, Any], min_sends: int = MIN_SENDS_PER_VERSION) -> Dict[str, Any]:
    """Say what the numbers support and nothing more."""
    variants = {name: data for name, data in result["variants"].items() if data["sent"] > 0}
    if not variants:
        return {"status": "no_data", "message": "No sends logged yet.", "alarms": []}
    alarms = ["bounce rate %.0f%% on version %s: stop sending and re-verify the addresses"
              % (100 * data["bounces"] / data["sent"], name)
              for name, data in variants.items()
              if data["sent"] >= BOUNCE_ALARM_MIN_SENDS and data["bounces"] / data["sent"] > BOUNCE_ALARM_RATE]
    summary = "; ".join(_describe(name, data) for name, data in variants.items())
    if len(variants) == 1:
        return {"status": "single", "alarms": alarms,
                "message": summary + ". One version only, so there is nothing to compare yet."}
    first, second = sorted(variants, key=lambda name: -variants[name]["sent"])[:2]
    one, two = variants[first], variants[second]
    if min(one["sent"], two["sent"]) < min_sends:
        return {"status": "too_early", "alarms": alarms,
                "message": "%s. Too early to call: each version needs at least %d sends. At this size a gap of "
                           "one or two replies is noise. Keep both running." % (summary, min_sends)}
    p_value = fisher_two_sided(one["replies"], one["sent"] - one["replies"],
                               two["replies"], two["sent"] - two["replies"])
    if p_value < LEADER_P_VALUE:
        winner = first if one["reply_rate"] > two["reply_rate"] else second
        return {"status": "leader", "winner": winner, "p_value": p_value, "alarms": alarms,
                "message": "%s. Version %s leads (p=%.3f). Use it as the default, and check that it still leads "
                           "after the next batch: looking after every batch makes a false winner more likely."
                           % (summary, winner, p_value)}
    return {"status": "no_difference", "p_value": p_value, "alarms": alarms,
            "message": "%s. No clear difference (p=%.2f). Keep the current default and test a bigger change."
                       % (summary, p_value)}


# ---------------------------------------------------------------- command line

def _read_leads(folder: Path) -> Tuple[List[Lead], List[Tuple[str, str]]]:
    """(leads, [(file name, why it could not be used)])."""
    leads: List[Lead] = []
    unreadable: List[Tuple[str, str]] = []
    for path in sorted(folder.glob("*.md")):
        try:
            meta = parse_front_matter(path.read_text(encoding="utf-8-sig"))[0]
        except ValueError as err:
            unreadable.append((path.name, "lead file could not be read: %s" % err))
            continue
        if meta.get("lead_id"):
            leads.append(meta)
        else:
            unreadable.append((path.name, "lead file has no front matter or no lead_id"))
    return leads, unreadable


def _read_drafts(folder: Path) -> Dict[str, Tuple[Path, str]]:
    """lead_id -> (path, text). Two drafts for one lead is an error."""
    drafts: Dict[str, Tuple[Path, str]] = {}
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        lead_id = parse_front_matter(text)[0].get("lead_id") or path.stem
        if lead_id in drafts:
            raise ValueError("two drafts for %s: %s and %s" % (lead_id, drafts[lead_id][0].name, path.name))
        drafts[lead_id] = (path, text)
    return drafts


def _require(path: str, what: str) -> None:
    if not Path(path).exists():
        raise ValueError("%s not found: %s. For a new workspace run `batch.py init` first; "
                         "otherwise check the path." % (what, path))


def _cmd_init(args: argparse.Namespace) -> int:
    append_csv(args.suppression, SUPPRESSION_FIELDS, [])
    append_csv(args.log, LOG_FIELDS, [])
    out(json.dumps({"ready": [args.suppression, args.log]}))
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    run = Path(args.run)
    leads = {lead["lead_id"]: lead for lead in _read_leads(run / "leads")[0]}
    drafts = _read_drafts(run / "drafts")
    wanted = sorted(drafts) if args.all else (args.lead_id or [])
    approved: List[str] = []
    problems: List[Dict[str, str]] = []
    for lead_id in wanted:
        if lead_id not in drafts or lead_id not in leads:
            problems.append({"lead_id": lead_id, "why": "no draft or no lead file with this id"})
            continue
        path, text = drafts[lead_id]
        atomic_write(path, approve_draft(text, leads[lead_id]))
        approved.append(lead_id)
    out(json.dumps({"approved": approved, "not_approved": problems}, indent=2))
    return 0 if approved and not problems else 1


def _cmd_build(args: argparse.Namespace) -> int:
    run = Path(args.run)
    offer_text = Path(args.offer).read_text(encoding="utf-8-sig")
    offer = parse_front_matter(offer_text)[0]
    errors, warnings = validate_offer(offer)
    if errors:
        out(json.dumps({"built": False, "errors": errors, "warnings": warnings}, indent=2))
        return 1
    _require(args.suppression, "suppression list")
    _require(args.log, "send log")
    suppression = load_suppression(args.suppression)
    contacted = contacted_from_log(read_log(args.log))
    leads, unreadable = _read_leads(run / "leads")
    drafts = {lead_id: text for lead_id, (_, text) in _read_drafts(run / "drafts").items()}
    ads_by_id = {str(ad.get("id")): ad for ad in read_jsonl(run / "ads.jsonl")}
    batch_id = args.batch_id or "B-%s-%s" % (date.today().strftime("%y%m%d"),
                                             re.sub(r"[^A-Za-z0-9._-]+", "-", run.name)[:40].strip("-."))
    rows, skipped = build_rows(leads, drafts, offer, suppression, contacted, ads_by_id, offer_text,
                               size=args.size, batch_id=batch_id, allow_large=args.allow_large)
    sheet = run / ("send-sheet-%s.csv" % batch_id)
    if rows:
        write_csv(sheet, SHEET_FIELDS, rows)
    nameless = [row["lead_id"] for row in rows if not row["first_name"]]
    out(json.dumps({"built": bool(rows), "sheet": str(sheet.resolve()) if rows else None, "batch_id": batch_id,
                    "rows": len(rows), "versions": {v: sum(1 for r in rows if r["variant"] == v) for v in "AB"},
                    "no_named_contact": nameless,
                    "left_out": [{"lead_id": name, "why": why} for name, why in unreadable + skipped],
                    "suppressed_loaded": {"emails": len(suppression.emails), "domains": len(suppression.domains)},
                    "already_contacted": len(contacted.emails), "warnings": warnings}, indent=2))
    return 0 if rows else 1


def _cmd_mark_sent(args: argparse.Namespace) -> int:
    rows = read_csv(args.sheet, required=("lead_id", "email"))
    logged = mark_sent(rows, args.log, args.date or date.today().isoformat())
    now_suppressed: List[str] = []
    if args.suppression:
        suppression = load_suppression(args.suppression)
        now_suppressed = [row["email"] for row in rows if row["email"] in suppression.emails
                          or domain_matches(domain_of(row["email"]), suppression.domains)]
    out(json.dumps({"logged_sent": logged, "already_logged": len(rows) - logged, "log": args.log,
                    "on_suppression_list": now_suppressed,
                    "note": "Addresses on the suppression list were suppressed after this sheet was built. "
                            "Do not send them follow-ups." if now_suppressed else ""}))
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    sent = next((row for row in read_log(args.log)
                 if row.get("lead_id") == args.lead_id and _event(row) == "sent"), {})
    day = args.date or date.today().isoformat()
    record_event(args.log, args.suppression, lead_id=args.lead_id, email=args.email or sent.get("email", ""),
                 event=args.event, day=day, batch_id=sent.get("batch_id", ""), test_id=sent.get("test_id", ""),
                 variant=sent.get("variant", ""), note=args.note or "")
    suppressing = args.event in SUPPRESSING_EVENTS
    if suppressing and args.email and sent.get("email") and normalize_address(args.email) != sent["email"]:
        add_suppression(args.suppression, sent["email"], args.event, day)  # the address that was actually emailed
    out(json.dumps({"recorded": args.event, "lead_id": args.lead_id, "suppressed": suppressing}))
    return 0


def _cmd_suppress(args: argparse.Namespace) -> int:
    stored = add_suppression(args.suppression, args.value, args.reason, date.today().isoformat())
    out(json.dumps({"suppressed": stored, "reason": args.reason}))
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    result = stats(read_log(args.log), args.test_id)
    out(json.dumps({"stats": result, "verdict": verdict(result)}, indent=2))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create the suppression list and send log for a new workspace")
    init.add_argument("--suppression", required=True)
    init.add_argument("--log", required=True)
    init.set_defaults(run_command=_cmd_init)

    approve = commands.add_parser("approve", help="record that the user read and approved these drafts")
    approve.add_argument("--run", required=True)
    approve.add_argument("--lead-id", nargs="+", help="the drafts the user approved")
    approve.add_argument("--all", action="store_true", help="every draft in the run (only if the user saw them all)")
    approve.set_defaults(run_command=_cmd_approve)

    build = commands.add_parser("build", help="write a send sheet for the next batch")
    build.add_argument("--run", required=True, help="run folder holding leads/, drafts/ and ads.jsonl")
    build.add_argument("--offer", required=True)
    build.add_argument("--suppression", required=True)
    build.add_argument("--log", required=True)
    build.add_argument("--size", type=int, default=DEFAULT_BATCH_SIZE)
    build.add_argument("--batch-id")
    build.add_argument("--allow-large", action="store_true", help="allow more than %d in one batch" % MAX_BATCH_SIZE)
    build.set_defaults(run_command=_cmd_build)

    sent = commands.add_parser("mark-sent", help="log every row of a send sheet as sent")
    sent.add_argument("--sheet", required=True)
    sent.add_argument("--log", required=True)
    sent.add_argument("--suppression", help="also report addresses suppressed since the sheet was built")
    sent.add_argument("--date", help="YYYY-MM-DD, default today")
    sent.set_defaults(run_command=_cmd_mark_sent)

    record = commands.add_parser("record", help="log a reply, positive reply, opt-out or bounce")
    record.add_argument("--log", required=True)
    record.add_argument("--suppression", required=True)
    record.add_argument("--lead-id", required=True)
    record.add_argument("--event", required=True, choices=[e for e in EVENTS if e != "sent"])
    record.add_argument("--email", help="only needed when the lead has no 'sent' row in the log")
    record.add_argument("--date", help="YYYY-MM-DD, default today")
    record.add_argument("--note")
    record.set_defaults(run_command=_cmd_record)

    suppress = commands.add_parser("suppress", help="never contact this email or domain")
    suppress.add_argument("--suppression", required=True)
    suppress.add_argument("--value", required=True, help="an email address or a domain")
    suppress.add_argument("--reason", required=True, help="e.g. competitor, customer, asked-to-stop")
    suppress.set_defaults(run_command=_cmd_suppress)

    result = commands.add_parser("stats", help="reply rates per version and what they support")
    result.add_argument("--log", required=True)
    result.add_argument("--test-id")
    result.set_defaults(run_command=_cmd_stats)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.run_command(args)
    except (OSError, ValueError) as err:
        sys.stderr.write("error: %s\n" % err)
        return 1


if __name__ == "__main__":
    sys.exit(main())
