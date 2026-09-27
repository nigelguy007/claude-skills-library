---
name: using_social_media_research
description: This skill should be used when the user asks what people on Reddit/X think about a topic, including requests like "best/top recommendation", "compare options", "sentiment", "trend over time", "controversy/debate", "what is trending", "quick summary", or "full analysis". It acts as the entrypoint router and delegates to the correct fetch and worker skills.
---

# Using Social Media Research (Orchestrator)

This skill is the **single entrypoint** for the entire research pipeline.

## Pipeline Flow (always follow this order)

```
User Question
  → Step 1: Resolve Intent (pick the right worker)
  → Step 2: Fetch Data (delegate to social_media_fetch)
  → Step 3: Classify (delegate to the chosen worker skill)
  → Step 4: Present Results
  → Step 5: Visualize (optional — run sc-research visualize)
```

**No other skill or command should run fetch commands directly.** Only this orchestrator decides when and how to fetch.

## Auto-Trigger Cues

Activate this skill when the user's request maps to social-media research intent:

- "What do people think about X?"
- "Best X according to Reddit?"
- "Compare A vs B from social media feedback"
- "How is sentiment for X?"
- "Is X trending recently?"
- "What are people debating about X?"
- "Give me a quick social media summary"
- "Full analysis of X"

## Core Contract

- Run exactly **one** worker by default.
- Run **multiple** workers only when the user explicitly asks for multi-view output ("full analysis", "all views", "run everything").
- Always use **deep** fetch for worker analysis routes.
- Use **quick** fetch only for explicit quick-answer requests.
- If intent is ambiguous after all routing rules, default to **quick-answer mode** (direct text response, no classified file).
- **Delegate all fetching to `social_media_fetch`** — never run `sc-research research` commands directly from this skill or any worker.

---

## Step 1: Resolve Intent (Strict Precedence)

Apply rules top-to-bottom. First match wins.

1. **Explicit multi-analysis request**
   - Trigger: "full analysis", "all views", "run everything", or equivalent.
   - Run all four workers in order: `social_media_rank` → `social_media_sentiment` → `social_media_trend` → `social_media_controversy`.
   - Include `social_media_discovery` only if user also asks about emerging/viral topics.

2. **Explicit template request**
   - Trigger: user names a specific analysis ("sentiment", "trend", "controversy", "discovery", "rank").
   - Route directly to that single worker.

3. **Explicit quick-answer request**
   - Trigger: "quick answer", "short summary", "brief".
   - Use quick-answer mode (no classified file, direct text response).

4. **Inferred strongest intent**
   - Map by primary question keywords (see table below).

5. **Fallback**
   - Default to **quick-answer mode** — synthesize a 3–5 sentence answer directly from the raw data. Do not produce a `classified_*.json` file.

### Intent → Worker Mapping

| Route        | Trigger phrases                                   | Worker skill               | Output file                   |
| ------------ | ------------------------------------------------- | -------------------------- | ----------------------------- |
| Rank         | best, top, compare, recommendation, which one     | `social_media_rank`        | `classified_rank.json`        |
| Sentiment    | feel, sentiment, opinion, positive/negative       | `social_media_sentiment`   | `classified_sentiment.json`   |
| Trend        | timeline, over time, peak, growth, decline        | `social_media_trend`       | `classified_trend.json`       |
| Controversy  | debate, divisive, disagreement, polarizing, vs    | `social_media_controversy` | `classified_controversy.json` |
| Discovery    | trending topics, viral, discover themes, clusters | `social_media_discovery`   | `classified_discovery.json`   |
| Quick Answer | quick answer, short summary, brief                | _(none)_                   | direct text answer            |

### Source Preference Detection

| User wording                          | Source value                                            |
| ------------------------------------- | ------------------------------------------------------- |
| "on Reddit", "subreddit", "Redditors" | `reddit`                                                |
| "on X", "on Twitter", "tweets"        | `x`                                                     |
| no explicit source                    | _(omit — runtime uses all sources with valid API keys)_ |

## Step 2: Fetch Data (delegate to `social_media_fetch`)

Read the `social_media_fetch` skill and follow its instructions to fetch raw data. Provide it with:

- **topic**: the user's topic string
- **depth**: `deep` for all worker routes, `quick` for quick-answer route
- **mode**: `discovery` for the discovery route, `research` for all others
- **source**: from source preference above (omit if not specified)
- **date range**: `from`/`to` if user provided dates

The fetch skill handles data freshness checks, CLI execution, and output validation. Do not duplicate that logic here.

After fetch completes, confirm that at least one raw data file (`reddit_data.json` / `x_data.json`) exists and is valid before proceeding.

## Step 3: Classify (delegate to worker skill)

Based on the route chosen in Step 1:

- **Single route**: Read the selected worker skill's instructions (e.g., `social_media_rank`) and follow them to produce the matching `classified_*.json` file.
- **Multi-route** (full analysis): Read and execute each worker skill in order. Each worker reads existing raw data and writes its own output file independently.
- **Quick answer**: Synthesize a 3–5 sentence answer directly from the raw data. Do not produce any `classified_*.json` file.

### CRITICAL: Schema Enforcement

Before writing ANY `classified_*.json` file, you MUST:

1. Read `social_media_schema` skill — it is the **single source of truth** for JSON shapes.
2. Each worker skill contains an **Output Type Contract** section with a concrete JSON example — match it exactly.
3. Use ONLY the enum values listed in the schema. Wrong casing = broken dashboard.

The dashboard auto-detects each classified type by checking for specific field signatures. If required fields are missing or misnamed, the dashboard will **not show that tab at all**.

## Step 4: Present Results

- Confirm the expected `classified_*.json` file(s) exist and are parseable.
- Present results matching what was requested:
  - Single-route → single output summary
  - Multi-route → sectioned summary per route
  - Quick answer → 3–5 sentence direct text

## Step 5: Visualize (optional)

Suggest running `sc-research visualize` to view results in the web dashboard. The visualize command:

1. Reads all `classified_*.json` files in the working directory.
2. Validates each against the expected schema.
3. Merges them into a single `data.json` for the dashboard.
4. Opens the dashboard at `localhost:5173`.

## Safety Rules

- If a request mixes intents without explicit multi-analysis wording, pick the single strongest route and state what was chosen.
- Never fabricate output files or data.
- Never silently switch from deep to quick fetch for worker routes.
- Each `classified_*.json` file is independent — producing one never requires producing another.

## File Map

| File                          | Producer                   |
| ----------------------------- | -------------------------- |
| `classified_rank.json`        | `social_media_rank`        |
| `classified_sentiment.json`   | `social_media_sentiment`   |
| `classified_trend.json`       | `social_media_trend`       |
| `classified_controversy.json` | `social_media_controversy` |
| `classified_discovery.json`   | `social_media_discovery`   |
