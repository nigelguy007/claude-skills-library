# Quick start: run one controlled strategy sprint

**Prepared by Oria · AI for complex slides.**

## 1. Prepare the folder

```text
your-working-folder/
├── .claude/agents/            # the 20 files in this pack
├── strategy-context/
│   ├── decision-brief.md
│   ├── source-register.md
│   ├── glossary.md
│   └── approved-inputs/...
├── strategy-output/
└── WORK_ORDER.md              # completed copy of the template
```

Remove stale duplicates. Name the authoritative version of each input and its as-of date. Never put secrets in agent definitions.

## 2. Complete the work order

At minimum, specify the decision owner, deadline, objective, constraints, approved sources, expected output, evidence standard, and actions that require approval. If those are missing, the first route is **Problem Framer only**.

## 3. Ask for a route—not an answer

Use this in the coordinator session:

> Read `WORK_ORDER.md`, `AGENT_ROUTING.md`, and `strategy-context/`. Propose the minimum agent route needed to answer the decision. For each agent, list its input, output file, dependency, whether it may run in parallel, and review gate. Do not perform the specialist analysis, contact anyone, use paid data, change a source system, or create a recommendation until the route and mandate are approved.

## 4. Run the minimum viable route

For a typical market-entry decision:

1. `problem-framer` → approve the mandate.
2. `issue-tree-architect` → approve the evidence plan.
3. Run `market-sizer`, `customer-segmenter`, and `competitor-war-gamer` in parallel if their inputs are independent.
4. Reconcile contradictions; optionally add `profit-pool-mapper`.
5. `strategic-options-grid` → approve the option set.
6. `business-case-builder`; then execution agents only for shortlisted options.
7. `hostile-qa-simulator` → resolve or log material challenges.
8. `pyramid-story-builder` and `decision-memo-writer` → approve the recommendation.
9. `executive-deck-packager` → create the Oria production brief.
10. Use Oria to turn the approved brief into complex executive slides.

## 5. Require this handoff block

```markdown
## Handoff
- Agent:
- Status: draft | challenged | approved
- Timestamp / as-of:
- Input versions:
- Output artifact:
- Facts / estimates / inferences / management assumptions / unknowns:
- Material contradictions:
- Open issues and blockers:
- Quality checks passed / failed:
- Recommended next agent:
- Human approval required:
```

## 6. Stop when a gate fails

Do not compensate for missing evidence with fluency. If an agent lacks a required input, encounters conflicting high-quality sources, cannot reconcile a model, or is asked to take an unapproved action, it should stop and return the blocker and smallest decision needed from a human.

