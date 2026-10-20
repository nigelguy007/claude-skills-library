#!/usr/bin/env bash
#
# Install ruflo (formerly claude-flow) globally and register it as a user-scope
# MCP server, so every Claude Code session on this machine (or cloud container)
# can use it.
#
# Called by install.sh. Safe to re-run: it skips work that is already done.
# Set SKIP_RUFLO=1 to skip it, or RUFLO_VERSION to pin another version.
#
set -uo pipefail

VERSION="${RUFLO_VERSION:-3.59.1}"

if [ "${SKIP_RUFLO:-}" = "1" ]; then
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "warning: npm not found; skipping ruflo setup" >&2
  exit 0
fi

installed="$(npm ls -g --depth=0 ruflo 2>/dev/null | sed -n 's/.*ruflo@\([^ ]*\).*/\1/p')"
if [ "$installed" = "$VERSION" ]; then
  echo "ruflo@$VERSION already installed globally"
else
  echo "Installing ruflo@$VERSION globally ..."
  # onnxruntime-node otherwise downloads CUDA binaries from api.nuget.org, which
  # are unneeded without a GPU and fail behind restrictive proxies.
  ONNXRUNTIME_NODE_INSTALL="${ONNXRUNTIME_NODE_INSTALL:-skip}" \
    npm install -g "ruflo@$VERSION" || echo "warning: npm install -g ruflo@$VERSION failed" >&2
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "warning: claude CLI not found; skipping ruflo MCP registration" >&2
  exit 0
fi

# Drop the entry earlier versions of this script registered under the old name,
# and re-register ruflo so a version change replaces the old entry.
claude mcp remove -s user claude-flow >/dev/null 2>&1 || true
claude mcp remove -s user ruflo >/dev/null 2>&1 || true
claude mcp add -s user ruflo -- npx "ruflo@$VERSION" mcp start \
  || echo "warning: could not register ruflo MCP server" >&2

exit 0
