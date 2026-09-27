# dkorobtsov/pitch-deck

Source: [dkorobtsov/pitch-deck](https://github.com/dkorobtsov/pitch-deck) · Author: Dmitry Korobtsov · License: MIT

> Narrative-first pitch deck builder and auditor — story before slides, writing before design,
> meaning before data.

Upstream this is a **Claude Code plugin** exposing two slash commands (`/create`, `/audit`). For this
library — where everything is a *model-invoked* `SKILL.md` — the two commands have been converted into
two skills so Claude loads them automatically when your request matches:

| Skill | What it does |
|-------|--------------|
| [`pitch-deck-builder`](pitch-deck-builder/SKILL.md) | Build an investor-grade deck from scratch: 12-question founder interview, then 6 gated phases (Interview → Foundation → Story → Objections → Design → Marp slides), rendered to PDF. |
| [`pitch-deck-audit`](pitch-deck-audit/SKILL.md) | Stress-test an existing deck with a 7-test investor-lens battery and produce a graded report with revised headlines. |

## Supporting files (preserved from upstream)

- [`references/reference.md`](references/reference.md) — detailed frameworks (Seven Moats, Onion
  Theory, Traction Rules, presentation budgets, headline writing, anti-patterns).
- [`assets/theme.css`](assets/theme.css) — the canonical `pitch-deck` Marp theme used at the slide
  generation phase.
- [`examples/headlines-comparison.md`](examples/headlines-comparison.md) — worked weak-vs-strong
  headline examples.
- [`AGENTS.md`](AGENTS.md), [`plugin.json`](plugin.json) — original plugin manifest and agent guide,
  kept for provenance.

## Output convention

Both skills write to `./pitch/` relative to the current working directory (interview transcript,
foundation, story, objections, visual brief, `pitch-deck.md`/`.pdf`, `theme.css`, and `pitch-audit.md`).

## Building slides

The slide-generation phase renders with [Marp](https://marp.app/):

```bash
marp --theme ./pitch/theme.css --html --pdf ./pitch/pitch-deck.md -o ./pitch/pitch-deck.pdf
```

Marp CLI is an external dependency and is not bundled here.
