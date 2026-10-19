---
name: dain-l1-learning
description: Post-launch, monthly. Compares what Dain predicted (B2 scores, P1 fit, B1 confidence) with what happened (approvals, edits, enquiries, wins) and proposes rubric and angle changes for a human to accept. Locked until 50 enquiries have known outcomes and 300 drafts have been reviewed. Calibration maths is built now; the node is not.
component: L1
department: agentic-os
archetype: analyst
owner: PL
---

# L1 · Outcome & Learning

## Purpose
- **Role:** closes the loop, so Dain gets better at booker relevance instead of just producing more.
- **Success:** rubric changes backed by outcome data with the sample size stated.

## 1 · Name and trigger
Monthly, once the entry criteria hold.

## 2 · When to use
Only with ≥ 50 enquiries with known outcomes and ≥ 300 reviewed drafts. Before that, any pattern it found would be noise.

## 3 · Inputs
Event log (`draft.scored`, `review.closed`, `enquiry.stage_changed`), B3 verdicts.

## 4 · Steps
1. Which rubric criteria disagree most with specialists? (`overrideShareByCriterion`)
2. Do humans agree with each other? (`cohensKappa` on pass/revise; below 0.6 means reword, not tune)
3. Does B2 agree with the human consensus? (`withinOneAgreement`, target ≥ 80%)
4. Which angles produced enquiries; which produced none in 90 days?
5. Which formats correlate with inbound enquiries, with the sample size stated?
6. Write proposals. A human accepts or rejects each; Canon changes stay human.

## 5 · Handoffs
Proposals to the product lead; accepted ones become a new rubric version in the Canon.

## Built now
`evals/calibration.ts` (κ, within-1 agreement, override share) runs the Day 18 calibration for B2 (R2).

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Monthly proposals for rubric and angle changes | human-led | no |
