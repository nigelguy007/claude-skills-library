#!/usr/bin/env bash
#
# Run Harvey for a bounded window in an ephemeral container: restore state,
# run the heartbeat loop, stop it cleanly, save state. Meant for a scheduled
# cloud session (e.g. hourly) since a container can't host the endless loop.
#
#   harvey_cycle.sh             # run for HARVEY_CYCLE_MINUTES (default 25)
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINUTES="${HARVEY_CYCLE_MINUTES:-25}"
HARVEY="${HARVEY_DIR:-$HOME/harvey}"

command -v harvey >/dev/null 2>&1 || bash "$SCRIPT_DIR/setup_harvey.sh"
bash "$SCRIPT_DIR/harvey_state.sh" pull

if [ ! -f "$HARVEY/harvey.local.yaml" ]; then
  echo "harvey-cycle: Harvey isn't trained yet (no harvey.local.yaml); run 'harvey train <url>' first" >&2
  exit 1
fi

# SIGTERM makes Harvey finish shutting down instead of dying mid-write;
# a single agent batch is capped at 10 minutes inside Harvey.
cd "$HARVEY" && timeout -s TERM -k 60 "${MINUTES}m" harvey run
status=$?

bash "$SCRIPT_DIR/harvey_state.sh" push
# 124 = stopped by the timeout, which is the normal end of a window.
[ "$status" -eq 124 ] && status=0
exit "$status"
