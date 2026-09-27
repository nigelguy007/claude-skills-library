---
name: social_media_controversy
description: Analysis-only worker. Reads existing raw Reddit/X data to identify divisive topics and generates `classified_controversy.json` with strict `ControversyData` output. Use for debate, disagreement, or polarizing-topic requests.
---

# Social Media Controversy Skill

This worker maps where social media opinions conflict and presents both sides with evidence. It performs **analysis only** — fetching is handled by the orchestrator via `social_media_fetch`.

## Prerequisites

The following files must already exist (produced by `social_media_fetch`):

- `reddit_data.json` and/or `x_data.json`

At least one valid source file must be present. If both are missing, **stop and report failure** — do not attempt to fetch data.

## Step 1: Preflight Validation

1. Parse each available source file.
2. Confirm top-level `items` arrays.
3. Skip malformed records and track skipped count.
4. Stop if no usable discussion text remains.

## Step 2: Lock Output Schema

Read `../social_media_schema/SKILL.md` and treat `ControversyData` as source of truth.

Required top-level fields:

- `topic`
- `overall_divisiveness`
- `controversies`

## Step 3: Identify Genuine Controversies

Find 2-5 topics with clear opposing viewpoints.

Good signals:

- explicit disagreement language
- conflicting claims about the same product/theme
- platform splits (Reddit vs X)
- high-engagement threads arguing opposite positions

Do not manufacture controversy where consensus is strong.

## Step 4: Structure Each Controversy

For each controversy:

- `topic`: concise debate label
- `heat_score`: `0-100` intensity score based on volume + engagement + disagreement strength
- `divisiveness`: `"Low" | "Medium" | "High"`
- `side_a` and `side_b` each with:
  - `position`
  - `supporter_count` (best estimate; `0` if unknown)
  - `sample_quotes` (up to 3 real quotes)

Quote rules:

- Use real text, real author, real link.
- Prefer diverse arguments per side (not duplicates).
- If limited evidence exists, include fewer quotes instead of fabricating.

## Step 5: Set Overall Divisiveness

Set `overall_divisiveness` from the full set:

- `"High"` if multiple high-heat, strongly split controversies exist
- `"Medium"` for mixed or moderate splits
- `"Low"` if disagreements are minor or sparse

## Step 6: Write Output

Save strict JSON to:

- `classified_controversy.json`

## Output Type Contract

Your output MUST match this exact shape. The dashboard detects controversy data by checking for `overall_divisiveness` (string) + `controversies` (array). Missing either field = broken tab.

```json
{
  "topic": "AI replacing developers",
  "overall_divisiveness": "High",
  "controversies": [
    {
      "topic": "Will AI make junior devs obsolete?",
      "heat_score": 82,
      "divisiveness": "High",
      "side_a": {
        "position": "AI will eliminate most entry-level coding jobs within 5 years",
        "supporter_count": 45,
        "sample_quotes": [
          {
            "text": "Why would a company hire juniors when Copilot can do 80% of their work?",
            "author": "u/startup_cto",
            "link": "https://reddit.com/r/programming/comments/ghi789"
          }
        ]
      },
      "side_b": {
        "position": "AI is a tool that augments developers, not replaces them",
        "supporter_count": 62,
        "sample_quotes": [
          {
            "text": "Every generation says the same thing. We still need people who understand the problem domain.",
            "author": "u/senior_eng_20yr",
            "link": "https://reddit.com/r/ExperiencedDevs/comments/jkl012"
          }
        ]
      }
    }
  ]
}
```

### Enum Rules for Controversy

- `overall_divisiveness`: **Title Case** — `"Low"`, `"Medium"`, `"High"`. NEVER use `"low"`, `"medium"`, `"high"`.
- `divisiveness` on each controversy: **Title Case** — same as above.
- `heat_score`: integer `0-100`. NEVER use a value outside this range.
- `supporter_count`: integer `>= 0`. Use `0` if unknown, NEVER use null.

## Final Validation Checklist

- JSON parse succeeds.
- Object matches `ControversyData` shape.
- Enum values use allowed casing exactly.
- Array fields are arrays (never null/undefined).
- Every quote references real source evidence.

## Critical Rules

1. **No external fetch**: analyze existing data only.
2. **No fabricated arguments**: only report controversies present in source text.
3. **No fabricated citations**: quote text, author, and link must be real.
4. **Schema strictness**: if instructions conflict with schema reference, schema reference wins.
