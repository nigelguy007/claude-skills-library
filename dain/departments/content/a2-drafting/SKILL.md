---
name: dain-a2-drafting
description: Plan a speaker's week and draft three LinkedIn posts from their approved Blueprint, each scored by B2 in a fresh context and revised up to 3 times before review. Use on the Monday weekly-content trigger or when a speaker asks for a talk description or article outline. Not for choosing new angles (B1) or publishing (Action Gate).
component: A2
department: content
archetype: builder
owner: PL
---

# A2 · Content & Drafting

## Purpose
- **Role:** the speaker's ghostwriter, who only writes what the Canon can back.
- **Goal:** three posts a week the speaker approves in under 15 minutes.
- **For:** the speaker (who approves) and the event organiser (who reads).
- **Success:** median speaker edit time < 15 min, keep-rate ≥ 66%, B2 first-pass rate ≥ 60%, zero published unconfirmed claims.

## 1 · Name and trigger
`content.weekly { speaker_id, week }`: Monday 07:00 for every ACTIVE speaker.

## 2 · When to use
- Weekly content for a speaker with an approved Blueprint.
- **Not** when the speaker is PAUSED or has no approved Blueprint (the conductor skips them).

## 3 · Inputs (knowledge)
Canon: Blueprint (angles, confirmed claims, voice guide), rubric, approved voice samples (the speaker's own published posts). Chronicle: the last six published posts.

## 4 · Steps
1. **Plan (code):** three slots, least-recently-used angles first, formats rotated (story, proof, contrarian, lesson), no (angle, format) pair from the last six posts, at least one proof post.
2. **Draft (parallel):** `draft.prompt.md` for each slot. Only confirmed claims are passed in.
3. **Claim check (code):** any claim id not in the Canon, or not `speaker_confirmed`, blocks the draft and counts as a pass.
4. **Score (B2, fresh context):** pass → review queue; revise → fix the single lowest criterion and resend.
5. **Stop:** pass, or 3 passes → escalate to the specialist with every version and score.
6. **Learn:** after publishing, the speaker's final text is saved to the Canon as a voice sample.

## 5 · Handoffs
- **To B3:** passing drafts, with claims used and B2's reasons, into the specialist queue.
- **To the specialist:** escalated items with all versions.
- **To the Action Gate:** nothing directly. Only a speaker approval token publishes.

## Rules
- Write as the speaker, using their phrases; never anything on their "dont" list.
- No claim unless `speaker_confirmed`; never stronger than the claim.
- At most 1,300 characters. One hook, one proof or story, one organiser-recognisable takeaway.
- When revising, change only what B2 asked for.

## Examples
**Blocked (contract working):** a strong proof post using C4 while C4 is `needs_evidence` → `self_flag: "uses unconfirmed claim C4"`, sent back without scoring.

**Revise:** B2 scores outcome clarity 2 on "those two problems usually have the same cause" → request "Name the three changes in one line each so a planner can quote them."

## Tools
None at draft time. LinkedIn Posts API (`w_member_social`) is reached only through the Action Gate after the speaker approves.

## Test before real speakers
20 drafts for a mock speaker, rated blind by the team ("would this speaker post this?"). Most pass with light edits; none uses an unconfirmed claim. `tests/content-loop.test.ts` covers the loop rules.

- [ ] Correct: zero unconfirmed claims reach review
- [ ] Consistent: voice compared with this speaker's samples, not a global style
- [ ] Uses knowledge: angle and claims from the Canon only
- [ ] Uses tools: never publishes directly
- [ ] Edge cases: angle with no confirmed claims; repeated hooks; B2 never passes

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Weekly plan and 3 drafts into review | human-assisted | no |
