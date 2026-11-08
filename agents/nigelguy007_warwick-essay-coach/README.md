# warwick-essay-coach

An essay coach for a first-year Politics student at the University of Warwick (PAIS). It reviews essay plans, drafts and finished essays against the Year 1 curriculum (PO107 Introduction to Politics, PO131 World Politics) and the Warwick 20-point marking scale, and turns tutor feedback into an action plan.

It gives feedback; it does not write the essay. Warwick treats unacknowledged AI-generated content as plagiarism, and the assessment brief decides what AI use is allowed. The coach only explains, questions, and lists spelling, grammar, punctuation and referencing fixes for the student to accept or reject. That keeps the work hers and inside the rules.

| Piece | Where | For |
|---|---|---|
| `warwick-politics-essay-coach` skill | `skills/nigelguy007_warwick-essay-coach/warwick-politics-essay-coach/` | claude.ai chat, Claude Desktop, Claude Code |
| `warwick-politics-essay-reviewer` agent | `agents/nigelguy007_warwick-essay-coach/education/` | Claude Code (runs a review as a subagent, saves it to `essay-coach/reviews/` and keeps `essay-coach/tracker.md`) |

## Five modes

1. **Question & plan**: before writing. Unpacks the question and pressure-tests her thesis and outline.
2. **Draft check**: while writing. Paragraph by paragraph: point, evidence, analysis, link to the question.
3. **Full review**: before submitting. Indicative band on the 20-point scale, the 3–5 changes that would lift the mark most, curriculum check, line-level corrections.
4. **Proofread**: final polish. Corrections table only.
5. **Feedback to action**: after marks come back. Plain-English reading of the tutor's comments and a ranked action list; tracks recurring issues across essays.

## Set-up for the student (claude.ai or the Claude app)

1. Build the upload zip: `python3 scripts/package_for_claude_ai.py warwick-politics-essay-coach` (written to `dist/claude-ai/`).
2. In claude.ai: Settings → Capabilities → Skills → upload the zip.
3. Best: create a Project called "Politics essays" and add the module handbooks, reading lists, essay briefs and every piece of tutor feedback as Project files, so the coach can use them.
4. Start a chat with: module, the exact question, word limit, and what the brief says about AI. Then paste or attach the plan, draft or feedback.

Chat can't save files between conversations, so after a Full review or Feedback session the coach prints a "carry forward" block. Paste it into the Project files to keep the history.

## Set-up in Claude Code

```bash
./install.sh --source nigelguy007_warwick-essay-coach            # skill
./install.sh --agents --source nigelguy007_warwick-essay-coach   # agent
```

## Keep it current

The curriculum and marking reference files were checked in November 2026 against the public Warwick module catalogue for 2026/27. Each new year, re-check the module pages linked in `references/curriculum.md`. If she can share the PAIS UG handbook marking criteria (login only), add them to `references/marking-rubric.md`.

## Limits

- The indicative mark is a guide, not a prediction. Her tutor marks the work.
- The third Year 1 core module (academic and research skills) isn't detailed: its public page wasn't found. Give the coach the brief when it comes up.
- If a brief bans AI, the coach declines that piece.
- She must declare her use of the coach wherever the brief or Warwick's submission declaration requires it.
