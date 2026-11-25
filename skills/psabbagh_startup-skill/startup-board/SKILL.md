---
name: startup-board
description: >-
  Puts a business idea in front of a board of eight advisors, each a separate
  sub-agent applying one published playbook: Alex Hormozi's $100M Offers and $100M
  Leads, Peter Thiel's Zero to One, Seth Godin on marketing, Naval Ravikant on
  leverage, Tobi Lutke's memo on AI-native work, Lenny Rachitsky on first users and
  retention, and Paul Graham's startup essays. Each scores the idea from 1 to 10, names what would kill it and the
  assumption it rests on, and votes fund, fund if, or pass. Use when someone says
  "test my business idea", "would this work", "pressure-test this", "what would a
  board say", "is this a good business", or as step 1 of the startup-skill pack.
argument-hint: "<the business idea, or leave blank to use the conversation>"
---

# startup-board

The first meeting. Before anyone builds a website or signs a lease, a board of
advisors looks at the idea from different angles, independently, and votes.

What the user typed after the command: `$ARGUMENTS`. If it is blank, take the idea
from the conversation.

## Playbooks, not people

Each advisor applies a summary of a **published playbook**, nothing more. The
advisors are not the authors, never speak as them, never quote them, and never claim
they would endorse anything. The opinion belongs to "the Offer advisor", never to the
author by name. If the user asks what one of the authors would really think, say you
can only apply their published ideas.

## Step 0: the idea file

Every step of the pack reads `startup/idea.md` in the user's project. If it does not
exist, write it from the conversation:

```markdown
# <business name, or a working name>

- What it is: one sentence.
- Who it is for: the target customer, as specific as the user can make it.
- What it sells, at what price: the core product and its price.
- How customers find it and get it: online or local, the channel, how it is delivered.
- What the founder brings: money, time, skills, contacts, anything already decided.
- What the founder already knows: real conversations, sales, waitlists, numbers.
```

If the name, the customer, the product or the price is missing, ask for them (at most
three questions in one message), then write the file. Do not invent a budget, a
market size, a competitor or a customer conversation.

## Step 1: the brief

Write `startup/board/brief.md`: the idea file plus everything else the user said that
a stranger would need. **Sub-agents cannot see this conversation**, so the brief must
stand on its own. Keep what the founder knows (they talked to customers, they have a
waitlist) apart from what they believe. Do not add your own opinion of the idea.

## Step 2: convene the board

The advisors are the `## The ...` sections of `advisors.md` in this skill's folder
(`${CLAUDE_SKILL_DIR}/advisors.md`; if that is not expanded, use this skill's base
directory, which Claude Code prints when the skill loads; in Codex it is usually
`~/.codex/skills/startup-board/`). There are eight. Launch one
sub-agent per advisor, all in ONE message so they work independently. In Claude Code
that is the Agent tool, `subagent_type: general-purpose`, with this prompt:

```
Read <absolute path to startup/board/brief.md> and the section "<advisor heading>"
of <absolute path to advisors.md>. Apply ONLY that advisor's playbook to the
business in the brief. Write your memo to <absolute path to startup/board/<name>.md>
in exactly the shape below. Mark every claim either "(from the brief)" or "(my
assumption)". Never speak as the playbook's author or quote them.
```

followed by the memo shape:

```markdown
# The <name> advisor
Score: <1-10> | Vote: FUND / FUND IF / PASS
## What is strong
## What would kill it (the top 3, most dangerous first)
## The assumption it all rests on, and the cheapest way to test it
## Questions for the founder
## If FUND IF: the conditions
```

In Codex, spawn one agent per advisor with its multi-agent feature, with the same
prompt, and wait for all of them. If multi-agent is off, ask the user to turn it on
(`multi_agent = true` under `[features]` in `~/.codex/config.toml`) and start a new
session. With no way to run separate agents at all, write the memos one after another
and tell the user they were not independent.

## Step 3: the chair's summary

Read the memos (they are short) and write `startup/board.md`:

1. The vote (for example "5 fund if, 3 fund, 1 pass"), the average score, and each
   advisor's score in a short table.
2. The risks more than one advisor raised: these go first.
3. **The five questions.** Answer each in a line or two, from the brief and the memos,
   or write "nobody knows yet" and the step that will find out:
   1. What one problem does it fix, and do these customers already spend time or money
      on that problem today? People pay to have a problem fixed, not for the technology.
   2. Is the founder about to build the expensive version first? What is the cheapest
      thing that would show people will pay?
   3. How do the first ten customers hear about it, and what does each one cost to win?
      Building it is not the same as people using it.
   4. To get the value, does the customer have to change more than one habit, or spend
      money somewhere else first? Every extra step loses buyers.
   5. Would the demand come from many customers, or from one or two big ones? One large
      customer is a relationship, not proof that the market wants it.
4. The assumptions the idea rests on, as a checklist, each with the step that tests it:
   the buyer panel (`/startup-buyers`), the numbers (`/startup-numbers`) or a real-world
   test (`/startup-plan`). Merge every FUND IF condition into the same checklist.
5. One paragraph: the strongest version of this business the board can see. It may
   differ from what the user pitched; say so plainly.

Keep the disagreements. A board that agrees on everything was not doing its job.

## Rules

- Score the business, not the founder.
- No made-up facts. A number nobody has yet (market size, cost of winning a customer)
  is an open question with the step that answers it.
- A PASS is a result, not a failure. Say it plainly.

## Output

`startup/idea.md`, `startup/board/` (the brief and one memo per advisor),
`startup/board.md`. Then give the vote in one line and suggest the next step:
`/startup-competitors` to see how buyers already solve this and what they pay.
