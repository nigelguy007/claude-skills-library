# Project Dain · agents

The agents from the *Dain Agent Specification* (Rev 3), built as an AI company: one shared brain, four departments, one SOP skill file per component, autonomy tags on every workflow, and one conductor over all of it.

```bash
cd dain && npm install
npm test                 # 80 tests: contracts, gate chaos test, loops, guards, end-to-end flows, register rules
npm run demo             # whole company, offline, with a scripted model (fictional speaker "Helen Marsh")
npm run demo -- --live   # same flow against Claude (needs ANTHROPIC_API_KEY; DAIN_MODEL to override)
npm run dain -- map      # print the org chart from the register
```

## Layout (the map's four layers)

| Layer | Where |
|---|---|
| 1 · Brain | `brain/` (Obsidian vault + `CLAUDE.md`) · `src/brain/store.ts` (Canon / Chronicle) · `db/schema.sql` |
| 2 · Departments | `departments/{content,bookability,pipeline,agentic-os}/` |
| 3 · SOPs | `departments/<dept>/<component>/SKILL.md` (trigger, when, inputs, steps, handoffs, rules, examples, tools, test, autonomy) + `*.prompt.md` |
| 4 · Conductor | `src/conductor/` (fixed command routes, durable runner) · `src/state.ts` · `src/gate.ts` |

Agent code is in `src/agents/`, the review module in `src/review.ts`, the event log and pilot dashboard in `src/events.ts`, and the component register (R1) in `src/register.ts`. Start with `brain/00-company-map.md`.

## What's built, and what isn't

**Built and tested:** every node contract; A1 Blueprint writer + independent transcript checker + coverage loop; A2 weekly plan + drafting; B2 scorer with quote rule and code-computed verdict; the A2↔B2 loop (3 passes, then escalate); P1 extraction, reply, null-unstated rule and fee/date/commitment guard; B1 diamond (fan-out, reduce, 3-way verify, rank, inside-out mode); P2 pack rendering and change list; P3 entry gate and redaction; C0 state machines, budgets and durable-run semantics; Action Gate with hash-bound tokens, idempotency and crash reconciliation; B3 review service with active-time edit timer; groundskeeper sweeps; R8 cap; R2 calibration maths; R5 dashboard.

**Not built (integration work):** the review **screen** (web UI); the voice transport for A1 (Vapi or OpenAI Realtime); inbound email parsing, the web form and the phone share target for P1; the LinkedIn and email adapters (stubs only); the B1 fetcher (Firecrawl or Apify); the Postgres adapter for `db/schema.sql`; the production workflow engine (choose by R9's criteria). No prompt has been run against real Claude yet: there was no API key in the build environment, so the prompts are untested against the model and need the spec's pre-launch tests (3 mock interviews, 20 blind-rated drafts, 30 co-scored drafts, 50 past enquiries).
