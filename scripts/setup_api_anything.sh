#!/usr/bin/env bash
#
# Install the api-anything CLI globally and register it as a user-scope MCP
# server, so every Claude Code session on this machine (or cloud container)
# can use it. The matching skill lives in skills/goodnight000_api-anything.
#
# Called by install.sh. Safe to re-run: it skips work that is already done.
# Set SKIP_API_ANYTHING=1 to skip it, API_ANYTHING_VERSION to pin another
# version, or API_ANYTHING_SHARE=1 to opt in to the shared public catalog
# (default: off, so nothing this machine learns is uploaded).
#
set -uo pipefail

VERSION="${API_ANYTHING_VERSION:-0.3.1}"

if [ "${SKIP_API_ANYTHING:-}" = "1" ]; then
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "warning: npm not found; skipping api-anything setup" >&2
  exit 0
fi

# api-anything needs Node >= 22.13.
if ! node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>22||(a===22&&b>=13)?0:1)' 2>/dev/null; then
  echo "warning: api-anything needs Node >= 22.13 (found $(node --version 2>/dev/null)); skipping" >&2
  exit 0
fi

installed="$(npm ls -g --depth=0 api-anything 2>/dev/null | sed -n 's/.*api-anything@\([^ ]*\).*/\1/p')"
if [ "$installed" = "$VERSION" ]; then
  echo "api-anything@$VERSION already installed globally"
else
  echo "Installing api-anything@$VERSION globally ..."
  npm install -g "api-anything@$VERSION" || { echo "warning: npm install -g api-anything@$VERSION failed" >&2; exit 0; }
fi

# Record the catalog-sharing answer so the agent never uploads by surprise.
if [ "${API_ANYTHING_SHARE:-}" = "1" ]; then
  api-anything setup --yes --share-only >/dev/null 2>&1 || true
else
  api-anything setup --no-share --share-only >/dev/null 2>&1 || true
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "warning: claude CLI not found; skipping api-anything MCP registration" >&2
  exit 0
fi

# Point it at a Chromium build if one exists (needed only to learn new sites).
browser_env=()
for b in "${API_ANYTHING_BROWSER:-}" /usr/bin/google-chrome /usr/bin/chromium /usr/bin/chromium-browser; do
  if [ -n "$b" ] && [ -x "$b" ]; then browser_env=(-e "API_ANYTHING_BROWSER=$b"); break; fi
done

claude mcp remove -s user api-anything >/dev/null 2>&1 || true
claude mcp add -s user api-anything "${browser_env[@]}" -- api-anything mcp \
  || echo "warning: could not register api-anything MCP server" >&2

exit 0
