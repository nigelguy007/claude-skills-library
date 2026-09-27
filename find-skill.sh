#!/usr/bin/env bash
#
# Search your installed Claude skills by keyword.
#
# Usage:
#   ./find-skill.sh video          # skills matching "video"
#   ./find-skill.sh "cold email"   # matches the whole phrase
#   ./find-skill.sh                 # list ALL skills (long!)
#
# Searches skill names AND descriptions. Looks in ~/.claude/skills first
# (your globally installed skills); falls back to this repo's skills/ folder.
# Override the search dir with CLAUDE_SKILLS_DIR.
#
set -euo pipefail

QUERY="${*:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SEARCH_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
if [ ! -d "$SEARCH_DIR" ]; then
  SEARCH_DIR="$SCRIPT_DIR/skills"
fi

python3 - "$SEARCH_DIR" "$QUERY" <<'EOF'
import re, sys
from pathlib import Path

search_dir = Path(sys.argv[1])
query = sys.argv[2].strip().lower()

rows = []
for sm in search_dir.rglob("SKILL.md"):
    name = sm.parent.name
    desc = ""
    try:
        txt = sm.read_text(errors="replace")
    except OSError:
        continue
    m = re.search(r'^\s*description\s*:\s*(.+)', txt[:4000], re.M)
    if m:
        desc = m.group(1).strip().strip('"').strip("'")
    hay = (name + " " + desc).lower()
    if not query or query in hay:
        rows.append((name, desc))

rows.sort(key=lambda r: r[0].lower())

if not rows:
    print(f'No skills matched "{query}".')
    sys.exit(0)

label = f'matching "{query}"' if query else "(all)"
print(f"\n{len(rows)} skill(s) {label}:\n")
for name, desc in rows:
    short = (desc[:140] + "…") if len(desc) > 140 else desc
    print(f"  \033[1m{name}\033[0m")
    if short:
        print(f"      {short}")
print(f"\nTip: just describe your task to Claude — the matching skill loads automatically.\n")
EOF