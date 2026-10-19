---
name: dain-p2-asset-pack
description: When the Canon changes, render a bureau-ready asset pack (50/150/300-word bios, talk descriptions, one-sheet, clip list) in each partner bureau's format, with a cover note listing what changed. A human sends it. Use on any Blueprint approval for a speaker with bureaus. Not a bureau API sync; none exists.
component: P2
department: pipeline
archetype: builder
owner: BS
---

# P2 · Bureau & Bio Asset Pack

## Purpose
- **Role:** keeps every bureau selling this year's version of the speaker.
- **Goal:** bureau pack refreshed within 14 days of a Canon change.
- **For:** the speaker's partner bureaus, via the speaker or specialist.
- **Success:** three pilot bureaus accept a pack without asking for reformatting; no bureau holds a pack older than 90 days; public listing checked monthly ("listing current: yes/no").

## 1 · Name and trigger
`pack.render { speaker_id }`, fired automatically after `blueprint.confirm`; `pack.sent` records each human send.

## 2 · When to use
After any approved change to positioning, angles, confirmed claims or clips. **Not** for sharing fees or private client data.

## 3 · Inputs (knowledge)
Canon Blueprint (current and previous version), speaker profile (clips, bureau ids), shared Bureau Profiles (`brain/canon/bureau-profiles.md`; Canon `bureau/<id>`).

## 4 · Steps (all code)
1. Render bios, `talks.md` and `one_sheet.html` from the Canon. Confirmed claims only, reputation proof (testimonials, rebookings, clients) included.
2. Diff the current and previous Blueprint into a plain "what's new" list.
3. For each bureau: pick the files its profile asks for, fill the cover-note template, check it for fees.
4. Queue the pack for approval; the speaker or specialist sends it and records `pack.sent`.

## 5 · Handoffs
- **To B3:** cover notes for approval.
- **To the groundskeeper:** `p2.sent` records, for the 90-day staleness check.

## Rules
- Every sentence traces to a Canon record; no free text.
- Check each speaker's bureau agreements for exclusivity or direct-contact clauses before the first send (specialist, at onboarding).

## Why this is code, not an LLM node
The spec drafts the cover note with a prompt. A note listing what changed fails R1's judgement test, so it's a template. That keeps v1 at five LLM components.

## Tools
None external. Print `one_sheet.html` to PDF (headless Chromium) for bureaus that want PDFs.

## Test before real speakers
Send packs to three friendly bureaus; pass if none asks for reformatting. `tests/p2.test.ts` covers rendering and the change list.

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Render pack and cover notes on Canon change | fully-autonomous | no |
| Send pack to a bureau | human-led | yes |
