#!/usr/bin/env bash
#
# Keep Harvey's state in a private git repo so it survives ephemeral cloud
# containers.
#
#   harvey_state.sh pull   # restore state from the repo into ~/harvey
#   harvey_state.sh push   # snapshot ~/harvey state and push it (no-op if unchanged)
#
# Synced: data/harvey.db (consistent SQLite snapshot), harvey.local.yaml,
# skills/product_knowledge.md, skills/competitive_intel.md, linkedin_cookies.json.
# Never synced: .env and data/*token* files. Put credentials in the cloud
# environment's variables instead; Harvey reads them from the process
# environment and .env never overrides them.
#
# Environment:
#   HARVEY_STATE_REPO  git URL of the state repo
#                      (default: https://github.com/nigelguy007/Harvey.git)
#   HARVEY_STATE_DIR   local clone (default: ~/.harvey-state)
#   HARVEY_DIR         Harvey checkout (default: ~/harvey)
#
# Exits 0 when the repo is unreachable, so it is safe in hooks.
#
set -uo pipefail

REPO="${HARVEY_STATE_REPO:-https://github.com/nigelguy007/Harvey.git}"
STATE="${HARVEY_STATE_DIR:-$HOME/.harvey-state}"
HARVEY="${HARVEY_DIR:-$HOME/harvey}"
FILES=(harvey.local.yaml skills/product_knowledge.md skills/competitive_intel.md linkedin_cookies.json)

log() { echo "harvey-state: $*" >&2; }

[ -d "$HARVEY" ] || { log "no Harvey checkout at $HARVEY; skipping"; exit 0; }

ensure_clone() {
  if [ ! -d "$STATE/.git" ]; then
    git clone --quiet "$REPO" "$STATE" 2>/dev/null || { log "can't reach $REPO; skipping"; return 1; }
  else
    git -C "$STATE" pull --quiet --rebase 2>/dev/null || log "warning: pull failed; using local copy"
  fi
}

snapshot_db() {  # $1 = source db, $2 = destination
  python3 - "$1" "$2" <<'PY'
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()
PY
}

case "${1:-}" in
  pull)
    ensure_clone || exit 0
    mkdir -p "$HARVEY/data" "$HARVEY/skills"
    if [ -f "$STATE/data/harvey.db" ]; then
      if [ -f "$HARVEY/data/harvey.db" ] && [ "$HARVEY/data/harvey.db" -nt "$STATE/data/harvey.db" ] \
        && ! cmp -s "$HARVEY/data/harvey.db" "$STATE/data/harvey.db"; then
        log "local harvey.db is newer than the repo copy; keeping it (run push to save it)"
      else
        cp -p "$STATE/data/harvey.db" "$HARVEY/data/harvey.db"
      fi
    fi
    for f in "${FILES[@]}"; do
      [ -f "$STATE/$f" ] && cp -p "$STATE/$f" "$HARVEY/$f"
    done
    log "restored state from $REPO"
    ;;
  push)
    ensure_clone || exit 0
    mkdir -p "$STATE/data" "$STATE/skills"
    if [ -f "$HARVEY/data/harvey.db" ]; then
      snapshot_db "$HARVEY/data/harvey.db" "$STATE/data/harvey.db.tmp" \
        && mv "$STATE/data/harvey.db.tmp" "$STATE/data/harvey.db"
    fi
    for f in "${FILES[@]}"; do
      [ -f "$HARVEY/$f" ] && cp -p "$HARVEY/$f" "$STATE/$f"
    done
    git -C "$STATE" add -A .
    if git -C "$STATE" diff --cached --quiet; then
      exit 0
    fi
    git -C "$STATE" -c user.name="harvey-state" -c user.email="harvey-state@users.noreply.github.com" \
      commit --quiet -m "Harvey state $(date -u +%Y-%m-%dT%H:%MZ)"
    for delay in 0 2 4 8; do
      sleep "$delay"
      git -C "$STATE" pull --quiet --rebase -X theirs 2>/dev/null || true
      if git -C "$STATE" push --quiet -u origin HEAD 2>/dev/null; then
        log "saved state to $REPO"
        exit 0
      fi
    done
    log "warning: push failed; state is committed locally in $STATE"
    ;;
  *)
    echo "usage: $0 pull|push" >&2
    exit 2
    ;;
esac
exit 0
