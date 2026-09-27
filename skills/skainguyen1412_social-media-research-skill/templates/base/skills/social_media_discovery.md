---
name: social_media_discovery
description: Analysis-only worker. Reads existing raw Reddit/X data to find emerging or viral themes and generates `classified_discovery.json` with strict `DiscoveryData` output.
---

# Social Media Discovery Skill

This worker clusters noisy social discussions into trend themes that can be visualized. It performs **analysis only** — fetching is handled by the orchestrator via `social_media_fetch`.

## Prerequisites

The following files must already exist (produced by `social_media_fetch`):

- `reddit_data.json` and/or `x_data.json`

At least one valid source file must be present. If both are missing, **stop and report failure** — do not attempt to fetch data.

**Note on discovery data**: For best results, the orchestrator should have fetched with `--mode=discovery`. This skill analyzes whatever raw data exists — it does not control how data was fetched.

## Step 1: Preflight Validation

1. Parse each available source file.
2. Confirm top-level `items` arrays.
3. Skip malformed records and track skipped count.
4. Stop if no usable posts remain.

## Step 2: Lock Schema

Read `../social_media_schema/SKILL.md` and follow `DiscoveryData` and `DiscoveryTopic` exactly.

Important enum constraints:

- `sentiment`: `"positive" | "negative" | "neutral" | "mixed"`
- `platform`: `"reddit" | "x"`

## Step 3: Cluster Topics

Create 3-8 meaningful topic clusters from actual post content.

- Merge near-duplicate themes.
- Ignore clear spam/noise.
- Prefer clusters with both relevance and engagement.

Each cluster should have:

- `id` (stable slug-like id)
- `topic_name`
- `description`
- `category`

## Step 4: Compute Topic Metrics

For each cluster:

- `engagement_score` = sum of per-item engagement where item engagement =
  `max(score, likes, upvotes, 0) + comments + shares`
- `sentiment` using allowed discovery sentiment enum

Also compute top-level:

- `total_posts_analyzed`
- `period` (always string, derived from available date range)

## Step 5: Attach Evidence Content

For each topic include:

- `key_posts` (high-signal posts, preferably 1-3 entries)
- `highlight_comments` (up to 3 real excerpts with author/link/platform)

Use real source text only. If evidence is limited, include fewer entries instead of fabricating.

## Step 6: Write Output

Save strict JSON to:

- `classified_discovery.json`

## Output Type Contract

Your output MUST match this exact shape. The dashboard detects discovery data by checking for `trending_topics` (array). Missing this field = broken tab.

**WARNING**: Discovery uses DIFFERENT enum casing than other skills. Everything is **lowercase** here.

```json
{
  "topic": "AI tools 2025",
  "period": "2025-01-01 to 2025-01-31",
  "total_posts_analyzed": 156,
  "trending_topics": [
    {
      "id": "local-llm-hosting",
      "topic_name": "Local LLM Hosting",
      "description": "Growing interest in running language models locally using consumer hardware",
      "category": "Technology",
      "engagement_score": 4500,
      "sentiment": "positive",
      "key_posts": [
        {
          "title": "I got Llama 3 running on my M3 MacBook and it's incredible",
          "url": "https://reddit.com/r/LocalLLaMA/comments/mno345",
          "platform": "reddit",
          "engagement": 2100
        }
      ],
      "highlight_comments": [
        {
          "text": "The performance gains with quantization are impressive",
          "author": "u/ml_enthusiast",
          "link": "https://reddit.com/r/LocalLLaMA/comments/mno345/comment/abc",
          "platform": "reddit"
        }
      ]
    }
  ]
}
```

### Enum Rules for Discovery (ALL LOWERCASE)

Discovery is the **only** classified type that uses lowercase sentiment values. Do NOT copy Title Case from rank/sentiment/controversy.

- `sentiment` on DiscoveryTopic: **lowercase** — `"positive"`, `"negative"`, `"neutral"`, `"mixed"`. NEVER use `"Positive"`, `"Mixed"`, or `"Very Positive"`.
- `platform` on key_posts and highlight_comments: **lowercase** — `"reddit"`, `"x"`. NEVER use `"Reddit"`, `"X"`, or `"twitter"`.
- `id`: use a **slug-like** identifier (e.g., `"local-llm-hosting"`), not a UUID or number.

## Final Validation Checklist

- JSON parse succeeds.
- Output matches `DiscoveryData` shape.
- All enum values are valid and correctly cased.
- Array fields are arrays (never null/undefined).
- Every quote/comment/link is traceable to raw input data.

## Critical Rules

1. **No external fetch**: do not run data collection here.
2. **No fabricated clusters or quotes**: everything must map to real evidence.
3. **Schema strictness**: the schema reference skill is authoritative.
4. **Graceful fallback**: use empty arrays for missing optional evidence; never invent content.
