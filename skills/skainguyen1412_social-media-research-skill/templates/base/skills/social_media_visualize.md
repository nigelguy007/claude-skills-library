---
name: social_media_visualize
description: Launch the local dashboard that visualizes available `classified_*.json` outputs. Use after one or more analysis workers have generated dashboard-ready JSON files.
---

# Social Media Visualize Skill

This worker launches the local web UI and renders the current classification outputs.

## Preconditions

Before launch:

1. Prefer having at least one of these files available:
   - `classified_rank.json`
   - `classified_sentiment.json`
   - `classified_trend.json`
   - `classified_controversy.json`
   - `classified_discovery.json`
2. If none exist, runtime still launches the dashboard in empty mode; inform the user to run analysis skills to populate tabs.

## Command Execution Flow

Use this sequence for visualization:

1. Ensure at least one classified output exists (for example by running `social_media_rank`, `social_media_sentiment`, `social_media_trend`, `social_media_controversy`, or `social_media_discovery`).
2. Launch dashboard:
   - `sc-research visualize`
3. Optional single-file mode:
   - `sc-research visualize path/to/classified_rank.json`

## Usage

Default auto-detect mode:

```bash
sc-research visualize
```

Single-file mode:

```bash
sc-research visualize path/to/classified_rank.json
```

## Expected Behavior

- Detect available `classified_*.json` files in project root.
- Build/refresh frontend data payload.
- Start local dashboard server (commonly `http://localhost:5173`).
- Enable only tabs backed by available data.

## Output to User

Return:

- server URL
- which data files were detected
- which tabs are available/missing

## Critical Rules

1. **Visualization only**: this skill does not fetch or classify data.
2. **No silent fallback confusion**: if no valid classified files exist, clearly explain that dashboard is running in empty mode.
3. **Use actual runtime URL**: if default port is taken, report the new port.

## Troubleshooting

| Issue               | Symptom                               | Action                                                                |
| ------------------- | ------------------------------------- | --------------------------------------------------------------------- |
| No classified files | empty dashboard (server still starts) | run a worker skill first (rank/sentiment/trend/controversy/discovery) |
| Port already in use | server starts on another port         | report actual URL shown by runtime                                    |
| Malformed JSON file | tab fails to render or command errors | regenerate that specific `classified_*.json` file                     |
