---
name: social_media_rank
description: Analysis-only worker. Reads existing raw Reddit/X data and generates `classified_rank.json` using the strict `ClassifiedData` schema. Use for ranking, best-of, compare, or recommendation requests.
---

# Social Media Ranking Skill

This worker converts raw discussion data into a ranked report suitable for the dashboard. It performs **analysis only** — fetching is handled by the orchestrator via `social_media_fetch`.

## Prerequisites

The following files must already exist (produced by `social_media_fetch`):

- `reddit_data.json` and/or `x_data.json`

At least one valid source file must be present. If both are missing, **stop and report failure** — do not attempt to fetch data.

## Step 1: Preflight Validation

Before analysis:

1. Confirm at least one input file exists.
2. Parse each existing file as JSON.
3. Confirm top-level `items` is an array.
4. Ignore malformed items, but keep count of dropped items for transparency.

If both sources are missing or invalid, stop and report the failure.

## Step 2: Lock Output Schema

Read `../social_media_schema/SKILL.md` and treat it as source of truth.

- Output type must match `ClassifiedData`.
- Product entries must match `Product`.
- If this file and schema reference conflict, schema reference wins.

## Step 3: Build Product Candidates

From raw text, identify products/topics that are actually discussed.

- Prefer candidates with repeated mentions across multiple posts.
- Merge obvious aliases into a single canonical product name.
- Keep the final ranked set to 1-5 products.

## Step 4: Rank with Consistent Signals

For each candidate product:

- **mentions**: count relevant references across items.
- **estimated_engagement_score**: sum per-item engagement where item engagement = `max(score, likes, upvotes, 0) + comments + shares`.
- **sentiment**: one of `"Very Positive" | "Positive" | "Mixed" | "Negative"`.
- **consensus**: short evidence-based summary sentence.
- **pros/cons**: distilled from real discussion content.

Sort by strongest combined community support (mentions + engagement + sentiment quality), then assign contiguous ranks starting at 1.

## Step 5: Extract Highlight Quotes

For each ranked product, include up to 3 real quotes:

- Quote must come from raw data text.
- Include real `author` and real `link`.
- Set `context` to `"pro"`, `"con"`, or `"general"`.
- Prefer a balanced set of contexts when evidence exists.

Do not fabricate quotes. If fewer than 3 valid quotes exist, include fewer.

## Step 6: Write Output

Save final JSON to:

- `classified_rank.json`

Required top-level fields:

- `topic`
- `products`
- `key_insights`

## Output Type Contract

Your output MUST match this exact shape. The dashboard detects rank data by checking for `products` (array) + `key_insights` (array). Missing either field = broken tab.

```json
{
  "topic": "best wireless earbuds 2025",
  "products": [
    {
      "rank": 1,
      "name": "Sony WF-1000XM5",
      "sentiment": "Very Positive",
      "mentions": 42,
      "estimated_engagement_score": 8750,
      "consensus": "Widely praised for ANC quality and sound clarity",
      "pros": [
        "Best-in-class ANC",
        "Excellent sound quality",
        "Comfortable fit"
      ],
      "cons": ["Premium price", "Average battery life"],
      "highlight_quotes": [
        {
          "text": "The XM5s completely changed how I listen to music",
          "author": "u/audiophile_reviews",
          "link": "https://reddit.com/r/headphones/comments/abc123",
          "context": "pro"
        }
      ]
    }
  ],
  "key_insights": [
    "Sony and Apple dominate recommendations with 70% of mentions",
    "ANC quality is the most-discussed factor across all posts"
  ]
}
```

### Enum Rules for Rank

- `sentiment` on Product: **Title Case** — `"Very Positive"`, `"Positive"`, `"Mixed"`, `"Negative"`. NEVER use `"positive"` or `"neutral"`.
- `context` on quotes: **lowercase** — `"pro"`, `"con"`, `"general"`. NEVER use `"Pro"` or `"Con"`.

## Final Validation Checklist

- JSON is parseable.
- `products` is an array with rank values `1..N` and no duplicates.
- Every product includes all required fields from `Product`.
- `key_insights` is non-empty and based on observed evidence.
- No null for array fields (`pros`, `cons`, `highlight_quotes`).

## Critical Rules

1. **No external fetch**: do not run new research in this skill.
2. **Schema strictness**: dashboard expects `ClassifiedData` shape exactly.
3. **Evidence-first ranking**: never rank based on assumptions alone.
4. **No fabricated citations**: quotes, authors, and links must be real.
