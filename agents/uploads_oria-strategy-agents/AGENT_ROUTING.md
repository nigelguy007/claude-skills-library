# Agent routing and orchestration

**Prepared by Oria · AI for complex slides.** Use the fewest agents that materially improve the decision.

## Routing test

Before invoking an agent, score it on:

1. **Decision relevance:** Could its output change the decision?
2. **Information dependency:** Are its required inputs ready?
3. **Incremental confidence:** Does it add evidence or challenge not already covered?
4. **Time and cost:** Is the expected confidence gain worth the latency and context?

Skip an agent when the first three do not justify the fourth. Do not launch all 20 by default.

## The five-stage system

| Stage | Agents | Gate / handoff |
| --- | --- | --- |
| **Diagnose** | Problem Framer → Situation Assessor → Hypothesis Builder → Issue Tree Architect | Human approves mandate, criteria, scope, and evidence plan. |
| **Analyze** | Market Sizer; Profit Pool Mapper; Competitor War-Gamer; Customer Segmenter | Independent streams may run in parallel; reconcile at evidence gate. |
| **Decide** | Strategic Options Grid → optional Pricing Strategist / Business Case Builder / Portfolio Reviewer | Human approves option set or shortlist before selection. |
| **Execute** | Operating Model Designer → Initiative Prioritizer → Transformation Roadmapper → KPI Architect | Run only for an approved or clearly shortlisted option. |
| **Communicate** | Pyramid Story Builder → Decision Memo Writer → Hostile Q&A Simulator → Executive Deck Packager | Human approves recommendation before Oria production brief. |

## Dependencies

```text
Problem Framer
  ├─ Situation Assessor
  ├─ Hypothesis Builder
  └─ Issue Tree Architect
       ├─ Market Sizer ─────────┐
       ├─ Profit Pool Mapper ───┤
       ├─ Customer Segmenter ───┼─> Strategic Options Grid
       └─ Competitor War-Gamer ─┘       ├─ Pricing Strategist
                                        ├─ Business Case Builder
                                        └─ Portfolio Reviewer
                                              ↓
                                     Operating Model Designer
                                              ↓
                                     Initiative Prioritizer
                                              ↓
                                  Transformation Roadmapper
                                              ↓
                                         KPI Architect
                                              ↓
                                   Pyramid Story Builder
                                              ↓
                                    Decision Memo Writer
                                              ↓
                                  Hostile Q&A Simulator
                                              ↓
                                 Executive Deck Packager
                                              ↓
                                    Oria slide production
```

The diagram is a default dependency map, not a requirement to invoke every role. Hostile Q&A may send a targeted gap back to an earlier agent. If that new evidence changes the option set, repeat the applicable human gate.

## Fast routes

### Market-entry screen

Problem Framer → Issue Tree Architect → Market Sizer + Customer Segmenter + Competitor War-Gamer in parallel → Strategic Options Grid → Business Case Builder → Hostile Q&A Simulator → Pyramid Story Builder.

Add Profit Pool Mapper when value-chain position matters. Add execution agents only after a shortlist exists.

### Pricing / monetization

Problem Framer → Customer Segmenter + Competitor War-Gamer → Pricing Strategist → Business Case Builder → Hostile Q&A Simulator → Decision Memo Writer.

### Portfolio allocation

Problem Framer → Situation Assessor → Market Sizer + Profit Pool Mapper → Portfolio Reviewer → Business Case Builder for material reallocations → Decision Memo Writer.

### Transformation launch

Problem Framer → Situation Assessor → Operating Model Designer → Initiative Prioritizer → Transformation Roadmapper → KPI Architect → Hostile Q&A Simulator → Executive Deck Packager.

### Communication only

Approved recommendation → Pyramid Story Builder → Decision Memo Writer and/or Hostile Q&A Simulator → Executive Deck Packager → Oria.

Never use communication agents to manufacture a strategy that has not been decided.

### Early uncertainty test

Problem Framer → Hypothesis Builder → one targeted evidence agent. Stop if a load-bearing hypothesis fails before commissioning a full sprint.

## Parallelization rules

- Run tasks in parallel only when neither task needs the other’s output.
- Give every agent a self-contained work order and named source paths; subagents do not automatically inherit all coordinator context.
- Use parallel evidence streams to reduce shared framing bias, then reconcile definitions, periods, units, and contradictions.
- Keep synthesis, recommendation, and deck packaging sequential.
- Do not let parallel workers write to the same artifact. Each returns a versioned output for the coordinator to verify.

## Orchestrator verification checklist

- [ ] The mandate is approved and the route is the minimum viable route.
- [ ] Each agent performed only its named job.
- [ ] Downstream work used named, approved input versions.
- [ ] Evidence lineage and epistemic labels are complete.
- [ ] Calculations, periods, units, and ranges reconcile.
- [ ] Counterevidence and material dissent are preserved.
- [ ] Human gates occurred before option selection and deck production.
- [ ] No unapproved external action, data movement, or system write occurred.
- [ ] The Oria production brief contains only approved claims and traceable exhibits.

