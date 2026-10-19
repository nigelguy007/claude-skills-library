---
name: dain-c0-conductor
description: The one entry point to Dain. Accepts a fixed set of commands, validates them, runs the matching workflow through explicit state machines, enforces per-call budgets and the 3-pass revise limit, and pauses at every human approval. Use for every trigger, schedule and human action. It never reads free text to decide where work goes.
component: C0
department: agentic-os
archetype: conductor
owner: TL
---

# C0 · Conductor

## Purpose
- **Role:** the map's conductor ("Jarvis"), built as code. You talk to one thing; it hands the job to the right department.
- **Goal:** every item moves through explicit states; nothing external happens without a token.
- **Success:** zero external actions without a valid token; stuck-item count near zero; p95 trigger-to-review-queue time tracked; chaos test passed.

## Why not an LLM router (F9)
The routes are known in advance: interview → Blueprint → weekly cycle → enquiry. An LLM router adds cost, latency and non-determinism to the one part that must be predictable and auditable. A natural-language front end can be added later, but only to *choose one of these commands and show it to a human* before it runs.

## 1 · Name and trigger
`Conductor.dispatch(command, payload)`. Commands (`src/conductor/commands.ts`):
`speaker.onboard` · `interview.transcript` · `interview.followup` · `blueprint.confirm` · `content.weekly` · `review.open` · `review.edit` · `review.approve` · `enquiry.capture` · `radar.weekly` · `radar.promote` · `pack.render` · `pack.sent` · `sweep.answer` · `nightly`

Schedules: content Monday 07:00 · radar Sunday 06:00 · groundskeeper nightly 02:00 · missed-enquiry sweep Friday 16:00.

## 2 · When to use
Always. Nothing calls an agent directly.

## 3 · Inputs (knowledge)
The Canon and Chronicle (`src/brain/store.ts`), the component register (`src/register.ts`), the state tables (`src/state.ts`).

## 4 · Steps
1. Validate the payload against the command's schema; refuse unknown commands.
2. Run the command's workflow with memoised steps (a restart replays without re-running).
3. Pause on human events (transcript, follow-up answers, Blueprint confirmation, approvals).
4. Every node call carries a budget (tokens, £, seconds). Breach → ESCALATED, never a silent retry.
5. Write the event log from the first call.

## State machines
```
Speaker:     ONBOARDING → INTERVIEW_BOOKED → INTERVIEWED → BLUEPRINT_DRAFT → BLUEPRINT_APPROVED* → ACTIVE ⇄ PAUSED
ContentItem: PLANNED → DRAFTED → SCORED → (REVISE ≤ 3) → SPECIALIST_REVIEW* → SPEAKER_REVIEW* → APPROVED → PUBLISHED | REJECTED | ESCALATED
Enquiry:     NEW → EXTRACTED → QUALIFIED → REPLY_DRAFTED → APPROVED* → SENT → NEGOTIATING → WON | LOST | REFERRED
AssetPack:   RENDERED → APPROVED* → SENT
(* = needs a named human approval)
```

## 5 · Handoffs
Each workflow's handoffs are in its department's SOP. C0 itself hands to the Action Gate for every external write.

## Deployment note
`src/conductor/runner.ts` gives the semantics R9 requires (memoised steps, pause for days on an event, resume) so the flows can be tested now. Choose the production engine by Day 2: Inngest (`step.run`, `step.waitForEvent`) for a small TypeScript team; Temporal at scale; n8n only with prompts and schemas kept in this repo.

## Test before real speakers
Each flow end to end with a test speaker; then the R9 chaos test: kill the worker mid-publish and mid-approval 20 times, with zero duplicate publishes and zero lost approvals. `tests/conductor.test.ts` and `tests/gate.test.ts`.

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Route commands, run state machines, enforce budgets | fully-autonomous | no |
