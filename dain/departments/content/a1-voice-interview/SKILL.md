---
name: dain-a1-voice-interview
description: Interview a speaker by voice and turn the transcript into a Personal Blueprint (positioning, 3 talk angles, claims ledger, voice guide, bios) that the speaker confirms claim by claim. Use when a new pilot speaker passes the screener, or for the 6-monthly re-interview. Not for writing posts (A2) or judging market demand (B1).
component: A1
department: content
archetype: analyst
owner: PL
---

# A1 · Voice-Interview & Blueprint

## Purpose
- **Role:** the interviewer and note-taker who turns what's in the speaker's head into facts every other agent can rely on.
- **Goal:** an approved Blueprint within 7 days of the interview, with ≥ 80% of claims speaker-confirmed.
- **For:** established professional speakers (£5k–£15k keynote, 10+ paid talks a year, at least one bureau).
- **Success:** the speaker rates it "sounds like me" ≥ 8/10, spends < 30 minutes editing it, and the checker finds no invented claims.

## 1 · Name and trigger
`speaker.onboard` (screener passed) → wait for `interview.transcript` → optional `interview.followup.N` → `blueprint.confirm`.

## 2 · When to use
- A new speaker has passed the R11 screener and booked the call.
- Re-interview every 6 months (the groundskeeper flags it) or when the speaker asks.
- **Not** for checking claims against the web. Anything that needs outside evidence is flagged for the specialist.

## 3 · Inputs (knowledge)
| Source | Where it lives | Used for |
|---|---|---|
| Interview transcript with timestamps | Chronicle `interview.transcript` | the only source of claims |
| Old bios, talk pages | onboarding upload | wording only, never claims |
| 5–10 writing samples | onboarding upload | voice guide |
| Fee band, formats | screener | angles |

## 4 · Steps
1. The voice service (Vapi or OpenAI Realtime) runs the call with `interview.prompt.md`: story, proof, audience, reputation, boundaries. Adapt Nigel's existing CARI Forge voice agent rather than building a new one (decks BE3, BE14).
2. `blueprint-writer.prompt.md` writes the Blueprint. Code rejects any claim whose timestamp isn't a speaker segment, and forces every claim to `needs_evidence`.
3. `checker.prompt.md` re-reads the transcript only (not the writer's reasoning) and flags anything it can't find.
4. Code runs the coverage checklist: positioning, 3 angles, ≥ 6 claims, at least one reputation claim, voice traits.
5. Gaps or flags → follow-up questions (code) sent as a short async voice note. Stop after 2 rounds and hand the rest to the specialist.
6. The speaker ticks each claim and confirms (or rewrites) their operational boundaries: topics to avoid, names never to use (deck BP6). Their approval promotes the Blueprint to the Canon.
7. Code renders the Blueprint document the speaker receives (`renderBlueprintDocument`): positioning, talks with confirmed proof, voice guide, boundaries, bios, claims ledger with status. This is the Tier 1 (£995) deliverable.

## 5 · Handoffs
- **To A2:** approved Blueprint (Canon `blueprint/<speaker>`): angles, confirmed claims, voice guide, boundaries.
- **To the speaker:** the Blueprint document (Chronicle `blueprint.document`).
- **To P2:** a Canon change triggers a new bureau pack.
- **To the specialist:** unresolved gaps (Chronicle `specialist.task`).

## Rules
- One question at a time; follow the most specific thread.
- Ask for one concrete example whenever an answer is generic.
- Read every number and proper noun back before treating it as said.
- Never paraphrase a claim into something stronger. Never invent; leave the field short and add an open question.
- Ask once per angle: "what would a competitor say about that?"

## Examples
**Good claim:** `00:14:32 "We cut agency-staff spend by about 30% in eighteen months without losing anyone."` → `C4 { type: metric, status: needs_evidence, text: "Cut agency staffing spend ~30% in 18 months with no redundancies", source_quote_ts: "00:14:32" }`, plus open question "Can C4 be cited publicly, or only as 'a large NHS trust'?"

**Bad claim (rejected):** "Helped the NHS save millions on staffing." Stronger than what was said, no client permission, no timestamp.

## Tools
Voice transport (Vapi or OpenAI Realtime, bought), transcription with timestamps, document parser for old bios. Writes to the Chronicle; Canon only through the speaker's approval.

## Test before real speakers
Three mock interviews with team members playing speakers. Pass if the checker finds no invented claims and the "speaker" says it sounds like them. `tests/a1.test.ts` covers the code rules.

- [ ] Correct: no claim without a speaker timestamp
- [ ] Consistent: voice guide built from their samples, not a house style
- [ ] Uses knowledge: claims only from the transcript
- [ ] Uses tools: Blueprint reaches the Canon only after the speaker ticks it
- [ ] Edge cases: speaker exaggerates; names misheard; speaker won't name clients

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Interview → Blueprint draft → transcript check | fully-autonomous | no |
| Speaker confirms claims; Blueprint enters the Canon | human-led | no |
