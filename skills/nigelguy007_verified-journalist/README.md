# Verified Journalist

An AI journalist that researches a topic, writes an article and then **checks it against its
own sources before anyone reads it**. Every direct quote must appear verbatim in a fetched page.
Every citation must point to a real source. Every factual sentence is checked against the
research notes. If a problem survives the revision rounds, the article is marked `needs_review`
with the specific problems listed. It is never passed off as `ready`.

A rewrite of the [AI Journalist Agent](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/advanced_ai_agents/single_agent_apps/ai_journalist_agent)
from awesome-llm-apps, built to close the gaps that make that demo unsafe to publish from.

## What changed compared with the original

| Problem in the original | What this version does |
|---|---|
| "Never make up facts" is only a line in a prompt; nothing checks it | Deterministic checks: quotes matched verbatim against source text, citation numbers range-checked, uncited figures flagged. A separate LLM pass checks each sentence against the cited notes |
| The writer can invent quotes and URLs | Research notes keep only facts whose supporting quote is literally in the page. The Sources list is built from the URLs actually fetched, and any sources section the model writes is thrown away |
| An LLM "team leader" decides the workflow | Fixed pipeline in plain Python: same stages every run, a known number of calls, and each stage testable on its own |
| Fetched pages go straight into the prompt | Pages are fenced as untrusted data, closing tags are escaped, and the model is told never to follow instructions inside them |
| Any URL gets fetched | SSRF guard: every hop, redirects included, must resolve to a public IP (blocks `localhost`, `10.x`, `169.254.169.254` metadata, IPv4-mapped IPv6 and the like). Size and content-type limits apply |
| No source quality control | URL canonicalisation and de-duplication, domain credibility tiers, a per-domain cap, optional recency preference, removal of syndicated duplicates, and paywall-stub detection |
| One-sided articles are possible | Notes record whose perspective each source represents. The writer must present disagreements and attribute contested claims. Leaning too hard on one source raises a warning |
| GPT-4o and SerpAPI only | Anthropic or OpenAI; Tavily, Brave or SerpAPI with automatic fallback |
| Re-runs on every keystroke, no error handling, no cost visibility | Explicit Run button, clear errors, token usage per model, on-disk cache for searches and fetches |
| Streamlit only, no tests | Library, CLI (with `--strict` for CI) and Streamlit UI. 33 offline tests; CI on Python 3.10–3.13 |
| AI-sounding prose | Style lint (word list adapted from [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing)) feeds the editor pass |

Original bug fixed along the way: missing commas in the original's `instructions` lists made
Python join separate instructions into one run-on string.

## How it works

```
plan ─▶ search ─▶ rank ─▶ fetch ─▶ notes ─▶ draft ─▶ ┌─ deterministic checks ─┐ ─▶ ready
 (fast)  (parallel) tiers   SSRF-   verbatim   (smart)  │  LLM fact-check        │    or
                   dedupe   safe    quotes only         └─ revise (≤ N rounds) ──┘  needs_review
```

1. **Plan**: the angle, 3–5 search queries and the questions readers will ask.
2. **Search**: the queries run in parallel; if a provider fails, the next one takes over.
3. **Rank**: de-duplicate, score by domain tier and cross-query hits, cap each domain, drop low-tier sites.
4. **Fetch**: safe download, then main-text extraction with trafilatura (title, date and author included).
5. **Notes**: per-source fact extraction. A fact is kept only if its quote is literally in the page.
6. **Draft**: written only from the notes, with a `[n]` citation on every factual sentence.
7. **Check → revise**: quote, citation and figure checks, plus an LLM verdict for each sentence
   (`supported` / `partially_supported` / `unsupported` / `contradicted`) and the style lint.
   Every problem goes back to the editor. This repeats until the draft is clean or `max_revisions` is reached.
8. **Assemble**: the Sources list is generated from real URLs, and the status comes from the remaining critical issues.

`ready` means: no unverified or misattributed quote, no citation to a missing source, no sentence
judged unsupported or contradicted, and at least `min_sources` independent sources cited.

## Quick start

```bash
git clone https://github.com/nigelguy007/verified-journalist.git
cd verified-journalist
pip install -e ".[all]"
cp .env.example .env   # add one LLM key and one search key, then export them
```

**CLI**

```bash
verified-journalist "How the EU AI Act's rules for general-purpose models apply" \
  --style explainer --words 1200 -o article.md --report report.json --strict
```

Exit codes: `0` success, `1` not enough usable sources, `2` configuration error, `3` still
needs review (only with `--strict`).

**Web UI**

```bash
streamlit run app.py
```

**Library**

```python
from verified_journalist import Journalist, Settings

article = Journalist(Settings(style="analysis", recency_days=30)).run("topic")
print(article.status, [i.detail for i in article.critical_issues])
open("article.md", "w").write(article.markdown)
```

## Configuration

| Setting | Env var / flag | Default |
|---|---|---|
| LLM provider | `VJ_LLM_PROVIDER`, `--provider` | whichever key is set (Anthropic first) |
| Models | `VJ_SMART_MODEL`, `VJ_FAST_MODEL` | `claude-sonnet-5-5` / `claude-haiku-4-5-20251001`; `gpt-5` / `gpt-5-mini` |
| Search | `TAVILY_API_KEY`, `BRAVE_API_KEY`, `SERPAPI_API_KEY` | all configured providers, in that order |
| Style | `--style` | `news` (also `feature`, `explainer`, `analysis`) |
| Sources | `--max-sources`, `--min-sources` | 8, 3 |
| Revision rounds | `--revisions` | 2 |
| Recency preference | `--recency-days` | off |
| Cache | `VJ_CACHE_DIR`, `--no-cache` | `~/.cache/verified-journalist` |
| Fetch User-Agent | `VJ_USER_AGENT` | identifies the project; set your own contact URL |

The domain tiers live in `credibility.py`. Adjust them for your beat, or pass `extra_tiers` to `rank_sources`.

## Limits

- **Verified against sources is not the same as true.** The checks prove the article matches
  what the fetched pages say. They can't prove the pages are right. For consequential pieces, a
  human still needs to read the Verification tab and the sources.
- The sentence-level fact check is an LLM judgement. It is strict and checks against the notes,
  but it is not deterministic. The quote and citation checks are deterministic.
- Paywalled, JavaScript-only and PDF sources are skipped, not read.
- Domain tiers are a heuristic. A low tier drops a site; a high tier does not vouch for any single article.
- The SSRF guard resolves DNS before connecting, so a DNS-rebinding attacker could in principle
  race it. Run the fetcher behind an egress proxy if you process hostile input at scale.
- Some sites (Wikipedia, for example) block non-browser HTTP clients, so they'll be skipped.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest -q
```

The tests use scripted fakes for the LLM, search and fetch, so they need no keys or network.

## Use it as a Claude skill

`skill/SKILL.md` wraps the CLI (with a manual fallback that follows the same method) so Claude
Code can use it. Copy the `skill/` folder into your skills directory as `verified-journalist/`.

## License

Apache-2.0. See `LICENSE` and `NOTICE` for the upstream attributions.
