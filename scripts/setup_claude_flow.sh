#!/usr/bin/env bash
#
# Install claude-flow globally and register it as a user-scope MCP server, so
# every Claude Code session on this machine (or cloud container) can use it.
#
# Called by install.sh. Safe to re-run: it skips work that is already done.
# Set SKIP_CLAUDE_FLOW=1 to skip it, or CLAUDE_FLOW_VERSION to pin another version.
#
set -uo pipefail

VERSION="${CLAUDE_FLOW_VERSION:-3.38.20}"

if [ "${SKIP_CLAUDE_FLOW:-}" = "1" ]; then
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "warning: npm not found; skipping claude-flow setup" >&2
  exit 0
fi

installed="$(npm ls -g --depth=0 claude-flow 2>/dev/null | sed -n 's/.*claude-flow@\([^ ]*\).*/\1/p')"
if [ "$installed" = "$VERSION" ]; then
  echo "claude-flow@$VERSION already installed globally"
else
  echo "Installing claude-flow@$VERSION globally ..."
  # onnxruntime-node otherwise downloads CUDA binaries from api.nuget.org, which
  # are unneeded without a GPU and fail behind restrictive proxies.
  ONNXRUNTIME_NODE_INSTALL="${ONNXRUNTIME_NODE_INSTALL:-skip}" \
    npm install -g "claude-flow@$VERSION" || echo "warning: npm install -g claude-flow@$VERSION failed" >&2
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "warning: claude CLI not found; skipping claude-flow MCP registration" >&2
  exit 0
fi

# Re-register so a version change replaces the old entry.
claude mcp remove -s user claude-flow >/dev/null 2>&1 || true
claude mcp add -s user claude-flow -- npx "claude-flow@$VERSION" mcp start \
  || echo "warning: could not register claude-flow MCP server" >&2

exit 0
