#!/usr/bin/env bash
#
# Install the `watch-video` CLI used by the watch-link skill
# (skills/mohamedishagg_watch-skill, from github.com/mohamedishagg/watch-skill).
#
# Differences from upstream install.sh: the command is `watch-video`, not
# `watch` (which would shadow /usr/bin/watch), and the SKILL.md is installed by
# install_global_skills.py rather than copied here.
#
# Called by install.sh. Safe to re-run. Set SKIP_WATCH_SKILL=1 to skip.
# Override pins with WATCH_YTDLP_VERSION / WATCH_WHISPER_VERSION / WATCH_PILLOW_VERSION.
#
set -uo pipefail

[ "${SKIP_WATCH_SKILL:-}" = "1" ] && exit 0

YTDLP_V="${WATCH_YTDLP_VERSION:-2026.10.21}"
WHISPER_V="${WATCH_WHISPER_VERSION:-1.2.1}"
PILLOW_V="${WATCH_PILLOW_VERSION:-12.3.0}"
AV_V="${WATCH_AV_VERSION:-15.1.0}"  # av>=16 breaks faster-whisper 1.2.1 (metadata_errors kwarg)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SCRIPT_DIR}/../skills/mohamedishagg_watch-skill/watch.py"
H="$HOME/.claude/watch"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "warning: ffmpeg not found; watch-video will not work until it is installed" >&2
fi

mkdir -p "$H" "$HOME/.local/bin"
if [ ! -x "$H/venv/bin/python" ]; then
  python3 -m venv "$H/venv" || { echo "warning: could not create venv for watch-video" >&2; exit 0; }
fi
"$H/venv/bin/pip" install -q "yt-dlp==${YTDLP_V}" "pillow==${PILLOW_V}" "faster-whisper==${WHISPER_V}" "av==${AV_V}" \
  || echo "warning: pip install for watch-video failed (it may still work partially)" >&2

cp "$SRC" "$H/watch.py"
printf '#!/bin/bash\nexec "$HOME/.claude/watch/venv/bin/python" "$HOME/.claude/watch/watch.py" "$@"\n' > "$H/watch-video"
chmod +x "$H/watch-video"
ln -sf "$H/watch-video" "$HOME/.local/bin/watch-video"
# Undo upstream's install if present: it shadows /usr/bin/watch.
if [ -L "$HOME/.local/bin/watch" ] && [ "$(readlink "$HOME/.local/bin/watch")" = "$H/watch" ]; then
  rm -f "$HOME/.local/bin/watch"
fi
echo "watch-video installed ($HOME/.local/bin/watch-video)"
