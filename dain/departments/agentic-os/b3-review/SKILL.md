---
name: dain-b3-review
description: Two-stage human review (booking specialist, then speaker) for drafts, replies and packs, showing claims used, B2 reasons and evidence; times the edit as active screen time; issues the approval token the Action Gate needs. Use for every item that needs a human before it moves. Not an agent; no model is called.
component: B3
department: agentic-os
archetype: gate
owner: BS
---

# B3 · Review module

## Purpose
- **Role:** the named human on every external action, and the instrument that measures the 15-minute promise.
- **Goal:** nothing reaches a client or LinkedIn without a named human; edit time measured, not assumed.
- **Success:** median and p90 speaker edit time; specialist minutes per speaker per week; SLA breaches (specialist 24 h, speaker 72 h).

## 1 · Name and trigger
`review.open` · `review.edit` · `review.approve` (plus request-change and reject with reason codes).

## 2 · When to use
Content: specialist (commercial relevance) → speaker (final say; only the speaker can approve publishing in their name). Replies and packs: specialist.

## 3 · Inputs
Item text, claims used, B2 reasons (labelled "Provisional score" while the rubric is provisional; never a total), evidence links, P1 guard hits.

## 4 · Steps
1. Reviewer opens the item; the screen reports activity (keys, scroll, focus).
2. Edits replace the text, clear guard blocks and void any token.
3. Approve: closes the session (edit time = active time, idle gaps over 2 min excluded; "copied out" logged), moves the state, and on the final approval issues the token.
4. Request change → back to A2 (specialist) or to the specialist (speaker). Reject → closed with a reason code.

## 5 · Handoffs
Token → C0 → Action Gate. Data for L1: edit time, reject reasons by criterion, draft-vs-published diff, specialist-vs-B2 verdicts.

## Capacity (R8)
`cap = floor(specialist minutes per week × 0.8 ÷ measured specialist minutes per speaker per week)`, recomputed weekly. Risk-based review after a speaker's first 4 weeks only if the client approves: B2-flagged items plus a random 10%, back to full review if the sample fails more than 5%. Speaker approval stays mandatory.

## Not built here
The review **screen** (web UI) is product surface still to build. This module is the service and rules behind it.

## Test before real speakers
The specialist and two team members review 20 test drafts and note anything confusing. `tests/review.test.ts` covers timer, token and role rules.

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Specialist then speaker review, edit timer, token issue | human-led | no |
