---
name: product-gap-finder
description: Find a product's real gaps from user evidence - Trustpilot and G2 low-star reviews, Reddit threads, YouTube comments, independent reviews and a last30days social sweep - then rank them by severity with concrete fixes and a priority order. Use when the user asks "where could <product> be better", "what do users complain about in <product>", "identify gaps in this app", "check reddit for <product> problems", or wants openings for a competitor.
---

# Product gap finder

Turn scattered user complaints into a ranked list of product gaps with fixes. It
works best after `reverse-engineer-website` has produced `reports/<target>/app_spec.md`,
but it also runs standalone.

Output: `reports/<target>/gaps.md`, linked from the repo README.

## Principles

- **Gaps come from users, not from your opinion.** Every gap needs at least one
  quoted, attributed piece of evidence. Ideas you inferred without evidence go in a
  clearly labeled section.
- **Grade your sources.** Every evidence table needs a bias column: affiliate links
  (`?via=`, "10% off with my link"), competitor-authored reviews, curated testimonials,
  tiny samples. Say when negatives are a small fraction of total reviews.
- **A cluster beats volume.** Ten reviews that independently describe the same failure
  point to a structural problem, even against 1,000 five-star reviews.
- **Silence is a finding.** If the only social content is affiliate promo, report it.
  That's what an acquisition engine looks like, and it means the product has no
  organic feedback channel.
- **Never get around bot protection.** Reddit blocks scripted and JSON access from
  most sandboxes. Don't switch user agents, mirrors or proxies to get past a block;
  use the sources below.

## Evidence sources (in this order)

1. **Trustpilot, low-star filter.** Scrape
   `https://www.trustpilot.com/review/<domain>?stars=1&stars=2` with Firecrawl
   (`firecrawl_scrape`, markdown). Plain curl gets a stub page. Capture each review's
   date, title, the key quote, and the company reply. Company replies often *admit*
   the root cause ("campaigns paused in the backend can process tasks without sending").
   Also note Trustpilot's own banners ("hasn't invited customers recently",
   "typically takes over 1 month to reply").
2. **G2:** `https://www.g2.com/products/<slug>/reviews` via Firecrawl. These are often few
   but verified.
3. **Product Hunt:** `/products/<slug>/reviews`. Usually launch-era praise; check for
   "what needs improvement".
4. **Reddit.** Run WebSearch for `<product> reddit review`. Search engines often index
   archive/snapshot mirrors of threads (for example `reddit.sentinel-team.org`
   snapshots) that Firecrawl can read. The comments are the evidence; the post itself
   is often affiliate content.
5. **`/last30days <product>`** (if installed). Social sweep across Reddit, YouTube
   (with transcripts and comments), TikTok, Instagram and HN. Use `--trustpilot-domain`.
   The top YouTube comments on the vendor's *own* videos are high signal. Expect
   mostly promo: say so instead of padding.
6. **Independent and competitor reviews.** Run WebSearch for
   `<product> review <year> honest cons limitations`, excluding the vendor's domain.
   Competitor blogs (e.g. "<product> alternatives") often collect the vendor's
   low-star reviews. Use them, but tag them as competitor-authored.
7. **The vendor's own help center and FAQ.** An article titled "Why was I charged if I
   cancelled" tells you that ticket is common.

## Analysis

Cluster the complaints and map each cluster to a mechanism in the product:

| Common cluster | What to check |
|---|---|
| Usage meter ("hours"/"credits") runs out fast | Is cost visible before the action? Per-agent caps? Shared pool across workspaces? Published top-up price? Did pricing change from "unlimited"? |
| Billing/refund distrust | Confirmation step before charging? "Trial" vs refund-window wording? Auto-upgrades? Add-ons that contradict a "one plan" headline? |
| Silent failure | Does the product burn usage on tasks that produced no external effect? Broken-integration alerts? |
| Memory/continuity | Plans or campaigns forgotten between sessions; duplicate outreach |
| Context bleed | Brand voice or data leaking across workspaces in one account |
| Brand safety | Public output that harmed the customer; approval fatigue |
| Offboarding | Agents still running after cancel or disconnect |
| Support | Bot pretending to be 24/7 humans; escalations that never close; credits instead of fixes |
| Scope | No custom workflows; redundant roles; platform-ToS risk (e.g. LinkedIn automation); accuracy-sensitive work; enterprise readiness |

## gaps.md format

1. **Evidence base table:** source | what it is | bias. Plus a one-line read and any
   coverage you couldn't get (and why).
2. **Tier 1: costs customers and money.** Each gap gets **Evidence** (quotes with
   source and date), **Gap** (one or two sentences), and **Fix** (concrete, shippable).
3. **Tier 2: output quality and control.**
4. **Tier 3: product scope.** A table: gap | evidence | opportunity (also openings for competitors).
5. **Tier 4: support operations.**
6. **Priority order (impact ÷ effort).** Put cheap trust and transparency fixes first.
7. **Counterpoint.** How small the negative sample is, and which failures are
   category-wide rather than vendor-specific.
8. **Sources:** the URLs you used.

Lead the user-facing reply with the single most important finding, not a summary of
the method. Point out where the evidence is thin rather than inflating it.
