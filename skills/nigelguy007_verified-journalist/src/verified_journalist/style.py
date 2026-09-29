"""Deterministic lint for machine-sounding prose.

Word list adapted from the MIT-licensed avoid-ai-writing skill by Conor Bronsdon
(https://github.com/conorbronsdon/avoid-ai-writing). These are signals for the editor
pass, not proof of anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

AI_WORDS = {
    "delve": "look at",
    "tapestry": "(describe the actual complexity)",
    "realm": "area",
    "paradigm": "model",
    "embark": "start",
    "beacon": "(name the example)",
    "testament to": "shows",
    "robust": "strong",
    "comprehensive": "thorough",
    "cutting-edge": "newest",
    "leverage": "use",
    "pivotal": "key",
    "underscores": "shows",
    "meticulous": "careful",
    "seamless": "smooth",
    "game-changer": "(say what changed)",
    "game-changing": "(say what changed)",
    "watershed moment": "turning point",
    "nestled": "sits",
    "vibrant": "(be specific)",
    "thriving": "(cite a number)",
    "showcasing": "showing",
    "deep dive": "close look",
    "intricate": "complex",
    "ever-evolving": "changing",
    "holistic": "whole",
    "actionable": "practical",
    "impactful": "(describe the impact)",
    "synergy": "(describe the combined effect)",
    "interplay": "relationship",
    "navigate the complexities": "(name the problem)",
    "in today's fast-paced world": "(cut)",
    "rapidly evolving": "(cut or be specific)",
    "it's important to note": "(cut)",
    "it is important to note": "(cut)",
    "only time will tell": "(cut)",
    "the future looks bright": "(cut)",
    "at its core": "(cut)",
    "stands as": "is",
    "serves as": "is",
    "boasts": "has",
    "in conclusion": "(cut)",
    "moreover": "(cut or 'and')",
    "furthermore": "(cut or 'and')",
    "experts believe": "(name the expert and cite them)",
    "some say": "(name who says it and cite them)",
}
_PATTERNS = {
    word: re.compile(r"\b" + re.escape(word).replace(r"\ ", r"\s+") + r"\w*", re.IGNORECASE)
    for word in AI_WORDS
}


@dataclass
class StyleHit:
    phrase: str
    suggestion: str
    excerpt: str


def lint(text: str) -> list[StyleHit]:
    hits = []
    for word, pattern in _PATTERNS.items():
        for match in pattern.finditer(text):
            start, end = max(0, match.start() - 40), min(len(text), match.end() + 40)
            excerpt = " ".join(text[start:end].split())
            hits.append(StyleHit(word, AI_WORDS[word], excerpt))
    words = max(1, len(text.split()))
    dashes = text.count("—")
    if dashes * 1000 / words > 3:
        hits.append(StyleHit("em dash overuse", f"{dashes} em dashes in {words} words", ""))
    return hits
