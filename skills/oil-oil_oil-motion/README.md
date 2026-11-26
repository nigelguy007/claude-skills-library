# oil-oil_oil-motion

[Oil Motion](https://github.com/oil-oil/oil-motion) by Lin Zhihuang (MIT): turns
AI-generated or existing video and frame sequences into web animation that follows
scroll, pointer, drag, touch or state.

`oil-motion/` is the upstream repository at commit
`c930f4477304603b192c9633a449c9f4da98d75c`, unmodified. It installs as the skill
`oil-motion`. It replaces the trimmed copy that used to come with
`skills/nexu-io_open-design/`, so there is one `oil-motion`, not two.

## What needs what

| Part | Needs | Network |
| --- | --- | --- |
| Processing existing video or frames (`scripts/*.py` except the two below) | Python 3.10+, Pillow, numpy, PyYAML, `ffmpeg`, `ffprobe` | none |
| Generating key frames and video (`scripts/image_job.py`, `scripts/video_job.py`) | a ZenMux API key in `ZENMUX_API_KEY` | `https://zenmux.ai/api/v1`, billed per generation |
| Key entry page (`scripts/credential-ui/`) | Node.js 22.18+, a desktop keychain | local only; do not expose it |

## The API key

Upstream reads the key from the `ZENMUX_API_KEY` environment variable first, then
from the system keychain through `scripts/credential-ui`.

- On your own computer, follow `oil-motion/references/api-key-setup.md`: the skill
  opens a local page where you type the key into the keychain.
- In a Claude Code cloud session there is no desktop keychain. Save the key as a
  network secret for the host `zenmux.ai` on the environment. The session proxy then
  adds it to requests to that host, and `ZENMUX_API_KEY` only needs a placeholder
  value so the scripts start. The real key never enters the session.

Never commit a key, and never paste one into a chat.

## Known difference from the open-design copy

open-design had changed one FFmpeg flag in `scripts/motion_pipeline.py`
(`-vsync 0` to `-fps_mode passthrough`). Upstream at this commit still uses
`-vsync 0`. FFmpeg 6.1 accepts both. FFmpeg builds that have removed `-vsync` will
fail at frame extraction until upstream changes it.

## Updating

Replace `oil-motion/` with a newer upstream commit, run
`python3 scripts/scan_skill_source.py skills/oil-oil_oil-motion`, run
`python3 -m unittest discover -s skills/oil-oil_oil-motion/oil-motion/tests`, update
`.vendor-info.json`, then rebuild the index with `python3 scripts/build_skills_index.py`.
