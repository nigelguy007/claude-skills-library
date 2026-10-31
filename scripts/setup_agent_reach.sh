#!/usr/bin/env bash
#
# Install the Agent Reach CLI (github.com/Panniantong/Agent-Reach) and run its
# setup, so every Claude Code session on this machine (or cloud container) can
# use it. The matching skill lives in skills/Panniantong_Agent-Reach.
#
# Called by install.sh. Safe to re-run: it skips work that is already done.
# Set SKIP_AGENT_REACH=1 to skip it, AGENT_REACH_VERSION to pin another
# release tag, or AGENT_REACH_LANG=zh for the Chinese skill text.
#
# NOTE: the PyPI package named "agent-reach" is a different project. This
# script installs only from the GitHub release and removes the PyPI one.
#
set -uo pipefail

VERSION="${AGENT_REACH_VERSION:-1.6.0}"
# git URL, not the archive zip: some proxies block codeload/archive downloads.
URL="git+https://github.com/Panniantong/Agent-Reach@v${VERSION}"
export AGENT_REACH_LANG="${AGENT_REACH_LANG:-en}"

if [ "${SKIP_AGENT_REACH:-}" = "1" ]; then
  exit 0
fi

# Remove the unrelated PyPI "agent-reach" (0.x) if it is installed.
for py in python3 /usr/local/bin/python3 /usr/bin/python3; do
  command -v "$py" >/dev/null 2>&1 || continue
  v="$("$py" -m pip show agent-reach 2>/dev/null | sed -n 's/^Version: //p')"
  case "$v" in
    0.*) echo "Removing unrelated PyPI agent-reach $v ($py)"
         "$py" -m pip uninstall -y -q agent-reach >/dev/null 2>&1 \
           || "$py" -m pip uninstall -y -q --break-system-packages agent-reach >/dev/null 2>&1 || true ;;
  esac
done

current="$(agent-reach version 2>/dev/null | python3 -c 'import sys,json;print(json.loads(sys.stdin.read().strip().splitlines()[-1]).get("result",{}).get("version",""))' 2>/dev/null)"
if [ "$current" = "$VERSION" ]; then
  echo "agent-reach $VERSION already installed"
else
  echo "Installing agent-reach $VERSION from GitHub ..."
  if command -v uv >/dev/null 2>&1; then
    uv tool install --force "$URL" >/dev/null 2>&1 || { echo "warning: uv tool install agent-reach $VERSION failed" >&2; exit 0; }
  else
    python3 -m pip install -q --user "$URL" >/dev/null 2>&1 \
      || python3 -m pip install -q --user --break-system-packages "$URL" >/dev/null 2>&1 \
      || { echo "warning: pip install agent-reach $VERSION failed (install uv for the supported path)" >&2; exit 0; }
  fi
fi

if ! command -v agent-reach >/dev/null 2>&1; then
  echo "warning: agent-reach not on PATH after install (try: uv tool update-shell)" >&2
  exit 0
fi

# setup links the skill into ~/.claude/skills. A symlink there would collide
# with this library's installer, so give it a real folder to refresh in place.
SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
LIB_SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/Panniantong_Agent-Reach/agent-reach"
if [ -d "$LIB_SKILL" ]; then
  mkdir -p "$SKILLS_DIR"
  if [ -L "$SKILLS_DIR/agent-reach" ]; then rm -f "$SKILLS_DIR/agent-reach"; fi
  [ -e "$SKILLS_DIR/agent-reach" ] || cp -r "$LIB_SKILL" "$SKILLS_DIR/agent-reach"
fi

agent-reach setup >/dev/null 2>&1 || echo "warning: agent-reach setup failed; run 'agent-reach doctor'" >&2

exit 0
