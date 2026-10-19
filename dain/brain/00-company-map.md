# Company map

Dain wired as an AI company: one brain, departments, one SOP per workflow, one conductor. The register in `src/register.ts` is the source of truth; `npm run dain -- map` prints it.

```
YOU
 └─ C0 Conductor (code: fixed routes, state machines, budgets)
     ├─ Content       A1 Voice-Interview & Blueprint · A2 Content & Drafting
     ├─ Bookability   B2 Bookability Scoring · B1 Relevance Radar (+ inside-out mode)
     ├─ Pipeline      P1 Lead Capture · P2 Bureau Asset Pack · P3 Referral (manual v0)
     └─ Agentic OS    Action Gate + publishers · B3 Review · Groundskeeper · L1 Learning (later)

Every box reads the Canon and writes the Chronicle.
```

## Components, archetypes and autonomy

| ID | Component | Dept | Archetype | Type | LLM | Phase | Workflows → autonomy |
|---|---|---|---|---|---|---|---|
| C0 | Conductor | Agentic OS | conductor | code | – | Days 1–14 | routing → autonomous |
| AG | Action Gate + publishers | Agentic OS | publisher | code | – | Days 1–14 | publish, send → **human-assisted** (token) |
| B3 | Review module | Agentic OS | gate | UI + code | – | Days 1–14 | review → human-led (screen, email reply or form) |
| GK | Groundskeeper | Agentic OS | groundskeeper | code | – | Days 1–14 | sweeps, cap, 4 h review ceiling → autonomous |
| A1 | Voice-Interview & Blueprint | Content | analyst | agent | ✓ | Days 1–14 | draft → autonomous; claims + boundaries confirmed → human-led; Blueprint document → autonomous |
| A2 | Content & Drafting | Content | builder | loop | ✓ | Days 1–14 | drafts → human-assisted (blocked on unconfirmed claims or boundary breaches) |
| B2 | Bookability Scoring | Bookability | analyst | node | ✓ | Days 1–14 | scoring → autonomous; rubric → human-led |
| P1 | Lead Capture & Pipeline | Pipeline | analyst | node | ✓ | Days 1–14 | capture → autonomous; reply → assisted; fees/dates → human-led |
| B1 | Relevance Radar | Bookability | scout | agent | ✓ | Days 16–29 | collect → autonomous; promote → human-led |
| P2 | Bureau Asset Pack | Pipeline | builder | code | – | Days 16–29 | render → autonomous; send → human-led |
| P3 | Pass the Gig (manual) | Pipeline | builder | code | – | post-launch | human-led |
| L1 | Outcome & Learning | Agentic OS | analyst | node | ✓ | post-launch | proposals → human-led |

**The map's "first five agents", mapped:** Scout = B1 · Drafter = A2 · Publisher = Action Gate · Groundskeeper = GK · Conductor = C0.

## Where this differs from the generic map, and why

1. **The conductor is code, not an LLM "Jarvis".** Dain's routes are known in advance. An LLM router would make the most safety-critical component non-deterministic (spec F9). If a natural-language front door is wanted later, it may only *propose* one of C0's fixed commands for a human to confirm.
2. **Four departments, not six.** The spec contains no Finance or Personal work. Inventing agents for them would be the "pile of bots" the map warns against. Add a department when there's a repeating job to put in it.
3. **Publishing is never promoted to fully autonomous.** The map's "promote after ten in a row" rule can't apply to anything posted or sent in a speaker's name: speaker approval is the product promise. Risk-based *specialist* sampling after week 4 (R8) is the only relaxation, and only if the client approves it.
4. **A seventh archetype, "gate".** The map has no word for the human review step. In Dain it is the product, so it gets its own row (B3).
5. **P2's cover note is a template, not a prompt.** The spec drafts it with an LLM; it fails R1's judgement test. That keeps v1 at five LLM components (the spec's own v1 list omits P2's prompt).

## The three rules, and what enforces them
| Rule | Enforced by |
|---|---|
| One brain, everyone reads it | `Brain` (Canon/Chronicle); agents receive Canon records as input, never free recall |
| Every workflow has an owner and a tag | `tests/register.test.ts`: every component has an owner, an eval, and SOP rows matching its tags; no external write is autonomous |
| The system writes back | published text → Canon voice sample; B3 edits/verdicts → event log → calibration (L1); enquiries → radar input |

## Build order (Sheet 04B), with status in this repo
| # | Component | Days | Status here |
|---|---|---|---|
| 1 | C0 + shared setup | 1–5 | built: state machines, durable runner semantics, budgets, event log; production engine still to choose (R9) |
| 2 | B3 review | 2–10 | service and rules built, plus approve / edit / reject by email reply or form; **review screen and inbound mail provider not built** |
| 3 | A1 | 3–8 | Blueprint writer, checker, coverage loop, operational boundaries and the speaker's Blueprint document built; **voice transport not connected** |
| 4 | A2 + B2 | 6–11 | built |
| 5 | P1 | 9–14 | extraction, reply, guard built; **inbound email parser and form not connected** |
| 6 | B1 | 16–24 | built; **fetcher not connected**; source list to curate |
| 7 | P2 | 20–26 | built (HTML one-sheet; print to PDF) |
| – | P3, L1 | post-launch | entry gates and calibration maths built; agents deferred |

## Updates after the full Drive read (19 Oct)

Every file in the Project Dain Drive folder was read: five image-only decks (67 slides), five images and three documents. Five gaps were small enough to build at once:

1. **Blueprint document** (`src/agents/blueprint-doc.ts`): the Tier 1 (£995) deliverable, rendered from the Canon when the speaker approves.
2. **Operational boundaries** (deck BP6): topics to avoid and names never to use, captured in the interview, confirmed or rewritten by the speaker, and enforced by a code check in A2.
3. **Speaker's desk by email or form** (deck BE8): `review.reply`, sender-checked; untimed reviews are kept out of the edit-time median.
4. **Approval target 70%** (decks BE8 and the launch blueprint) replaces the spec's 66%: `checkLaunchGates` in `src/events.ts`.
5. **Review ceiling**: the groundskeeper flags specialist review above 4 hours per speaker in 30 days (decks BE13, VS12).

Still open, for the client (see `decisions/open-decisions.md`): the edit-time promise (15 min a week in the Speaker Growth Platform deck, under 15 min per post elsewhere); whether the speaker approves (missing from the Validation deck); articles and talk ideas (in the architecture, in no price tier); pilot length (14 days, 4 weeks or 30 days); and when relevance checking arrives (sold from day one, built in Days 16–29).
