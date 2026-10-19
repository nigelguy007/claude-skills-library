---
name: dain-b2-scoring
description: Score a draft post against the booker rubric in a context that has never seen the drafting conversation, quote the draft for every reason, and return one revision request. Use as the checker inside A2's loop. Not a booking probability, and never shown to speakers as a number.
component: B2
department: bookability
archetype: analyst
owner: BS
---

# B2 · Bookability Scoring

## Purpose
- **Role:** the independent checker that gives A2's loop something it can fail.
- **Goal:** reviewers only see work that has already passed on the criteria bookers care about.
- **For:** A2 (feedback), the specialist (reasons beside the draft).
- **Success:** B2–specialist agreement ≥ 80% (within 1 point per criterion); first-pass rate ≥ 60%; overrides concentrated on no single criterion.

## 1 · Name and trigger
Called by the A2 loop for every draft that passes the claim check.

## 2 · When to use
Every draft, every pass. **Not** for judging commercial suitability (the specialist owns that) or predicting bookings.

## 3 · Inputs (knowledge)
Only: draft text, the angle, the claims used, the rubric (Canon `rubric/current`), five voice samples. Never A2's prompt, reasoning or earlier drafts.

## 4 · Steps
1. `score.prompt.md` scores six criteria 1–5 with a quoted reason each.
2. Code rejects any reason that doesn't quote the draft word for word (one retry, then escalate).
3. Code computes the verdict: pass if every criterion ≥ 3 and mean ≥ 3.8. The model's own verdict is ignored.
4. Code stamps the rubric version and label (`provisional` until R2 calibration passes).

## 5 · Handoffs
- **pass →** B3 specialist queue, reasons attached.
- **revise →** back to A2 with the one change for the lowest criterion.

## Rules (anti-Goodhart)
- Speakers see reasons, never the total.
- The review screen says "Provisional score" whenever `label = provisional`.
- Rubric changes are versioned in the Canon, by a human only.
- 10% of passing drafts go to blind specialist review.

## Rubric lifecycle
| Version | When | Rule | Label |
|---|---|---|---|
| v0 | Day 1 | booker guidance + specialist judgement (`brain/canon/rubric-v0.md`) | provisional |
| v1 | Day 12 | criterion kept only if ≥ 4 of 12 bookers raised it | provisional |
| calibration | Day 18 | humans agree (κ ≥ 0.6) and B2 within 1 point on ≥ 80% | calibrated if both pass |
| v1.x | every 300 reviewed drafts | L1 proposes, a human approves | — |

## Examples
`{ outcome_clarity: 2, reason: "\"those two problems usually have the same cause\" names no action an attendee could take", revision_request: "Name the three changes in one line each so a planner can quote them as session outcomes." }`

## Tools
None. Calibration runs in `evals/calibration.ts` (Cohen's κ, within-1 agreement, override share by criterion).

## Test before real speakers
The specialist and B2 each score the same 30 drafts. Where they disagree, reword that criterion and re-run. `tests/b2.test.ts` covers the quote rule and the verdict.

- [ ] Correct: verdict from code, not the model
- [ ] Consistent: same draft, same rubric → scores within 1 point across runs
- [ ] Uses knowledge: rubric from the Canon, with its version
- [ ] Edge cases: model returns a reason without a quote; all criteria 3 (mean 3.0 fails)

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Score each draft in a fresh context | fully-autonomous | no |
| Change the rubric | human-led | no |
