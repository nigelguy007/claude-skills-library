# book-studio

Eight subagents that write a nonfiction book with you, plus the `write-book` skill that orchestrates them (`skills/nigelguy007_book-studio/write-book`). They merge two prompt sets (a ChatGPT book-writing set and a NotebookLM book-creation set) and remove the duplicate steps.

| Agent | Covers |
|---|---|
| `book-market-strategist` | 10 ranked book ideas with verified comparable titles |
| `book-architect` | Raw notes → 5–7 pillars → 3 structures → full outline |
| `book-title-cover-marketer` | 20 titles and subtitles, cover briefs (Minimal, Premium, Bold), Gemini cover prompts |
| `book-chapter-writer` | One chapter in the author's voice, plus a 3-step action checklist |
| `book-developmental-editor` | Expert-level revision and an edit summary |
| `book-visuals-designer` | Framework infographic and action-plan prompts for Gemini or Canva |
| `book-copy-editor` | Line edit, a change log with reasons, and a style sheet |
| `book-launch-consultant` | KDP formatting, upload, categories, pricing, description, 30-day launch |

Install:

```bash
./install.sh --agents --source nigelguy007_book-studio
```

Then run `/write-book` in Claude Code. The orchestrator is a skill, not an agent, because subagents can't start other subagents.

Ground rules built into every agent:
- No invented stories, studies, statistics or quotes. Gaps are marked `[STORY NEEDED]` or `[SOURCE NEEDED]`.
- Comparable books and KDP rules are checked on the web and linked.
- Nothing is published automatically.
