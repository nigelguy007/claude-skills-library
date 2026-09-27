#!/usr/bin/env bash
#
# One-command setup for a NEW machine or Claude account.
#
# Clones (or updates) this skill library and installs every skill into the
# global ~/.claude/skills directory, so Claude Code can use them in any project.
#
# Run it directly:
#     curl -fsSL https://raw.githubusercontent.com/nigelguy007/claude-skills-library/HEAD/bootstrap.sh | bash
#
# ...or clone first and run locally:
#     git clone https://github.com/nigelguy007/claude-skills-library.git
#     cd claude-skills-library && ./bootstrap.sh
#
# Environment overrides:
#     SKILLS_REPO_URL     git URL to clone            (default: this repo)
#     SKILLS_REPO_BRANCH  branch to use               (default: repo default branch)
#     SKILLS_REPO_DIR     where to clone the library  (default: ~/claude-skills-library)
#     CLAUDE_SKILLS_DIR   where to install skills      (default: ~/.claude/skills)
#
set -euo pipefail

REPO_URL="${SKILLS_REPO_URL:-https://github.com/nigelguy007/claude-skills-library.git}"
REPO_BRANCH="${SKILLS_REPO_BRANCH:-}"
DEST="${SKILLS_REPO_DIR:-$HOME/claude-skills-library}"

for bin in git python3; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "error: '$bin' is required but not installed." >&2
    exit 1
  fi
done

if [ -d "$DEST/.git" ]; then
  echo "Updating existing library at $DEST ..."
  if [ -n "$REPO_BRANCH" ]; then
    git -C "$DEST" fetch origin "$REPO_BRANCH"
    git -C "$DEST" checkout "$REPO_BRANCH"
    git -C "$DEST" reset --hard "origin/$REPO_BRANCH"
  else
    git -C "$DEST" pull --ff-only || echo "warning: could not fast-forward; using existing checkout"
  fi
else
  echo "Cloning skill library into $DEST ..."
  if [ -n "$REPO_BRANCH" ]; then
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$DEST"
  else
    git clone "$REPO_URL" "$DEST"
  fi
fi

echo "Installing skills globally ..."
bash "$DEST/install.sh"

echo
echo "All set. Restart Claude Code, then try:  \"$DEST/find-skill.sh\" video"
