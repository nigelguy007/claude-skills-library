# watch

A Claude Code skill that lets Claude actually **watch** a video from a link (Instagram reels, TikTok, YouTube, X, anything yt-dlp supports).

It downloads the video, pulls out frames into labelled contact sheets, transcribes every spoken word with timestamps, and hands Claude both. When you are done, it deletes the video.

## Install

```bash
git clone https://github.com/mohamedishagg/watch-skill ~/watch-skill
bash ~/watch-skill/install.sh
```
Needs `python3` and `ffmpeg` (`brew install ffmpeg`). Then restart Claude Code, paste a link and say **watch this**.

## Notes
- Instagram often wants a login: sign in to Instagram in your browser and Claude will re-run with `--cookies chrome`. Cookies are read locally and never leave your machine.
- Speech-to-text runs locally (faster-whisper); nothing is uploaded.
- Only use it on videos you are allowed to view. Not affiliated with Instagram, TikTok, YouTube, X or Anthropic.

Made by [@_mosvlih](https://instagram.com/_mosvlih).
