---
name: issue-tree-decomposition
description: Breaks the governing question into a mutually exclusive, collectively exhaustive tree of sub-questions so analysis is complete without overlap, used to scope what to investigate.
---

# Issue Tree Decomposition

## When to use
Use this when a problem feels sprawling and you risk missing a driver or double-counting. It decomposes the question into clean, non-overlapping branches you can each test, then prioritizes which branches matter most so effort goes where the answer lives.

## Instructions
1. Place the governing question at the root and choose one logical basis for the first split.
2. Break it into branches that are mutually exclusive and collectively exhaustive at each level.
3. Drill each branch down until the leaves are concrete, answerable sub-questions.
4. Sanity-check for overlaps and gaps, then rename branches so the logic is obvious.
5. Prioritize the two or three branches most likely to drive the answer and mark the rest as lower effort.

## Example prompts
- "Build a MECE issue tree to break down why our margins are falling."
- "Decompose this strategy question into non-overlapping branches I can analyze."

## Output
An indented issue tree with labeled levels and a short list of priority branches.
