#!/usr/bin/env python3
"""Rebuild the per-source counts and the skill table in SKILLS.md from skills/ on disk.

Existing rows are kept verbatim when the skill still exists, so hand-edited
descriptions survive; new skills get rows generated from their SKILL.md
front-matter, and rows for skills no longer on disk are dropped.

    python3 scripts/build_skills_index.py
"""
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import install_global_skills as g  # noqa: E402

INDEX = REPO / "SKILLS.md"
# Source dirs whose name isn't "<owner>_<repo>" of their upstream.
ALIASES = {"affaan-m_ecc": "affaan-m/everything-claude-code"}
ROW_RE = re.compile(r"^\| `([^`]+)` \| ([^|]+?) \|")


def clip(text, n):
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def front_matter(skill_dir):
    text = (skill_dir / "SKILL.md").read_text(errors="ignore")
    fm = text.split("---", 2)[1] if text.startswith("---") else ""
    m = re.search(r"^name:\s*['\"]?([^'\"\n]+)", fm, re.M)
    name = m.group(1).strip() if m else skill_dir.name
    m = re.search(r"^description:\s*(?:[>|][-+]?)?\s*\n?((?:.*\n?)*?)(?=^[\w-]+:|\Z)", fm, re.M)
    desc = " ".join(m.group(1).split()).strip("'\"") if m else ""
    return name, desc


def main():
    text = INDEX.read_text()
    head, table = text.split("## All installed skills", 1)

    # Source dir -> display label, taken from the summary table.
    labels = {}
    for line in head.splitlines():
        m = re.match(r"^\| \d+ \| \[([^\]]+)\]\(https://github\.com/[^)]+\) \| \d+ \|$", line)
        if m:
            label = m.group(1)
            src = next((k for k, v in ALIASES.items() if v == label), label.replace("/", "_", 1))
            labels[src] = label
            continue
        m = re.match(r"^\| \d+ \| (.+?) \(`skills/([^`]+)`\) \| \d+ \|$", line)
        if m:
            labels[m.group(2)] = m.group(1)

    existing = {}
    for line in table.splitlines():
        m = ROW_RE.match(line)
        if m:
            existing.setdefault((m.group(1), m.group(2).strip()), line)

    rows, per_source = [], Counter()
    top = g.find_top_level_skills(g.SRC_ROOT)
    for d in sorted(set(top) | set(g.find_router_children(g.SRC_ROOT, top))):
        src = g.owner_repo(d)
        label = labels.get(src)
        if label is None:
            # New source: its dir is "<owner>_<repo>" (or listed in ALIASES).
            label = labels[src] = ALIASES.get(src, src.replace("_", "/", 1))
        name, desc = front_matter(d)
        per_source[src] += 1
        row = existing.get((name, label))
        if row is None:
            tm = re.search(r"((?:Use|Triggers?) (?:when|whenever|this|on|for)[^.]*\.)", desc)
            trig = clip(tm.group(1), 160) if tm else "Model-invoked automatically when a request matches the skill's description."
            row = f"| `{name}` | {label} | {clip(desc, 240).replace('|', '/')} | {trig.replace('|', '/')} |"
        rows.append(row)

    total = len(rows)
    order = list(OrderedDict.fromkeys(labels))
    summary = []
    for src in order:
        if not per_source[src]:
            continue
        label = labels[src]
        cell = f"[{label}](https://github.com/{label})" if "/" in label and " " not in label else f"{label} (`skills/{src}`)"
        summary.append((cell, per_source[src]))
    n_repos = sum(1 for c, _ in summary if c.startswith("["))
    n_packs = len(summary) - n_repos

    head = re.sub(r"\*\*\d+ Claude skills\*\*", f"**{total} Claude skills**", head)
    head = re.sub(r"from \d+ source repositories plus \d+ uploaded skill packs",
                  f"from {n_repos} source repositories plus {n_packs} uploaded skill packs", head)
    lines, out, in_summary = head.split("\n"), [], False
    for line in lines:
        if re.match(r"^\| \d+ \|", line):
            if not in_summary:
                in_summary = True
                out += [f"| {i} | {c} | {n} |" for i, (c, n) in enumerate(summary, 1)]
            continue
        out.append(line)
    head = "\n".join(out)

    header = "\n\n| Skill | Source repo | Description | Trigger |\n|-------|-------------|-------------|---------|\n"
    INDEX.write_text(f"{head}## All installed skills ({total}){header}" + "\n".join(rows) + "\n")
    print(f"{total} skills from {len(summary)} sources")


if __name__ == "__main__":
    main()
