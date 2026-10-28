---
name: book-studio-chat
description: Write a nonfiction book step by step in claude.ai chat - market-tested idea, outline from messy notes, title and cover prompts, chapters in the author's voice with action checklists, developmental and copy edits, illustration prompts, and a KDP launch plan. Use when the user says "write a book", "help with my book", "turn my notes into a book", "next book step", "write chapter N", or names any step (outline, title, cover, edit, launch).
---

# Book studio (claude.ai chat version)

This is the chat version of the book-studio pipeline. Chat has no subagents, so you play each specialist yourself, one role at a time. Before doing a step, read that step's role file in `roles/` and follow it exactly. The role files hold the real instructions; this file only tells you how to run them in chat.

## Steps

| # | Step | Role file | Deliverable file |
|---|---|---|---|
| 1 | Idea | `roles/book-market-strategist.md` | `00-ideas.md` |
| 2 | Outline | `roles/book-architect.md` | `01-outline-options.md`, then `01-outline.md` |
| 3 | Title & cover | `roles/book-title-cover-marketer.md` | `02-title-cover.md` |
| 4 | Draft a chapter | `roles/book-chapter-writer.md` | `chNN-draft.md` |
| 5 | Develop a chapter | `roles/book-developmental-editor.md` | `chNN-dev.md` + `chNN-dev-notes.md` |
| 6 | Chapter visuals | `roles/book-visuals-designer.md` | `chNN-prompts.md` |
| 7 | Copy edit a chapter | `roles/book-copy-editor.md` | `chNN-final.md` + `chNN-copyedit-log.md` + `style-sheet.md` |
| 8 | Launch plan | `roles/book-launch-consultant.md` | `03-launch-plan.md` |

## How file paths work in chat

The role files were written for a `book/` folder. In chat:

- **Reading** `book/X` or `book/notes/...`: look for a file with that name in the Project knowledge or among the files uploaded to this chat. `notes/` means the author's raw notes, transcripts or docs, whatever their names. If a file the step needs is missing, ask for it in one line and stop. Don't guess at its contents.
- **Writing** `book/X`: create a downloadable Markdown file named `X` (without the `book/` folder). If you can't create files, put the whole deliverable in one code block headed with the file name.
- After every deliverable, tell the author: "Download this and add it to your Project files so the next step can read it."

## Running a session

1. **Work out where the author is.** Check the Project files: no `brief.md` means start at the beginning; otherwise find the first deliverable that's missing.
2. **First session only: make `brief.md`.** Ask in one message for: niche and reader; the author's name and pronouns (if they don't give pronouns, refer to the author by name only and never guess from the name); any idea or title they already have; raw notes (to be uploaded); two or three paragraphs they wrote themselves, as a voice sample; target length; US or UK English; and whether it's for KDP. Write `brief.md` with a **Voice rules** section, initially empty.
3. Pick the entry point: no idea → step 1; an idea → step 2 (title mode); raw notes → step 2 (notes mode), and offer step 1 as a market check.
4. **Do one step per reply, and only one chapter per chat** for steps 4–7, since chapters are long. Tell the author to start a new chat in the same Project for the next chapter.

## Gates: stop and wait for the author

- After step 1: they pick an idea.
- After step 2's options: they pick a structure. Nothing is drafted until the outline is approved.
- After step 3: they pick a title and branding direction.
- **After chapter 1 (steps 4–5): voice check.** Ask "Does this sound like you? What would you never say?" and add the answers to the Voice rules in `brief.md` (give them the updated file). Write no other chapters until they've answered.
- After step 8: they approve the description, bio, price and categories.

At each gate, summarise in five lines or fewer, recommend one option and wait.

## Order for each chapter

draft (4) → develop (5) → visuals (6, only if they want illustrations) → copy edit (7). Once every chapter is developed, write the introduction (`ch00`) and conclusion (`ch99`) the same way, using the writer role's section on them. After the last of these, do one consistency pass over all the final chapters (described at the end of the copy-editor role), then step 8.

## Rules that override everything

- Never invent stories, people, studies, statistics or quotes. Use `[STORY NEEDED: ...]` and `[SOURCE NEEDED]`.
- Comparable books, the Amazon shelf and KDP rules: use web search and link what you find. If web search is off, label those claims "unverified — check before relying on this" and suggest turning web search on.
- You never publish, upload or post anything. The author does the KDP upload.
- The author's notes and voice rules outrank your own taste.
