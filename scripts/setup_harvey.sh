#!/usr/bin/env bash
#
# Install Harvey (github.com/ethanplusai/harvey), the autonomous sales agent CLI,
# so the `harvey` command is on PATH in every session on this machine (or cloud
# container).
#
# Harvey is a Python app, not a Claude skill. It is cloned to ~/harvey, installed
# into its own virtualenv there, and linked into ~/.local/bin (and /usr/local/bin
# when writable). Its state (data/harvey.db, .env, harvey.local.yaml) lives in
# the clone, so on an ephemeral cloud container that state is lost when the
# container is reclaimed.
#
# Called by install.sh. Safe to re-run: it skips work that is already done.
# Set SKIP_HARVEY=1 to skip it, HARVEY_REF to pin another commit/branch/tag, or
# HARVEY_DIR to clone somewhere else.
#
set -uo pipefail

REPO_URL="https://github.com/ethanplusai/harvey.git"
# Pinned so a new upstream commit can't change what runs here unreviewed.
REF="${HARVEY_REF:-60120fd6912f127428316384166580a31467ba7d}"
DEST="${HARVEY_DIR:-$HOME/harvey}"

if [ "${SKIP_HARVEY:-}" = "1" ]; then
  exit 0
fi

PY=""
for cand in python3.13 python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1 \
    && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "warning: Harvey needs Python 3.11+; skipping Harvey setup" >&2
  exit 0
fi

if [ ! -d "$DEST/.git" ]; then
  echo "Cloning Harvey into $DEST ..."
  git clone --quiet "$REPO_URL" "$DEST" || { echo "warning: could not clone Harvey" >&2; exit 0; }
fi

current="$(git -C "$DEST" rev-parse HEAD 2>/dev/null)"
target="$(git -C "$DEST" rev-parse --verify --quiet "$REF^{commit}" || true)"
if [ -z "$target" ]; then
  git -C "$DEST" fetch --quiet origin "$REF" || echo "warning: could not fetch Harvey ref $REF" >&2
  target="$(git -C "$DEST" rev-parse --verify --quiet "$REF^{commit}" || git -C "$DEST" rev-parse --verify --quiet FETCH_HEAD || true)"
fi
if [ -n "$target" ] && [ "$current" != "$target" ]; then
  git -C "$DEST" checkout --quiet "$target" || echo "warning: could not check out Harvey $REF" >&2
fi

stamp="$DEST/.venv/.installed-rev"
rev="$(git -C "$DEST" rev-parse HEAD)"
if [ -x "$DEST/.venv/bin/harvey" ] && [ "$(cat "$stamp" 2>/dev/null)" = "$rev" ]; then
  echo "Harvey ${rev:0:7} already installed"
else
  echo "Installing Harvey ${rev:0:7} ..."
  "$PY" -m venv "$DEST/.venv" \
    && "$DEST/.venv/bin/pip" install --quiet --upgrade pip \
    && "$DEST/.venv/bin/pip" install --quiet -e "$DEST" \
    && echo "$rev" > "$stamp" \
    || { echo "warning: Harvey pip install failed" >&2; exit 0; }
fi

mkdir -p "$HOME/.local/bin"
ln -sf "$DEST/.venv/bin/harvey" "$HOME/.local/bin/harvey"
if [ -w /usr/local/bin ]; then
  ln -sf "$DEST/.venv/bin/harvey" /usr/local/bin/harvey
fi

# State sync commands (see harvey_state.sh and harvey_cycle.sh).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ln -sf "$SCRIPT_DIR/harvey_state.sh" "$HOME/.local/bin/harvey-state"
ln -sf "$SCRIPT_DIR/harvey_cycle.sh" "$HOME/.local/bin/harvey-cycle"

exit 0
