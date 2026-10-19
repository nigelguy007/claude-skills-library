---
name: dain-groundskeeper
description: Nightly maintenance of the brain and the pipeline. Escalates items stuck 7+ days in a human-wait state, pauses speakers who have gone quiet, flags Blueprints due a re-interview, unconfirmed claims, angles without fresh evidence and stale bureau packs, and computes the weekly onboarding cap. Use on the nightly schedule. Never publishes, sends or edits the Canon.
component: GK
department: agentic-os
archetype: groundskeeper
owner: TL
---

# Groundskeeper

## Purpose
- **Role:** the team that maintains the team, so the machine doesn't rot.
- **Goal:** no orphan items, no stale facts, no capacity surprises.
- **Success:** stuck-item count; share of angles with evidence under 90 days; bureaus with a pack older than 90 days.

## 1 · Name and trigger
`nightly` at 02:00. The onboarding cap is computed weekly from R5 data.

## 2 · When to use
On schedule. Safe to run any time: everything it does is a flag, an escalation or a pause.

## 3 · Inputs
State tables, Canon (`blueprint`, `angle_evidence`, `rubric`), Chronicle (`p2.sent`), event log.

## 4 · Steps
1. Items waiting on a human for 7+ days → ESCALATED; a speaker who has left their own review queue → PAUSED.
2. Blueprints older than 6 months → re-interview due.
3. Claims still `needs_evidence` → chase list.
4. Angles without Canon evidence under 90 days → flag for B1 and the specialist.
5. Bureau packs not sent in 90 days → flag.
6. Rubric still provisional → reminder on the dashboard.
7. Report written to the Chronicle (`groundskeeper.report`).

## 5 · Handoffs
To the specialist (escalations and chase lists) and the dashboard.

## Not built here
Backups and link checks belong to the database and hosting platform (scheduled Postgres backups to private storage), not to application code.

## Test
`tests/groundskeeper.test.ts`: stuck items escalate at 7 days, not before; quiet speaker paused; cap formula.

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Nightly sweep: stuck items, stale facts, stale packs | fully-autonomous | no |
| Weekly onboarding cap (R8) | fully-autonomous | no |
