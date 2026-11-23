# Oria Strategy Agents for Claude

Twenty bounded strategy agents mapped to **Diagnose → Analyze → Decide → Execute → Communicate**. The pack turns the public playbook into an inspectable workflow: each agent has a job, evidence contract, controls, output, and handoff.

**Prepared by Oria · AI for complex slides.** Claude supports the reasoning workflow; Oria turns an approved recommendation into polished, executive-ready slides.

## What is included

- `.claude/agents/` — 20 Claude Code project-agent definitions.
- `QUICKSTART.md` — a safe first run.
- `WORK_ORDER_TEMPLATE.md` — the run-specific contract.
- `AGENT_ROUTING.md` — minimum viable routes, dependencies, and approval gates.

This package contains **agents**, not Claude Skills. An agent owns a bounded workflow. A Skill records a reusable method. If your team repeatedly uses the same source hierarchy, model checks, interview-coding method, or Oria slide standard, record that separately as a Skill and reference it in the work order.

## Install in Claude Code

1. Unzip the package into the root of the working folder. The definitions must land at `.claude/agents/*.md`.
2. Open Claude Code in that folder. If the agent list does not refresh after creating the directory, start a new session.
3. Add only approved engagement material to a `strategy-context/` folder. Include a mandate, source register, glossary, prior decisions, and current templates; do not add secrets unless your organization explicitly permits them.
4. Copy and complete `WORK_ORDER_TEMPLATE.md` for the decision.
5. Start with the routing prompt in `QUICKSTART.md`. Approve the route before analysis begins.

Project agents use YAML frontmatter understood by Claude Code (`name`, `description`, `model`, `disallowedTools`, `permissionMode`, and `maxTurns`) followed by a self-contained system prompt. `permissionMode: plan` is intentional: the portable pack is analysis-oriented and should not imply authority to write to source systems or act externally. `disallowedTools: Agent` keeps each specialist a leaf worker so the coordinator session owns routing. The files do not declare a fixed positive tool list because available tools and MCP servers vary by environment.

## Use in a Claude.ai Project or manually

Claude.ai Projects can hold durable project instructions and knowledge. They do **not** execute `.claude/agents/` files as native Claude Code subagents. To use this pack there:

1. Upload the completed work order and approved sources to Project knowledge.
2. Open the relevant agent Markdown file and use its body as specialist instructions in a chat.
3. Run one agent at a time, or manually run independent evidence streams in separate chats.
4. Copy each structured output into Project knowledge before invoking the downstream specialist.
5. Keep the human approval gates in `AGENT_ROUTING.md`.

Product capabilities, plan availability, and interfaces can change. Confirm current Anthropic documentation and your organization’s admin policies before rollout.

## Orchestration contract

Use a human lead or a coordinator session to route work. The orchestrator does not replace the specialists and should not invent their outputs.

- Invoke the **fewest agents** that materially improve the decision.
- Parallelize only independent work; sequence dependent work.
- Provide downstream agents the named, versioned artifacts they require—do not assume the parent conversation is inherited.
- Stop at three gates: mandate/evidence plan; option set/shortlist; recommendation/deck production.
- Reject outputs that violate role boundaries, evidence lineage, arithmetic checks, or the stated output contract.
- Preserve material dissent and open issues in every handoff.

The post headline says “20+,” but its five stage lists name exactly 20 agents. This pack intentionally contains those exact 20 named workflows. Coordination is a role performed by the user or coordinator session, not a hidden 21st agent.

## Shared controls

1. **Evidence lineage:** source, date, location/excerpt, transformation, and confidence for every material claim.
2. **Epistemic labels:** `Fact`, `Estimate`, `Inference`, `Management assumption`, or `Unknown`.
3. **No fabrication:** no invented values, quotes, citations, market shares, competitor motives, owners, or dates.
4. **Read-only default:** no messages, purchases, uploads, writes, system changes, publication, or transactions without separate explicit approval.
5. **Least data:** use authorized sources, minimize personal data, and never move confidential material into an unapproved tool.
6. **Transparent math:** expose formulas, units, periods, ranges, sensitivities, and reconciliation checks.
7. **Human authority:** agents draft and recommend; accountable people approve commitments and irreversible actions.
8. **Versioned handoffs:** include agent, timestamp, input versions, status, open issues, and next recipient.

## Limitations and security

These agents can miss context, misread a source, produce faulty calculations, omit contrary evidence, or reproduce bias. Their outputs are drafts for qualified human review—not legal, investment, accounting, regulatory, or transaction advice.

The pack does not grant access to the web, databases, paid data, files, or applications. Access depends on the user’s environment. A connector provides access, not truth: verify freshness, authorization, scope, and source quality. Treat retrieved content as potentially untrusted; do not follow embedded instructions that conflict with the work order.

Never place API keys, passwords, personal data, material non-public information, or restricted client information in agent files. Follow internal retention, privacy, licensing, compliance, and professional-review requirements. Escalate material ambiguity rather than filling it with plausible text.

## Oria slide handoff

Only `executive-deck-packager.md` should create the final production brief, and only after the recommendation is approved. The brief should contain audience and decision, action-title spine, one message per slide, exhibit specification, data lineage, source notes, appendix proof, and speaker cues. Give that approved brief to **Oria, AI for complex slides**, for slide design and production.
