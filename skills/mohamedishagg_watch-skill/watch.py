#!/usr/bin/env python3
"""watch <link> — let Claude "watch" a short video from a link.

Downloads the video (Instagram reels/posts, TikTok, YouTube, X ... anything yt-dlp
understands), then makes three things a model can actually read:

  report.md        who posted it, the caption, length, counts, and the spoken words with times
  sheet_N.jpg      contact sheets: evenly spaced frames, each labelled with its timestamp
  frames/          the same frames full size (look at one when a sheet is not enough)

Everything lands in ~/.claude/watch/runs/<id>/ and the report is printed.

  watch-video https://www.instagram.com/reel/XXXX/
  watch-video <link> --cookies chrome        a private/age-gated post: borrow your logged-in browser
  watch-video <link> --frames 36             more frames (default: about one per 1.5 s, 12 to 36)
  watch-video <link> --at 3.2 7.5            also pull full-size frames at these seconds
  watch-video <link> --no-transcript         skip speech-to-text
  watch-video --clean                        delete everything downloaded (do this when you are done watching)

Instagram often wants a login even for public reels. If the download is refused, run it
again with --cookies chrome (or safari / firefox / brave / edge) while you are signed in
to Instagram in that browser. Cookies stay on this Mac; nothing is uploaded anywhere.
"""
import argparse, glob, json, os, re, subprocess, sys

HOME = os.path.expanduser("~/.claude/watch")
RUNS = os.path.join(HOME, "runs")
YTDLP = os.path.join(HOME, "venv", "bin", "yt-dlp")
WHISPER_PYTHONS = [
    os.path.join(HOME, "venv", "bin", "python"),
]


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def die(msg, code=1):
    print(f"watch: {msg}", file=sys.stderr)
    sys.exit(code)


def fmt_t(s):
    s = max(0.0, float(s))
    return f"{int(s // 60)}:{s % 60:04.1f}"


def short_count(n):
    if n is None:
        return "?"
    return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.1f}K" if n >= 1e4 else str(n)


# ---------------------------------------------------------------------------- download
def download(url, cookies):
    os.makedirs(RUNS, exist_ok=True)
    probe_cmd = [YTDLP, "--no-warnings", "--no-playlist", "-J", url]
    if cookies:
        probe_cmd[1:1] = ["--cookies-from-browser", cookies]
    probe = sh(probe_cmd)
    if probe.returncode != 0:
        err = (probe.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        hint = ""
        low = (probe.stderr or "").lower()
        if any(k in low for k in ("login", "log in", "rate-limit", "cookies", "empty media", "private", "403", "401")):
            hint = ("\n  Instagram wants a login for this one. Sign in to Instagram in your browser, then run:\n"
                    f"    watch-video {url} --cookies chrome     (or safari / firefox / brave / edge)")
        die(f"couldn't fetch that link: {err[0]}{hint}")
    info = json.loads(probe.stdout)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]
    vid = re.sub(r"[^A-Za-z0-9_-]", "", str(info.get("id") or "video"))[:40] or "video"
    out = os.path.join(RUNS, f"{(info.get('extractor_key') or 'x').lower()}_{vid}")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "video.mp4")
    if not os.path.exists(path):
        cmd = [YTDLP, "--no-warnings", "--no-playlist", "-q",
               "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
               "-o", os.path.join(out, "video.%(ext)s"), url]
        if cookies:
            cmd[1:1] = ["--cookies-from-browser", cookies]
        r = sh(cmd)
        if r.returncode != 0 or not os.path.exists(path):
            cands = glob.glob(os.path.join(out, "video.*"))
            if not cands:
                die("download failed: " + ((r.stderr or "").strip().splitlines() or ["?"])[-1])
            path = cands[0]
    return info, out, path


# ---------------------------------------------------------------------------- frames
def probe_video(path):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
            "-of", "json", path])
    j = json.loads(r.stdout or "{}")
    dur = float((j.get("format") or {}).get("duration") or 0)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in j.get("streams", []))
    return dur, v.get("width"), v.get("height"), has_audio


def make_frames(path, out, duration, n_frames, extra_at):
    fdir = os.path.join(out, "frames")
    os.makedirs(fdir, exist_ok=True)
    for f in glob.glob(os.path.join(fdir, "*.jpg")):
        os.remove(f)
    n = n_frames or max(12, min(36, int(duration / 1.5) or 12))
    n = max(1, min(n, 60))
    times = [duration * (i + 0.5) / n for i in range(n)]
    times += [t for t in extra_at if 0 <= t <= duration]
    times = sorted(set(round(t, 2) for t in times))
    files = []
    for t in times:
        fp = os.path.join(fdir, f"t{int(t*100):05d}.jpg")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
            "-vf", "scale='min(720,iw)':-2", "-q:v", "3", fp])
        if os.path.exists(fp):
            files.append((t, fp))
    return files


def contact_sheets(files, out, cols=4, rows=3, tile_w=300):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return []
    sheets = []
    per = cols * rows
    for si in range(0, len(files), per):
        chunk = files[si:si + per]
        ims = []
        for t, fp in chunk:
            im = Image.open(fp).convert("RGB")
            h = int(im.height * tile_w / im.width)
            ims.append((t, im.resize((tile_w, h))))
        th = max(im.height for _, im in ims)
        sheet = Image.new("RGB", (cols * tile_w, ((len(ims) + cols - 1) // cols) * th), (12, 12, 12))
        d = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        except Exception:
            font = ImageFont.load_default()
        for i, (t, im) in enumerate(ims):
            x, y = (i % cols) * tile_w, (i // cols) * th
            sheet.paste(im, (x, y))
            label = fmt_t(t)
            d.rectangle([x, y, x + 74, y + 26], fill=(0, 0, 0))
            d.text((x + 6, y + 3), label, fill=(255, 255, 255), font=font)
        sp = os.path.join(out, f"sheet_{si // per + 1}.jpg")
        sheet.save(sp, quality=88)
        sheets.append(sp)
    return sheets


# ---------------------------------------------------------------------------- transcript
WHISPER_SNIPPET = r"""
import sys, json
from faster_whisper import WhisperModel
m = WhisperModel("base", device="cpu", compute_type="int8")
segs, info = m.transcribe(sys.argv[1], vad_filter=True)
out = [{"s": round(s.start, 1), "e": round(s.end, 1), "t": s.text.strip()} for s in segs]
print(json.dumps({"lang": info.language, "segments": out}))
"""


def transcribe(path):
    audio = path[:-4] + ".wav"
    sh(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "16000", audio])
    if not os.path.exists(audio):
        return None
    try:
        for py in WHISPER_PYTHONS:
            if not os.path.exists(py):
                continue
            chk = sh([py, "-c", "import faster_whisper"])
            if chk.returncode != 0:
                continue
            r = sh([py, "-c", WHISPER_SNIPPET, audio])
            if r.returncode == 0 and r.stdout.strip():
                return json.loads(r.stdout.strip().splitlines()[-1])
        print("watch: installing the transcriber once (about a minute)...", file=sys.stderr)
        py = WHISPER_PYTHONS[-1]
        sh([py, "-m", "pip", "install", "-q", "faster-whisper"])
        r = sh([py, "-c", WHISPER_SNIPPET, audio])
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        try:
            os.remove(audio)
        except OSError:
            pass
    return None


# ---------------------------------------------------------------------------- report
def write_report(info, out, path, dur, w, h, has_audio, sheets, frames, tr, url):
    lines = ["# watch report", ""]
    who = info.get("uploader") or info.get("channel") or info.get("uploader_id") or "?"
    lines.append(f"- **Link:** {url}")
    lines.append(f"- **Posted by:** {who}" + (f" (@{info['uploader_id'].lstrip('@')})" if info.get("uploader_id") and info.get("uploader_id").lstrip("@") != who else ""))
    lines.append(f"- **Length:** {fmt_t(dur)}  ·  {w}x{h}  ·  audio: {'yes' if has_audio else 'none'}")
    counts = [f"{short_count(info.get(k))} {label}" for k, label in
              (("view_count", "views"), ("like_count", "likes"), ("comment_count", "comments")) if info.get(k) is not None]
    if counts:
        lines.append("- **Counts:** " + " · ".join(counts))
    if info.get("upload_date"):
        d = info["upload_date"]
        lines.append(f"- **Posted:** {d[:4]}-{d[4:6]}-{d[6:]}")
    for k, label in (("track", "Sound"), ("artist", "Artist")):
        if info.get(k):
            lines.append(f"- **{label}:** {info[k]}")
    lines += ["", "## Caption", "", (info.get("description") or info.get("title") or "(none)").strip(), ""]
    if tr is None:
        lines += ["## Spoken words", "", "(no audio track, or transcription skipped)" if not has_audio else "(transcription unavailable)", ""]
    else:
        segs = tr.get("segments") or []
        lines += [f"## Spoken words ({tr.get('lang', '?')})", ""]
        lines += [f"[{fmt_t(s['s'])}] {s['t']}" for s in segs] if segs else ["(no speech detected — music or silence)"]
        lines.append("")
    lines += ["## Look at these", ""]
    lines += [f"- {s}  (contact sheet, timestamp on each tile)" for s in sheets]
    lines.append(f"- {len(frames)} full-size frames in {os.path.join(out, 'frames')}/ (file name = seconds x100)")
    lines.append(f"- the video itself: {path}")
    text = "\n".join(lines)
    open(os.path.join(out, "report.md"), "w").write(text)
    return text


def main():
    ap = argparse.ArgumentParser(description="Watch a video from a link.")
    ap.add_argument("url", nargs="?")
    ap.add_argument("--cookies", metavar="BROWSER", help="chrome|safari|firefox|brave|edge — use that browser's login")
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--at", type=float, nargs="*", default=[], help="extra full-size frames at these seconds")
    ap.add_argument("--no-transcript", action="store_true")
    ap.add_argument("--clean", action="store_true", help="delete every downloaded video and its frames")
    a = ap.parse_args()

    if a.clean:
        import shutil
        n = len(glob.glob(os.path.join(RUNS, "*")))
        shutil.rmtree(RUNS, ignore_errors=True)
        print(f"watch: deleted {n} downloaded video folder(s) from {RUNS}")
        return
    if not a.url:
        ap.error("give me a link, or use --clean to delete everything downloaded")
    if not os.path.exists(YTDLP):
        die("yt-dlp is missing — run: python3 -m venv ~/.claude/watch/venv && ~/.claude/watch/venv/bin/pip install yt-dlp")
    if not re.match(r"^https?://", a.url):
        die("give me a full link starting with http(s)://")
    info, out, path = download(a.url, a.cookies)
    dur, w, h, has_audio = probe_video(path)
    frames = make_frames(path, out, dur, a.frames, a.at)
    sheets = contact_sheets(frames, out)
    tr = None if (a.no_transcript or not has_audio) else transcribe(path)
    print(write_report(info, out, path, dur, w, h, has_audio, sheets, frames, tr, a.url))
    print(f"\n(saved in {out})")


if __name__ == "__main__":
    main()
