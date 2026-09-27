---
name: social_media_fetch
description: The sole data-fetching authority for the research pipeline. Handles CLI execution, data freshness checks, and output validation. Always called by the orchestrator — never by worker skills directly.
---

# Social Media Fetch Skill

This is the **only** skill that runs `sc-research research` CLI commands. No other skill or command should execute fetch commands. The orchestrator delegates here; worker skills consume the output.

## Inputs (provided by orchestrator)

The orchestrator will specify:

- **topic**: the search query string
- **depth**: `quick` or `deep`
- **mode**: `research` (default) or `discovery`
- **source** (optional): `reddit`, `x`, or omit for all available
- **date range** (optional): `from` / `to` as `YYYY-MM-DD`

## Outputs

- `reddit_data.json` (project root)
- `x_data.json` (project root)

At least one output file must be produced for a successful fetch.

---

## Step 1: Check Data Freshness

Before running a new fetch, check whether existing raw files can be reused:

1. Does `reddit_data.json` or `x_data.json` exist?
2. Is the file valid JSON with a top-level `items` array?
3. Does the `query` field match the current topic (same or equivalent intent)?
4. Does the `dateRange` match the requested window (if provided)?
5. Does the source scope match (e.g., if user asked for Reddit-only, is Reddit data present)?

**If all checks pass** → skip fetch, use existing data and report "Using cached data."
**If any check fails** → proceed with fresh fetch.

## Step 2: Build CLI Command

Construct the command based on inputs:

**Standard analysis routes:**

```bash
sc-research research:deep "TOPIC"
```

**Quick-answer route:**

```bash
sc-research research "TOPIC" --source=reddit
```

**Discovery route (broad weekly):**

```bash
sc-research research:deep "DISCOVERY_WEEKLY" --mode=discovery
```

**Discovery route (topic-focused):**

```bash
sc-research research:deep "TOPIC" --mode=discovery
```

Append optional flags only when provided by the orchestrator:

- `--source=reddit|x|both`
- `--from=YYYY-MM-DD --to=YYYY-MM-DD`
- `--mode=discovery`

When `--source` is omitted, runtime uses all sources whose API keys are available.

## Step 3: Execute and Validate

Run the constructed command, then validate each produced file:

1. File exists.
2. JSON is parseable.
3. Top-level `items` exists and is an array.
4. `query` and `dateRange` are present.
5. Items include usable fields (`text`, `author`, `url`, `date`, `engagement`).

If a source was explicitly requested but its file is missing or malformed, report the failure clearly.

## Step 4: Return Fetch Summary

Return to the orchestrator:

- topic
- mode used (`research` / `discovery`)
- sources fetched
- date range used
- item count per source
- any warnings (missing source, partial results, cached data reuse)

---

## Discovery Fetch Behavior (runtime details)

When `--mode=discovery` is used, runtime behavior differs by topic:

1. Topic is exactly `DISCOVERY_WEEKLY` with Reddit enabled → fetches `r/popular/top` with `t=week`, limit `25`.
2. Other topics in discovery mode with Reddit enabled → maps topic to candidate subreddits, then fetches top posts or searches per subreddit.
3. X source → runs normal X search flow regardless of discovery mode.

## Error Handling

| Scenario                           | Symptom                               | Action                                               |
| ---------------------------------- | ------------------------------------- | ---------------------------------------------------- |
| Missing `OPENAI_API_KEY`           | Auth failure on Reddit fetch          | Set valid `OPENAI_API_KEY` in `.sc-research`         |
| Missing `XAI_API_KEY`              | X file missing while Reddit succeeds  | Set `XAI_API_KEY` in `.sc-research` to enable X      |
| No relevant results                | `items` is empty                      | Broaden topic keywords and retry                     |
| Rate limit / transient API failure | Timeout or provider error             | Wait, then retry once with same parameters           |
| Malformed output                   | JSON parse failure or missing `items` | Re-run fetch; if repeated, report failure explicitly |

## Critical Rules

1. **No analysis here** — do not rank, classify, or generate classified files.
2. **No fabricated data** — do not create synthetic posts.
3. **This is the only fetch point** — worker skills must never run fetch commands.
4. **Fail loudly** — do not continue as if fetch succeeded when validation fails.
