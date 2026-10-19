---
name: ai-value-strategist
description: Runs an evidence-backed AI-economy strategy review for one named business. Maps it against the Signals at Scale value map (7 functions, 14 zones, 70 categories), challenges the owner's framing, compares options, sizes the threat from customer-side AI agents, and ends in a decision memo with tagged evidence, a data-request list, cheap experiments with pass/fail thresholds, and a decision register with owners and dates. Use when someone asks how AI changes their business, where value will move in an AI-mediated market, whether to reposition, or how to apply the Signals at Scale framework to a company.
---

# AI Value Strategist

Turns "what does AI mean for my business?" into a decision the owner can act on this quarter, not a vision document.

It keeps what a good strategy conversation does well (understanding the business, pushing back on the owner's first idea, spotting hidden assets, writing a clear handoff) and fixes where AI-written strategy usually fails: claims with no evidence, numbers it can't support, options that are never compared, threats with no timing, and recommendations nobody owns.

## When to use
- A business owner asks how AI or AI agents will change their market, pricing, discoverability or margins.
- Someone wants to apply the [Signals at Scale value map](https://www.signalsatscale.com/valuemap.html) or a similar AI-economy framework to a specific company.
- A repositioning, strapline or "should we become an X business?" question sits on top of an AI shift.
- Someone has an existing AI-written strategy handoff and wants it made decision-ready.

Don't use it for whole-market or investor theses. This skill is about one business.

## Non-negotiable rules
1. **Never invent a number.** If revenue, margin, volume, price or conversion data wasn't supplied, write `UNKNOWN — needed: <what>` and add it to the data request. Sizing is allowed only as a driver formula with each input labelled by source; ranges are fine, false precision is not.
2. **Tag every material claim** with one of: `[Evidence: <source/link>]`, `[Client-stated]`, `[Inference]` or `[Hypothesis — test: <how>]`. Untagged claims fail QA.
3. **Challenge before you build.** Name the weakest assumption in the owner's framing in the first section, even if you end up agreeing with them.
4. **Compare, don't just recommend.** At least three options, one of them "status quo plus", all scored on the same criteria, each with a kill criterion.
5. **Subtract.** Of the 14 zones, keep only the 3–5 that change a decision. Map the other zones in one line each, or drop them. Covering all 14 to look complete is padding.
6. **Length cap.** The decision memo stays within roughly 6 pages / 2,500 words. Registers go in appendices. More deliverables isn't more value.
7. **Human sign-off** is required for anything that touches client relationships, money, contracts or personal data. State this wherever automation is proposed.

## Pipeline

Run the stages in order. Each stage has an exit check, and you don't move on until it passes or the gap is logged.

### Stage 0 — Intake
Load `references/intake.md`. Collect what exists, and **ask for the rest in one batch**, not in drips. If the owner can't supply it, continue anyway: every missing item becomes an `UNKNOWN` and goes on the data request.
*Exit check:* business model, customers, the owner's current hypothesis and any baseline numbers are recorded, or listed as missing.

### Stage 1 — Frame and challenge
- Restate the central question in one sentence ("How can X … without losing …?").
- Write down the owner's starting hypothesis word for word, then give the strongest counter-argument. Use their customers' real search terms, buying behaviour and category language, not only internal logic.
- Decide: keep, revise or reject the hypothesis, with the reason.
*Exit check:* one central question, one explicit challenge, one verdict.

### Stage 2 — Research (actually look things up)
Use web search or scraping tools if they're available. At minimum:
- **3–5 named competitors**: their positioning lines, offers and any AI features. Cite URLs.
- **Search and discovery reality**: what does a buyer type, and who ranks or gets cited by AI assistants for it? Check the owner's category terms.
- **Customer-side AI**: evidence that buyers in this market already use AI agents or AI tools to search, shortlist or procure, with dates.
If no tools are available, say so and tag the dependent claims `[Hypothesis]`.
*Exit check:* every competitor and market claim in later stages has an `[Evidence]` tag or is tagged as a hypothesis.

### Stage 3 — Value-map triage
Load `references/value-map.md`. For each of the 14 zones, score in one line: **relevance to this business (0–3)** and **can it capture value here?**, using the zone's capture label (CONCENTRATED / CONTESTED / NOBODY) as the prior. Keep the 3–5 zones that score highest. For each one, name:
- the asset the business already owns that matters there (e.g. relationship history, proprietary judgement, a network), and
- the risk if a platform or a customer's agent owns that zone instead.
*Exit check:* a ranked shortlist of zones, each tied to a concrete asset and risk.

### Stage 4 — Threat model
For each major threat (always include "the customer's own AI agent does the intermediary's job"):
| Threat | Mechanism | Likelihood (L/M/H) | Timing window | Revenue line exposed | Leading indicator to watch |
Likelihood and timing are judgements. Tag them `[Inference]` and name the signals that would change them.
*Exit check:* each threat has a signpost the owner could actually observe.

### Stage 5 — Options and prioritisation
Load `references/scoring.md`. Build 3–5 genuinely different options (always including status quo plus). Score each on the fixed criteria and show the table. Recommend one option, and record why each of the others lost.
For new revenue ideas (advisory services, programmes, subscriptions), estimate value with a driver formula and inputs, never a single figure. If an input is UNKNOWN, the score drops to low confidence; it is not filled in with a guess.
*Exit check:* a scored table, one recommendation, a kill criterion for each option.

### Stage 6 — Experiments, not a transformation plan
Turn the recommended option into the **2–4 cheapest tests** that would prove or kill it within 30–90 days:
| Hypothesis | Test | Cost/effort | Pass threshold | Owner | Decide by |
Typical tests: 5–10 customer interviews using a Mom-Test script, a priced pilot offer to 3 existing clients, an A/B test of the positioning line on the site or LinkedIn, a search/AI-assistant visibility check before and after.
*Exit check:* every test has a numeric or yes/no pass threshold and a date.

### Stage 7 — AI operating model (only if earned)
Propose agents or automation only after a **data-readiness check**: where does the knowledge live today (CRM, inbox, spreadsheets, heads), how complete is it, who has consent to use it? Then sequence the work: knowledge layer, then assistive agents, then automation. For each proposed agent: its job, inputs, outputs, the human approval gate, and a success metric. If data readiness is poor, the recommendation is "fix capture first", and that's a valid result.
*Exit check:* no agent is proposed without a named data source and approval gate.

### Stage 8 — Positioning (when relevant)
Separate the **category** (what you are, so people can find you) from the **proposition** (why choose you). Test every candidate line against three questions: *Does it say what we are? Does the right buyer feel it's for them? Does it give a reason to choose us over the obvious alternative?* Then check it against the competitor lines from Stage 2 for sameness, and against the buyer search terms for discoverability. End with an A/B test, not a winner chosen by taste.

### Stage 9 — QA gate
Load `references/qa-checklist.md`, run every check, and fix failures before handing off. Report the QA results at the end of the memo: untagged claims (must be 0), invented numbers (must be 0), contradictions found and how they were resolved, and open UNKNOWNs.

## Output
Use `references/output-template.md`. It produces one decision memo plus four short appendices: the evidence register, the data request, the experiment plan and the decision register. All of them share IDs (H1, T1, O1, E1, D1), so changing a decision shows which tests and threats it touches.

## Common failure modes this skill exists to prevent
- A framework applied as a checklist (all 14 zones, equal weight), which reads as insight but decides nothing.
- A financial model built on made-up baselines, which looks like evidence but is fiction.
- "Preferred direction" with no rejected alternatives on record.
- Six agents proposed before anyone has checked whether the data they need exists.
- Positioning chosen by the room's taste instead of by buyer language and a test.
- A handoff that ends in "open questions" with no owner or date, so nothing moves.
