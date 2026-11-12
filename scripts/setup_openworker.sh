#!/usr/bin/env bash
#
# Install the OpenWorker headless CLI (github.com/andrewyng/openworker) so every
# Claude Code session on this machine (or cloud container) has the `openworker`
# command. The matching skill lives in skills/andrewyng_openworker.
#
# Called by install.sh. Safe to re-run: it skips work that is already done.
# Set SKIP_OPENWORKER=1 to skip it, or OPENWORKER_VERSION to pin another tag.
#
# NOTE: the PyPI package named "openworker" (0.0.1) is not this project's
# release. This script installs only from the pinned GitHub tag.
#
# This installs the command only. It does not enroll the machine, store any
# model key or start a server: `openworker join` / `up` are left to the user.
#
set -uo pipefail

VERSION="${OPENWORKER_VERSION:-0.3.4}"
# git URL, not the archive zip: some proxies block codeload/archive downloads.
URL="git+https://github.com/andrewyng/openworker@v${VERSION}"

if [ "${SKIP_OPENWORKER:-}" = "1" ]; then
  exit 0
fi

current="$(openworker version 2>/dev/null | awk '{print $NF}')"
if [ "$current" = "$VERSION" ]; then
  echo "openworker $VERSION already installed"
  exit 0
fi

echo "Installing openworker $VERSION from GitHub ..."
if command -v uv >/dev/null 2>&1; then
  uv tool install --force "$URL" >/dev/null 2>&1 \
    || { echo "warning: uv tool install openworker $VERSION failed" >&2; exit 0; }
else
  python3 -m pip install -q --user "$URL" >/dev/null 2>&1 \
    || python3 -m pip install -q --user --break-system-packages "$URL" >/dev/null 2>&1 \
    || { echo "warning: pip install openworker $VERSION failed (install uv for the supported path)" >&2; exit 0; }
fi

if ! command -v openworker >/dev/null 2>&1; then
  echo "warning: openworker not on PATH after install (try: uv tool update-shell)" >&2
fi

exit 0
