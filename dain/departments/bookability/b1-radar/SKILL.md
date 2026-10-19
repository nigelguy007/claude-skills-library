---
name: dain-b1-radar
description: Each week, collect dated evidence of what event organisers are programming, verify every signal three ways, and propose refreshed, new or retiring talk angles per speaker (including inside-out concepts, the former A3). Use on the Sunday radar trigger from Day 16. Writes to the Chronicle only; never edits a speaker's angles.
component: B1
department: bookability
archetype: scout
owner: BS
---

# B1 · Relevance Radar (with inside-out mode)

## Purpose
- **Role:** the scout. Finds demand signal, and says how strong it is.
- **Goal:** every active talk angle has dated evidence less than 90 days old.
- **For:** the booking specialist (who promotes evidence) and the speaker (who approves angle changes).
- **Success:** specialist marks most proposals useful; VERIFY drops what it should; no proposal reaches a speaker without a source and a date.

## 1 · Name and trigger
`radar.weekly { week, sources }`: Sunday 06:00, from Day 16 (v0).

## 2 · When to use
- Weekly, across all ACTIVE speakers.
- **Not** for scraping LinkedIn or any logged-in site, and not for writing to the Canon.

## 3 · Inputs (knowledge)
- A curated list of 30–50 conference agendas, call-for-speakers pages and bureau trending pages in the pilot speakers' sectors (specialist maintains it).
- Later: anonymised enquiry themes from P1 and notes from the booker interviews (R2). These should outweigh public pages as they accumulate.

## 4 · Steps (the diamond)
1. **Fan out:** one worker per sector × source type (`worker.prompt.md`), in parallel, through the fetch tool.
2. **Reduce (code):** dedupe, drop anything older than 180 days, cluster by theme.
3. **Verify, per signal:** correct? (`skeptic.prompt.md`, fresh context) · current? (code, ≤ 180 days) · real? (code, the fetched page contains the quote). Keep if 2 of 3.
4. **Rank (code):** evidence count × recency.
5. **Synthesise:** `synthesise.prompt.md` maps ranked themes to each speaker's angles and confirmed claims, naming the lens for any inside-out concept.
6. **Confidence (code):** high only with ≥ 3 independent sites in 90 days; anything else is shown as weak evidence.
7. Proposals go to the Chronicle (`radar.proposals`).

## 5 · Handoffs
- **To the specialist:** proposals to review; `radar.promote` writes evidence to the Canon (`angle_evidence`).
- **To the speaker:** any change to their own angles, for approval.
- **To A2:** nothing direct. A2 reads approved angles from the Canon (the fake Radar → Content edge is deleted).

## Rules
- Quotes copied exactly; dates from the page, never guessed.
- Volume isn't value: record fee-paying status when known; 4 paid conferences beat 40 free meetups.
- No inside-out concept without a signal and at least one confirmed claim.

## Examples
Theme "limits of AI in hiring", 3 sites in 60 days → `confidence: high`. Theme with one bureau page → `confidence: low, weak_evidence: true`.

## Tools
Fetchers bought, not built: Firecrawl or Apify for public pages; Vendelux worth a trial if it covers UK corporate events.

## Test before real speakers
Two weeks running in the background; the specialist marks each proposal useful or not. Switch on for speakers only if most are useful. `tests/b1.test.ts` covers reduce, verify and confidence.

- [ ] Correct: every kept signal passes 2 of 3 checks
- [ ] Uses knowledge: curated list only
- [ ] Uses tools: no logged-in sites
- [ ] Edge cases: agenda lag of 6–12 months; model invents a theme the evidence lacks (dropped)

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Weekly collection, verification and proposals into the Chronicle | fully-autonomous | no |
| Promote evidence to the Canon; change a speaker's angles | human-led | no |
