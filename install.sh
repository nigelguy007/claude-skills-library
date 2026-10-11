#!/usr/bin/env bash
#
# Install skills from this repo into your global Claude Code skills directory
# (~/.claude/skills) so they are available in every project.
#
# Usage:
#   ./install.sh                              # install every skill
#   ./install.sh --source emilkowalski_skills # install just one collection
#   ./install.sh --agents                     # install subagents into ~/.claude/agents
#   ./install.sh --agents --division engineering  # just one agent division
#
# Set CLAUDE_SKILLS_DIR (or CLAUDE_AGENTS_DIR) to install somewhere else.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required" >&2
  exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)'; then
  echo "error: python3 3.6+ is required (found: $(python3 --version 2>&1))" >&2
  echo "hint: install a newer python3 (e.g. 'brew install python3') and re-run, or set PATH so a newer python3 is found first." >&2
  exit 1
fi

if [ "${1:-}" = "--agents" ]; then
  shift
  exec python3 "${SCRIPT_DIR}/install_global_agents.py" "$@"
fi

exec python3 "${SCRIPT_DIR}/install_global_skills.py" "$@"
