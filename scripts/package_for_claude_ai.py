#!/usr/bin/env python3
"""Package skills as upload-ready zips for claude.ai chat / Claude Desktop chat.

claude.ai chat (web, desktop and mobile apps) does NOT read ~/.claude/skills --
that directory only exists for Claude Code. Chat skills are stored on your
account and added by uploading a zip in Settings -> Capabilities -> Skills.
Once uploaded, a skill is available in every chat on every device.

This script builds one zip per skill (a top-level folder containing SKILL.md
and its supporting files), which is the layout that upload expects.

Usage:
    python3 scripts/package_for_claude_ai.py <skill-name> [more names...]
    python3 scripts/package_for_claude_ai.py --source addyosmani_agent-skills

Skill names are matched against the SKILL.md directory name or front-matter
``name`` anywhere under skills/. Zips are written to dist/claude-ai/
(override with --out).
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "skills"
NAME_LINE = re.compile(r"(?m)^name:\s*[\"']?([^\"'\n]+)")


def top_level_skills(root: Path):
    dirs = {p.parent for p in root.rglob("SKILL.md")}
    return sorted(d for d in dirs if not any(a in dirs for a in d.parents))


def skill_name(d: Path) -> str:
    m = NAME_LINE.search((d / "SKILL.md").read_text(errors="ignore")[:2000])
    return m.group(1).strip() if m else d.name


def build_zip(d: Path, out_dir: Path) -> Path:
    name = skill_name(d)
    dest = out_dir / f"{name}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(d.rglob("*")):
            if f.is_file() and ".git" not in f.parts:
                z.write(f, Path(name) / f.relative_to(d))
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("names", nargs="*", help="skill names to package")
    ap.add_argument("--source", action="append", default=[],
                    help="package every skill from skills/<owner>_<repo>")
    ap.add_argument("--out", default=str(REPO_ROOT / "dist" / "claude-ai"))
    args = ap.parse_args()
    if not args.names and not args.source:
        ap.error("give skill names and/or --source")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    selected = []
    for src in args.source:
        root = SRC_ROOT / src
        if not root.is_dir():
            print(f"unknown source: {src}", file=sys.stderr)
            return 1
        selected += top_level_skills(root)

    if args.names:
        wanted = set(args.names)
        for d in top_level_skills(SRC_ROOT):
            if d.name in wanted or skill_name(d) in wanted:
                selected.append(d)
                wanted.discard(d.name)
                wanted.discard(skill_name(d))
        if wanted:
            print("not found: " + ", ".join(sorted(wanted)), file=sys.stderr)

    for d in dict.fromkeys(selected):
        print(build_zip(d, out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
