---
name: startup-plan
description: >-
  Compiles what the startup-skill pack found (the board, the competitors, the buyer
  panel, the marketing plan and the numbers) into one business plan with a verdict at the top that is computed, never
  written by hand: Profitable, Not yet (with the numbers that fail) or Incomplete.
  Adds a half-page summary and the cheapest test to run on real people next. Use when
  someone asks "write my business plan", "put it all together", "is it profitable",
  "give me the verdict", "what should I do next", or as the last step of the
  startup-skill pack.
argument-hint: "[--min-buy-rate 0.20]"
---

# startup-plan

The last step. One document a founder can act on, or hand to a partner or a lender,
built only from what the pack found.

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/plan.py" --dir startup
```

If `${CLAUDE_SKILL_DIR}` is not expanded, use this skill's base directory (Claude
Code prints it when the skill loads; in Codex it is the folder this SKILL.md was read
from, usually `~/.codex/skills/startup-plan/`).

## Step 1: the verdict

```bash
python3 "${CLAUDE_SKILL_DIR}/plan.py" --dir startup --check
```

It prints the verdict and every check, all computed:

1. Each sale, or each customer each month, leaves money after its own costs.
2. Subscriptions: a customer brings in more than it costs to win them.
3. By month 12 the business makes money every month.
4. The money put in (startup spend plus the early losses) comes back within 24 months.
5. Break-even fits within what the business can handle, if a capacity was given.
6. At least 20 % of the simulated buyers would pay now, or, when the offer starts with a
   free trial, would start it today and expect to pay after it. Change the bar with
   `--min-buy-rate` only for a reason, and say the reason.
7. The buyers were shown the same price the numbers use. If the price changed after the
   panel, the panel has not tested it: run `/startup-buyers` again at the new price.
8. If there is a marketing plan, the numbers use its forecast of new customers and what
   each costs to win. Without one, the plan notes that the customer numbers are a guess.

It also warns when the plan is fragile: still profitable as planned, but not with
20 % fewer sales.

**Incomplete** means the numbers or the buyer panel are missing: offer to run
`/startup-numbers` or `/startup-buyers`. Never fill a missing part from guesses.

## Step 2: the real-world test

Write `startup/real-test.md`: the cheapest way to find out whether real people pay,
before the big money goes out. Simulated buyers suggest; only real ones prove.

| business | the test |
| --- | --- |
| app, software, online product | a landing page with the real price and a pre-order or paid waitlist |
| service or agency | three paying pilot clients at the planned price |
| subscription | a founding-member offer, paid up front |
| shop, food, local | a pop-up, a market stall or a pre-order list with a price and a date |

Include:

- **The success line, written before the test**: a number, a time window and a price
  (for example: 30 paid pre-orders in 14 days at $29). Compare it with the panel's
  "would pay now" rate.
- **Five questions for ten real customers**, built from the panel's top objections.
  Ask about what they did, not what they would do: "When did this last happen? What
  did you do about it? What did that cost you?" Never "would you buy this?"
- **What to do with the result**: if real people fall well short of the panel, trust
  the real people and go back to the pitch, the price or the customer.

## Step 3: the summary

Write `startup/summary.md`, half a page, plain words:

- What the business is and who it is for, in two sentences.
- The verdict and the three numbers behind it.
- What the board and the buyers agreed on, and where they disagreed.
- The biggest risk and what will be done about it.
- What it takes to start: the cash from the numbers, and the first real test.
- The one thing to do this week.

If the verdict is Not yet, lead with what has to change, which number it moves, and
which skill to run again. Never soften a failing check.

## Step 4: build the plan

```bash
python3 "${CLAUDE_SKILL_DIR}/plan.py" --dir startup
```

It writes `startup/plan.md`: the verdict and its checks, the key numbers, the
summary, the idea, the board, the competition, the buyer panel, how customers will find
it, the numbers, the real-world test, and what is not done yet.

## Rules

- The verdict comes from `plan.py`. Never write Profitable by hand, and never round a
  failing number into a passing one.
- Say once, clearly: the buyers are simulated and the numbers are projections; real
  customers and real quotes confirm them. Not financial, legal or tax advice.
- If the user wants a PDF or slides, offer to export, but keep `plan.md` as the source.

## Output

`startup/real-test.md`, `startup/summary.md`, `startup/plan.md`. Then give the user
the verdict in one line and the one thing to do this week.
