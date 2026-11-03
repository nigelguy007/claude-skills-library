# How this was reverse-engineered

Target: https://chatgpt.com/g/g-hhh4w3eov-prompt-maker (reconstructed 2026-11-03)

The GPT's instructions are not public. The GPT page itself is behind the
ChatGPT login wall, so the spec was inferred from what the author published.

## Sources

| Source | What it gave |
|---|---|
| GPT page header (screenshot in the Substack post) | Name "Prompt Maker", author Ruben Hassid, tagline "from a simple prompt → to an optimized prompt", no conversation starters |
| https://app.aiprm.com/gpts/g-hhh4w3eov/prompt-maker | Same description; conversation starters: none |
| https://ruben.substack.com/p/prompt-maker (Jun 2025, updated that day) | Two full input→output screenshots; author says it "always creates a Copy button" (i.e. output in a code block) and that the green text is a placeholder the user fills in; 700k+ users claimed |

## Observed invariants (both examples)

- Lead-in sentence: "Here is your upgraded prompt, designed for optimal performance when used in ChatGPT's browser interface:" / "Here is your optimized and detailed ChatGPT prompt, upgraded to provide thorough analysis and rich output:"
- Prompt inside one code block (rendered with a `vbnet` language label)
- Opens with `Act like a/an [expert role] ...`
- Task framed as `Your task is to ...` or `Objective: Your goal is to ...`
- `Follow these steps:` / `Step-by-step:` with numbered steps, 6 in both examples
- Concrete numbers injected the user never gave (12 hooks, 280 characters, 5 bullets, 10 topics, 2-3 improvements)
- Exclusion step ("Do not include the full post body")
- Sub-bullets defining fields of each output item
- `Optional:` bonus step
- Input slot `"""Insert ... here"""`
- Closes with `Take a deep breath and work on this problem step-by-step.`
- No clarifying questions, no commentary after the block

## What is guessed, not observed

- The screenshots are cut off on the right. Line endings in the worked example
  in SKILL.md (e.g. "...who specializes in LinkedIn content and high-engagement
  hooks", the list of angle types) are plausible completions, not verbatim.
- Word-count range, language-matching and "never invent user facts" rules are
  inferred defaults, not seen in the evidence.
- The original may include knowledge files or extra rules (e.g. refusing to
  reveal its instructions) that leave no trace in its outputs.

## How to verify against the real thing

Run the same 3-5 one-line requests through the live GPT and this skill, then
diff the structure (block order, step count, presence of placeholder and
closer). Differences in wording are expected; differences in structure mean
the spec needs updating.
