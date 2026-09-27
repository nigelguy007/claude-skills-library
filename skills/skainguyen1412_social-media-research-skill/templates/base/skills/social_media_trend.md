---
name: social_media_trend
description: Analysis-only worker. Reads existing raw Reddit/X data and generates `classified_trend.json` with strict `TrendData` output. Use for timeline, growth/decline, and discussion-peak analysis requests.
---

# Social Media Trend Skill

This worker converts raw discussion timestamps into a trend timeline with key moments. It performs **analysis only** — fetching is handled by the orchestrator via `social_media_fetch`.

## Prerequisites

The following files must already exist (produced by `social_media_fetch`):

- `reddit_data.json` and/or `x_data.json`

At least one valid source file must be present. If both are missing, **stop and report failure** — do not attempt to fetch data.

## Step 1: Preflight and Date Parsing

1. Parse each available source file and validate `items` arrays.
2. For each item, parse date from:
   - `date` (preferred)
   - fallback `createdAt` (legacy/test data)
3. Skip items with invalid/missing date values; track skipped count.
4. If no valid dated items remain, stop and report failure.

## Step 2: Determine Date Span and Granularity

From earliest to latest valid date:

- `<= 31` days -> `granularity = "day"` (`YYYY-MM-DD`)
- `32-120` days -> `granularity = "week"` (`YYYY-Www`, ISO week)
- `> 120` days -> `granularity = "month"` (`YYYY-MM`)

Set `date_range.from` and `date_range.to` from actual observed dates.

## Step 3: Build Timeline Buckets

Build a continuous timeline across the full date range.

For each bucket:

- `post_count`
- `reddit_posts`
- `x_posts`
- `total_engagement`

Use engagement formula per item:

`max(score, likes, upvotes, 0) + comments + shares`

Include low-activity buckets (including zero-count buckets inside the range) so trend shape is clear.

## Step 4: Identify Key Moments

Select 3-5 moments from strongest engagement spikes and notable discussion events.

Each `key_moments` entry must include:

- `date` (real date from data)
- `event` (short factual description)
- `significance` (`"high" | "medium" | "low"`)
- optional `url` from source post

Prefer evidence-backed moments over generic commentary.

## Step 5: Write Output

Read `../social_media_schema/SKILL.md` and output strict `TrendData` JSON to:

- `classified_trend.json`

## Output Type Contract

Your output MUST match this exact shape. The dashboard detects trend data by checking for `date_range` (object) + `timeline` (array). Missing either field = broken tab.

```json
{
  "topic": "AI coding assistants",
  "date_range": {
    "from": "2025-01-01",
    "to": "2025-01-31"
  },
  "granularity": "day",
  "timeline": [
    {
      "period": "2025-01-01",
      "post_count": 12,
      "total_engagement": 3400,
      "reddit_posts": 8,
      "x_posts": 4
    },
    {
      "period": "2025-01-02",
      "post_count": 7,
      "total_engagement": 1850,
      "reddit_posts": 5,
      "x_posts": 2
    }
  ],
  "key_moments": [
    {
      "date": "2025-01-15",
      "event": "Major product update announcement drove spike in discussion",
      "significance": "high",
      "url": "https://reddit.com/r/programming/comments/def456"
    }
  ]
}
```

### Period Format Rules

The `period` field in each timeline entry MUST match the selected granularity:

| Granularity | Period Format | Example        |
| ----------- | ------------- | -------------- |
| `"day"`     | `YYYY-MM-DD`  | `"2025-01-15"` |
| `"week"`    | `YYYY-Www`    | `"2025-W03"`   |
| `"month"`   | `YYYY-MM`     | `"2025-01"`    |

### Enum Rules for Trend

- `significance` on KeyMoment: **lowercase** — `"high"`, `"medium"`, `"low"`. NEVER use `"High"`, `"Medium"`, `"Low"`.
- All numeric fields (`post_count`, `total_engagement`, `reddit_posts`, `x_posts`) must be numbers, NEVER strings or null.

## Final Validation Checklist

- JSON parse succeeds.
- Object matches `TrendData` shape.
- `timeline` entries use period format consistent with selected granularity.
- Numeric fields are numbers (not strings/null).
- `key_moments` only use allowed significance values.

## Critical Rules

1. **No external fetch**: analyze existing raw files only.
2. **No invented dates/events**: every bucket and key moment must come from real data.
3. **Schema strictness**: the schema reference skill is authoritative.
4. **Graceful degradation**: skip bad records; never crash the whole report for a few malformed items.
