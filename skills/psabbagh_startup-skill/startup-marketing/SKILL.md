---
name: startup-marketing
description: >-
  Works out how the first customers will actually find and buy a new business, and
  what each one costs to win: the first audience, the positioning, two or three
  channels with every step from reaching someone to getting paid, the first 30 days,
  and messages that answer the buyers' objections. A small tool turns the channel plan
  into new customers per month and the cost to win each one, and writes them into the
  numbers, so the forecast comes from a plan instead of a guess. Use when someone asks
  "how do I get customers", "marketing plan", "where do I find my first customers",
  "how much should I spend on ads", "go-to-market", or as step 4 of the startup-skill
  pack.
argument-hint: "[monthly budget, if known]"
---

# startup-marketing

A business no one hears about does not exist, and most forecasts fail on exactly this
line: "and then customers arrive". This step replaces that line with a plan you can
count: who you reach, how many, what share takes each step, what it costs, and how
much of your own time it eats.

What the user typed after the command: `$ARGUMENTS`.

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/funnel.py" startup/marketing.json --buyers startup/buyers/results.json --out startup/marketing-forecast.md
```

If `${CLAUDE_SKILL_DIR}` is not expanded, use this skill's base directory (Claude
Code prints it when the skill loads; in Codex it is usually
`~/.codex/skills/startup-marketing/`). The shape of the plan is in
`marketing.example.json` next to this file.

## Step 1: read the evidence

- `startup/buyers/results.md`: who buys. The segment with the highest buy rate is the
  first audience, and the top objections are what the messages must answer.
- `startup/competitors.md`: how competitors pitch themselves (so you don't sound like
  them), the gap (your positioning), and where they find their customers.
- `startup/board.md` and the Leads, Marketing and Traction memos in `startup/board/`.
- `startup/idea.md`: what the founder brings. People they already know are often the
  cheapest first channel.

If the buyer panel has not run, say so and offer `/startup-buyers` first. Do not
invent an audience. Without `startup/competitors.md`, position against what buyers
use today (the `today` list in `startup/buyers/customer.json`).

**If no buyer would buy**, the offer as tested convinces nobody. Say so, and offer the
buyer skill's "Improve the pitch and re-test" before planning any channel: no channel
fixes an offer nobody wants. If the user wants to carry on anyway, the honest forecast
is zero customers, and the plan will show that as a failing check.

## Step 2: the first audience and the positioning

Name the first audience as narrowly as the evidence allows: the people who would buy
first, not everyone who might one day. Take the group with the highest buy rate in
the panel; when groups tie, the one with the most "probably" answers. Then one line:

```
For <the first audience>, who <their problem, in their words>, <business> is the
<category> that <the gap>, unlike <what they use today>.
```

Offer two or three versions, recommend one, and say which evidence backs it.

## Step 3: the channels

Pick two or three ways to reach the first audience, and say which ones you are not
using and why:

| kind | what it is |
| --- | --- |
| people you know | messages to the founder's own network and their introductions |
| direct outreach | contacting strangers who fit the audience: messages, calls, visits |
| content | posting useful things where the audience already spends time |
| paid ads | paying a platform to show the offer to the audience |
| partners and referrals | other businesses, communities or customers who send buyers |
| marketplaces and listings | app stores, directories, map listings, where buyers already search |

For each channel, ask the founder what they will really do each month, and write it
into `startup/marketing.json`: how many people it reaches each month, every step from
reached to paid with the share that makes it, the spend, and the founder's hours.

- **Things change over the year.** `reach`, each step's `rate`, `cost_per_month` and
  `founder_hours_per_month` take one number or 12 (one per month): rates rise as the
  founder gets better at a channel, and hours move from one channel to the next (do not
  count the same hours twice).
- **Payment can come later.** With a free trial or a long sales cycle, set
  `delay_months` (1 for a 14-day trial) so paying customers land in the month they
  first pay.
- **Every rate has a source.** Give each channel a `source`, and a step its own when
  it comes from somewhere else. Real results the founder already has come first; then
  public benchmarks with a link; otherwise start the source with `estimate:` and give
  the reasoning.

Keep the rates honest. No channel can turn the people it reaches into customers at a
higher rate than the buyer panel's "would buy" share, which is already the best case.
If the founder has never done a channel, its early rates are lower, not higher.

## Step 4: run the forecast

```bash
python3 "${CLAUDE_SKILL_DIR}/funnel.py" startup/marketing.json --buyers startup/buyers/results.json --out startup/marketing-forecast.md
```

It reports, per channel and in total: new customers each month, spend, the cost to win
one customer, and the founder's hours. It flags a channel that converts better than
the panel's best case, a plan that takes more hours than a full-time job, and a month
12 with almost no new customers. Fix the plan, not the flag.

## Step 5: the first 30 days and the messages

Write `startup/marketing.md`:

1. The first audience and the positioning line, with the evidence.
2. The channels, and the ones you are not using and why.
3. **The first 30 days**, week by week: what the founder does to win the first
   customers by hand, before anything is automated. If the forecast takes longer than
   30 days to reach ten customers, say so plainly: that is a finding about reach.
4. **Five messages**, each answering one of the buyers' top objections, written for
   where it will be seen (the first line of a message, an ad headline, the opening of a
   short video).
5. The forecast from `marketing-forecast.md`: new customers per month, the cost to win
   one, the founder's hours.
6. **The three numbers to watch every week** (for example: replies per 100 messages,
   trials started, trials that pay) and the level that means something must change.

## Step 6: feed the numbers

If `startup/numbers.json` exists, or once `/startup-numbers` has written it, put the
forecast into it:

```bash
python3 "${CLAUDE_SKILL_DIR}/funnel.py" startup/marketing.json --apply startup/numbers.json
```

That writes the new customers per month and the cost to win a customer (for one-off
sales: the sales per month and the marketing per sale) and notes where they came from.
Then refresh the numbers report (`numbers.py startup/numbers.json --out
startup/numbers.md`, see `/startup-numbers`) and, if a plan exists, rebuild it. The
plan checks that the numbers match this forecast, so run `--apply` again after any
change to the channels. A plan that wins no customers cannot be applied: that is the
result, and the plan reports it.

## Rules

- No fake reviews, testimonials, follower counts, scarcity or "as seen on". Buyer
  panel quotes are research, never customer quotes in an ad.
- Disclose paid partnerships, and follow the advertising rules of the user's market,
  especially for health and earnings claims. Not legal advice.

## Output

`startup/marketing.json`, `startup/marketing-forecast.md`, `startup/marketing.md`.
Next: `/startup-numbers`.
