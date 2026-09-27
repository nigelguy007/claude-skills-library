---
name: social_media_sentiment
description: Analysis-only worker. Reads existing raw Reddit/X data and generates `classified_sentiment.json` with strict `SentimentData` output. Use for sentiment, mood, or positive-vs-negative analysis requests.
---

# Social Media Sentiment Skill

This worker measures community tone and produces evidence-backed sentiment output for the dashboard. It performs **analysis only** — fetching is handled by the orchestrator via `social_media_fetch`.

## Prerequisites

The following files must already exist (produced by `social_media_fetch`):

- `reddit_data.json` and/or `x_data.json`

At least one valid source file must be present. If both are missing, **stop and report failure** — do not attempt to fetch data.

## Step 1: Preflight Validation

1. Parse each available source file.
2. Confirm top-level `items` arrays exist.
3. Skip malformed entries but track skipped-count notes.
4. Stop if both sources are missing or invalid.

## Step 2: Lock Schema and Allowed Labels

Read `../social_media_schema/SKILL.md` before building output.

- Output must match `SentimentData`.
- Allowed labels are only:
  - `"Very Positive"`
  - `"Positive"`
  - `"Mixed"`
  - `"Negative"`

Never invent extra labels.

## Step 3: Classify Item-Level Sentiment

Read each post/comment text and assign one allowed label based on explicit language and context.

- Use evidence from actual text, not title-only shortcuts.
- Prefer `"Mixed"` when meaningful praise and criticism both appear.

## Step 4: Aggregate Sentiment Metrics

Produce:

- `overall_mood` for the full corpus
- `distribution` totals (`very_positive`, `positive`, `mixed`, `negative`)
- `by_source.reddit` and `by_source.x` counts using `SourceSentiment`

Use `0` for missing source buckets rather than null.

## Step 5: Build Product Sentiment Entries

For each major product/topic discussed:

- `overall` sentiment label
- `reddit_sentiment` (or `null` if no Reddit evidence)
- `x_sentiment` (or `null` if no X evidence)
- `evidence_quotes` with up to 3 real quotes

Each evidence quote must include:

- `text`
- `author`
- `link`
- quote-level `sentiment` label

If evidence is sparse, include fewer than 3 quotes instead of fabricating.

## Step 6: Write Output

Save result to:

- `classified_sentiment.json`

## Output Type Contract

Your output MUST match this exact shape. The dashboard detects sentiment data by checking for `distribution` (object) + `by_source` (object). Missing either field = broken tab.

```json
{
  "topic": "iPhone 16 Pro reviews",
  "overall_mood": "Positive",
  "distribution": {
    "very_positive": 15,
    "positive": 38,
    "mixed": 22,
    "negative": 8
  },
  "by_source": {
    "reddit": {
      "very_positive": 10,
      "positive": 25,
      "mixed": 15,
      "negative": 5
    },
    "x": {
      "very_positive": 5,
      "positive": 13,
      "mixed": 7,
      "negative": 3
    }
  },
  "product_sentiments": [
    {
      "name": "iPhone 16 Pro",
      "overall": "Positive",
      "reddit_sentiment": "Positive",
      "x_sentiment": "Mixed",
      "evidence_quotes": [
        {
          "text": "Camera upgrade alone makes it worth it",
          "author": "u/tech_reviewer",
          "link": "https://reddit.com/r/iphone/comments/xyz789",
          "sentiment": "Very Positive"
        }
      ]
    }
  ]
}
```

### Enum Rules for Sentiment

- ALL sentiment labels: **Title Case** — `"Very Positive"`, `"Positive"`, `"Mixed"`, `"Negative"`. NEVER use `"positive"` or `"neutral"`.
- `distribution` keys: **snake_case** — `very_positive`, `positive`, `mixed`, `negative`. NEVER use `veryPositive` or `Very Positive` as keys.
- `by_source` keys: **lowercase** — `reddit`, `x`. NEVER use `Reddit` or `X`.

## Final Validation Checklist

- JSON parse succeeds.
- Top-level object matches `SentimentData`.
- All labels are valid `SentimentLabel` values.
- `product_sentiments` entries include required fields.
- Array fields are arrays (never null/undefined).

## Critical Rules

1. **No external fetch**: analyze only provided raw files.
2. **Evidence over guesswork**: every product label must be explainable from quotes/content.
3. **Strict schema**: the schema reference skill is the only schema source of truth.
4. **No fabricated citations**: quote text, author, and link must exist in raw data.
