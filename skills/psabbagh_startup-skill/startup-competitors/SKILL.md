---
name: startup-competitors
description: >-
  Finds out how buyers already solve the problem a business idea targets, from public
  sources only, every fact linked: the direct competitors, the other products people
  use for the same job, and the do-it-yourself way, with what each charges, how they
  pitch themselves and what their own customers complain about. Ends with what buyers
  already pay to solve this, the gap nobody fills, and who could copy the idea
  fastest. Use when someone asks "who are my competitors", "is this market crowded",
  "what else is out there", "what do others charge", "find the gap", or as step 2 of
  the startup-skill pack.
argument-hint: "[city or market, if it matters]"
---

# startup-competitors

Every buyer already solves this problem somehow, even if the answer is "I live with
it". This step finds out how, what they pay for it, and what they hate about it. It is
the one step in the pack built on real-world evidence instead of simulation, so the
rule is simple: if you cannot link it, it does not go in.

What the user typed after the command: `$ARGUMENTS`.

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/competitors.py" check startup/competitors.csv
```

If `${CLAUDE_SKILL_DIR}` is not expanded, use this skill's base directory (Claude
Code prints it when the skill loads; in Codex it is usually
`~/.codex/skills/startup-competitors/`). The shape of the CSV is in
`competitors.example.csv` next to this file (made-up companies).

This step needs web search. In Claude Code that is WebSearch and WebFetch. In Codex,
web search has to be on (start Codex with `codex --search`). Without it, say so and
stop: never fill the table from memory.

## The rules

- **Public sources only, every fact linked, every page dated.** Websites, price
  pages, app store and map listings, review sites, forums, news. If a page cannot be
  reached, say so.
- **Never invent** a competitor, a price, a rating, a review or a quote.
- **Read pages as a person would.** No bulk scraping, and respect each site's terms.
- **Facts come from each company's own pages.** Most "best X for Y" lists are written
  by one of the competitors. Use them to find names, never for prices or verdicts.
- **If a page refuses to load, say so.** A search result's excerpt can be used only as
  an excerpt, labelled as one, never as a full quote.
- **Quotes are short, word for word, and linked.** They are research, never
  testimonials.

## Step 1: the job, and who already does it

Read `startup/idea.md` (`/startup-board` writes it; if it is missing, write it as that
skill's step 0 says). Write down the job the customer wants done, in plain words.
It is your paraphrase, not a quote, so never present it as something a buyer said.
Then search the way a buyer would ("best <thing> for <who>", "<thing> alternative",
"<thing> price", and for a local business, the map for that area). Aim for 5 to 10:

| type | what it means |
| --- | --- |
| `direct` | the same thing, sold to the same buyer |
| `indirect` | a different product people use for the same job |
| `diy` | how buyers solve it without buying anything new: a spreadsheet, a family member, doing it by hand, or nothing |

Always include the do-it-yourself way. It is often the real competitor. Look for
evidence that buyers really do it (forum threads, trade press, community posts). If
you find none, describe it in `competitors.md` as an assumption, without a row: the
CSV only holds what you can link.

## Step 2: the facts

One row per competitor in `startup/competitors.csv`, with the date you checked:

- **`url`**: the page the price comes from (or the main page if there is no price).
  When the headline or the rating come from other pages, list those links under the
  competitor in `competitors.md`.
- **`price`**: what this buyer would really pay, per unit, for the closest equivalent:
  - an add-on that needs a base plan: the add-on plus the cheapest base plan;
  - several tiers: the cheapest tier that does what the new business does;
  - pay-per-use: the price at typical use for this buyer, with the arithmetic in
    `includes`;
  - the company's own pages disagree: use the price page, and note the conflict;
  - no public price ("book a demo"): leave it empty.
- **`includes`**: what that price includes, so prices compare like with like.
- **`headline`**: their own headline, copied word for word. If the price page only
  says "Pricing", take the home page's.
- **`rating`** and **`reviews`**: from one public review site, named in
  `competitors.md`. Skip a rating that belongs to a parent product, and say when a
  rating rests on very few reviews.

Then:

```bash
python3 "${CLAUDE_SKILL_DIR}/competitors.py" check startup/competitors.csv
python3 "${CLAUDE_SKILL_DIR}/competitors.py" table startup/competitors.csv --out startup/competitors-table.md
```

`check` refuses a row with no link or no date. Fix the row, never the rule.

## Step 3: what their customers complain about

For the 3 to 5 closest competitors, read their reviews: the low ratings first, then
the "good, but..." ones. Linked forum posts and community threads count too. Group
the complaints into themes, count them, and keep one or two short linked quotes per
theme. Mark a theme as thin when it rests on fewer than three reviews. Few or no
reviews is itself a finding: say so (often it means a young or tiny market).

## Step 4: write it up

Write `startup/competitors.md`:

1. **What buyers already pay to solve this today**, in one or two sentences. Money
   people already spend on the problem is the strongest sign they would pay for a
   better answer; if nobody pays anything, say that too.
2. The table from `competitors-table.md`, and the price range of the direct
   competitors (the range that matters for pricing), with any links for headlines and
   ratings that came from other pages.
3. A positioning map in words: two things this buyer cares about (price and effort,
   speed and quality...) and where each competitor sits.
4. The complaints, most common first, with links.
5. **The gap**: what nobody does well that this business could, tied to the evidence.
   If there is no gap, say so plainly. That is the most useful thing this step can
   find.
6. **The copycat risk**: who could copy the idea fastest, and how.

## Hand it on

Tell the user the gap (or that there is none) in two lines, then hand the evidence to
the next steps:

- **Buyers** (`/startup-buyers`): the real alternatives become the profile's `today`
  list, the recurring complaints go into `known_objections`, and the price range is
  what buyers will compare the offer with.
- **Marketing** (`/startup-marketing`): competitors' headlines show how not to sound,
  and the gap is the positioning.
- **Numbers** (`/startup-numbers`): competitors' prices are a check on the planned price.

## Output

`startup/competitors.csv`, `startup/competitors-table.md`, `startup/competitors.md`.
Next: `/startup-buyers`.
