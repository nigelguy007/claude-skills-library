#!/usr/bin/env bash
#
# Install the Agent Reach CLI (github.com/Panniantong/Agent-Reach) that the
# vendored agent-reach skill calls, and turn on its default channels.
#
# Called by install.sh. Safe to re-run: it skips the install when the pinned
# version is already there. Set SKIP_AGENT_REACH=1 to skip it, or
# AGENT_REACH_VERSION to pin another release.
#
# The PyPI package named agent-reach is a different project. This script
# removes it if present and installs from the GitHub release instead.
#
# YouTube blocks cloud IPs without a signed-in session. To fix that, store a
# Netscape-format cookies.txt from a throwaway YouTube account, base64-encoded,
# in the environment variable AGENT_REACH_YT_COOKIES_B64. Never commit it.
#
set -uo pipefail

VERSION="${AGENT_REACH_VERSION:-1.6.0}"
URL="https://github.com/Panniantong/Agent-Reach/releases/download/v${VERSION}/agent-reach.zip"
export PATH="$HOME/.local/bin:$PATH"

if [ "${SKIP_AGENT_REACH:-}" = "1" ]; then
  exit 0
fi

python3 -m pip uninstall -y agent-reach >/dev/null 2>&1 || true

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (needed by Agent Reach) ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "warning: uv not found; skipping Agent Reach setup" >&2
  exit 0
fi

if agent-reach version 2>/dev/null | grep -q "\"version\": \"${VERSION}\""; then
  echo "agent-reach ${VERSION} already installed"
else
  echo "Installing agent-reach ${VERSION} ..."
  uv tool install --force "$URL" >/dev/null 2>&1 \
    || { echo "warning: agent-reach ${VERSION} install failed" >&2; exit 0; }
fi
agent-reach setup >/dev/null 2>&1 || echo "warning: 'agent-reach setup' failed" >&2

cookies="$HOME/.agent-reach/youtube-cookies.txt"
if [ -n "${AGENT_REACH_YT_COOKIES_B64:-}" ]; then
  mkdir -p "$HOME/.agent-reach"
  ( umask 077; printf '%s' "$AGENT_REACH_YT_COOKIES_B64" | base64 -d > "$cookies" ) 2>/dev/null \
    || { echo "warning: AGENT_REACH_YT_COOKIES_B64 is not valid base64" >&2; rm -f "$cookies"; }
fi
if [ -s "$cookies" ]; then
  mkdir -p "$HOME/.config/yt-dlp"
  grep -qxF -- "--cookies $cookies" "$HOME/.config/yt-dlp/config" 2>/dev/null \
    || echo "--cookies $cookies" >> "$HOME/.config/yt-dlp/config"
  echo "agent-reach ${VERSION} ready (YouTube cookies on)"
else
  echo "agent-reach ${VERSION} ready (no YouTube cookies; YouTube may be blocked from cloud IPs)"
fi
