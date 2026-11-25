---
name: startup-numbers
description: >-
  Works out whether a business makes money before any is spent: what each sale or
  each customer leaves after its own costs, what it costs to win a customer and
  whether they are worth it, the break-even, 24 months month by month, the cash
  needed before it pays for itself, when the money put in comes back, and what
  happens if prices, sales or costs go the wrong way. Handles subscriptions
  (customers who cancel) and one-off sales. Use when someone asks "is this
  profitable", "do the numbers", "find my margins", "break-even", "unit economics",
  "how much money do I need to start", "how many customers do I need", or as step 5
  of the startup-skill pack.
argument-hint: "[path to numbers.json]"
---

# startup-numbers

The person in the room who asks "and what does that cost?" A good idea is only a
business if the numbers work. This skill finds out, with every number traceable to
an input the user can check.

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/numbers.py" startup/numbers.json --out startup/numbers.md
```

If `${CLAUDE_SKILL_DIR}` is not expanded, use this skill's base directory (Claude
Code prints it when the skill loads; in Codex it is the folder this SKILL.md was read
from, usually `~/.codex/skills/startup-numbers/`). Two worked examples sit next to this file: `example-subscription.json` (an app
for hair salons, $29 a month) and `example-one-time.json` (a kit sold online).

## Step 1: gather the inputs

Write `startup/numbers.json`. First pick the model:

- **subscription**: customers pay every month and some cancel (apps, software,
  memberships, retainers).
- **one-time**: each sale is its own purchase (products, kits, courses, meals, events).

| field | what goes in it |
| --- | --- |
| `price` | per unit (one-time) or per customer per month (subscription), before tax |
| `variable` | the cost of ONE unit, or of serving one customer for a month: materials, shipping, hosting, card fees |
| `fixed_monthly` | paid every month whatever happens: rent, salaries, the founder's own pay, software |
| `startup` | one-off spend before opening: building it, equipment, first stock, legal, launch ads |
| `sales` (one-time) | 12 numbers: units sold in each month of year 1 (or `sales_per_day` with `days_per_month`) |
| `marketing_per_sale` (one-time) | ad and marketing spend to make one sale. 0 only if sales really come for free, and say why |
| `new_customers` (subscription) | 12 numbers: new paying customers in each month of year 1 |
| `churn` (subscription) | share of customers who cancel each month: 0.05 means 5 % |
| `cost_to_win_customer` (subscription) | marketing and sales spend to win one new customer |
| `capacity` | optional: the most units a month, or customers, the business can handle |

Each cost line can carry a `source`, and `sources` holds the source of a single
number (`"churn": "estimate: ..."`). Where the numbers come from, in this order:

1. The user's own quotes, invoices, leases and price lists.
2. Public prices the user can check (a supplier's price list, a payment processor's
   published fees). Name the source.
3. Your estimate, marked as one: the source starts with `estimate` and gives the
   reasoning. The report lists every estimate so the user knows what to replace.

Ask the user, in one message, for what only they know: the price, what they will pay
themselves, rent or salaries they have been quoted, how they will find customers. Use
the price from `startup/buyers/pitch.md` if it exists, and compare it with the
competitors' prices in `startup/competitors.md`. Founders often leave out their own
pay; ask about it.

**The sales forecast is where plans lie.** Month 1 is almost never the plan. If
`/startup-marketing` ran, do not type the forecast: write the rest of the file, then
let the marketing plan fill it in:

```bash
python3 "${CLAUDE_SKILL_DIR}/../startup-marketing/funnel.py" startup/marketing.json --apply startup/numbers.json
```

That writes the new customers per month and the cost to win one (for one-off sales,
the sales per month and the marketing per sale). Without a marketing plan, build the
12 months from how many people the user can actually reach each month and what share
might buy, mark them as estimates, and suggest `/startup-marketing`. If the buyer panel ran, its "would pay now" rate is the best case
(`startup/buyers/results.md`), so a forecast that needs more than that is a red flag.
Show the user the arithmetic behind month 1 and month 12.

## Step 2: run it

```bash
python3 "${CLAUDE_SKILL_DIR}/numbers.py" startup/numbers.json --out startup/numbers.md
```

What-ifs without editing the file:

```bash
python3 "${CLAUDE_SKILL_DIR}/numbers.py" startup/numbers.json --price 39
python3 "${CLAUDE_SKILL_DIR}/numbers.py" startup/numbers.json --volume 0.7
```

The report already includes a price 10 % lower, 20 % fewer sales or new customers,
every cost 15 % higher and, for subscriptions, customers cancelling 50 % more often.

## Step 3: the CFO's note

Add a short section at the top of `startup/numbers.md`, in plain words:

- **The margin**: what each sale or customer leaves, and what a customer is worth
  against what it costs to win them.
- **The number to watch**: the one input that moves the result most, with the
  what-if that proves it.
- **Cash**: how much money the founder needs before it pays for itself, and when it
  comes back.
- **Three ways to improve it**, each with the number it changes and by how much. Run
  the what-if; do not guess.
- Whether the board's money conditions (`startup/board.md`) are met.

## Rules

- Every number in your note comes from the tool's output or an input you can name.
- Prices are before tax; say so if the user's market adds tax on top.
- Say once: this is not financial, tax or legal advice, and an accountant should check
  the structure, payroll and tax before money moves.

## Output

`startup/numbers.json`, `startup/numbers.md`. Next: `/startup-plan` turns these into
the verdict.
