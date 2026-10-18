# Meeting consultant ("Atlas")

An AI consultant you invite to Zoom, Google Meet or Microsoft Teams. It joins as a participant, transcribes the call, keeps a running brief and answers when someone says its name. It speaks up unprompted only when a point is worth the interruption. During the call it sends research agents after factual questions. Afterwards it writes a memo and a separate set of research and follow-up notes, and turns what it learned into a reusable skill. The same brain also runs as a standalone voice assistant at `/assistant`.

## What it does

| In the meeting | How |
|---|---|
| Joins and transcribes | [Recall.ai](https://recall.ai) bot. Low-latency transcripts with speaker names arrive about 1–3 s after speech |
| Answers when addressed | Someone says "Atlas …" out loud, or types `@atlas …` in chat. It waits for them to finish, then answers in chat, and optionally aloud |
| Acts as the domain expert | Every ~90 s it works out the domain and picks an expert persona. It also picks the most relevant playbooks from **every indexed skill**: this repo's 2,600+ plus any folder in `SKILLS_DIRS`, plus skills it learned in earlier meetings |
| Speaks up unprompted | Only when its own value score is ≥ 8/10, at most once every 4 minutes, never repeating itself. `/quiet` stops it |
| Researches live | When the room raises a factual question (competitor pricing, regulation, market size), it splits the question into sub-questions. Parallel web-searching sub-agents take one each, while ChatGPT, Perplexity and any custom service are asked for second opinions. The synthesis flags where sources disagree and gets posted back to the chat |
| Asks "hindsight" questions | When the meeting starts wrapping up, it posts the 3 questions it would ask after reading the whole transcript |
| Writes up afterwards | **Memo:** decisions, scope, risks with cheap tests, recommendations, next steps. **Notes (separate):** research write-ups, a follow-up pack per action item, plus more research agents on open questions |
| Gets better over time | It distils each meeting into a general playbook in `learned_skills/` (no names, no confidential figures) and loads it in later meetings on the same subject |

Chat commands: `/brief` `/questions` `/research <question>` `/agents` `/quiet` `/resume` `/voice on|off` `/skills` `/leave` `/help`

**Standalone assistant** (`/assistant`): add it to your phone's home screen. Tap to talk, or turn on hands-free and say "Atlas, …" while the page is open. Replies are read aloud. Via its tools it can search the web, ask other AI services for second opinions, start research agents (results arrive in the feed and are read out), join a meeting ("join my meeting at https://…"), and read back any meeting's memo and notes.

## Setup (about 20 minutes)

1. **Accounts and keys**
   - Anthropic API key (console.anthropic.com).
   - Recall.ai account and API key. Note your region (e.g. `us-east-1`).
   - Optional: OpenAI and Perplexity keys for second opinions, ElevenLabs or OpenAI for voice in meetings, a Slack incoming webhook for end-of-meeting notifications.
2. **Deploy.** Recall must be able to reach the server over HTTPS.
   - **Render (easiest):** New → Blueprint → this repo. It reads `render.yaml` at the repo root. Fill in the keys, then set `PUBLIC_BASE_URL` to the URL Render gives you.
   - **Any Docker host:** from the repo root, `docker build -f tools/meeting-consultant/Dockerfile -t meeting-consultant .`, then run it with the variables from `.env.example` and a volume on `/data`.
   - **Your laptop:** `pip install -r requirements.txt`, then `python -m consultant serve`. Expose it with `cloudflared tunnel --url http://localhost:8000` (or ngrok) and use that URL as `PUBLIC_BASE_URL`.
3. **Recall dashboard → Webhooks:** add `PUBLIC_BASE_URL/webhook/recall/status?token=<WEBHOOK_TOKEN>` and subscribe to `bot.done` and `bot.call_ended`. This lets it write up as soon as the call ends. Without this step it writes up after 15 minutes of silence, or when you click "Leave and write up now".
4. Open `PUBLIC_BASE_URL/?key=<ADMIN_TOKEN>` once to sign in. Check `PUBLIC_BASE_URL/healthz`: `config_problems` should be empty.

## Using it

- **Web form:** paste the meeting link, a topic and some context (who's attending, what you want to decide). The live page shows the brief, the chosen expert persona and playbooks, what the bot has said, and links to the memo and notes.
- **Command line:** `python -m consultant join <meeting-url> --topic "MVP scoping"`, or `python -m consultant ask "…"`. Set `SERVER_URL` and `ADMIN_TOKEN` first.
- **Assistant:** `PUBLIC_BASE_URL/assistant`.

Zoom bots may need the host to admit them. Teams chat only works if the tenant allows guests to chat.

## Limits

- **It costs money per meeting.** You pay Recall's per-hour bot pricing plus Claude usage. Claude usage rises with long meetings, research agents (each one is several web-searching calls) and Opus write-ups. Set `MAX_AUTO_RESEARCH` and the model variables to control it.
- **Transcription mishears.** Names and jargon get mangled, and the wake word can be missed. Pick a distinctive `WAKE_WORDS`. Typing `@atlas` always works.
- **Its voice is limited to short clips.** Spoken output uses Recall's Output Audio endpoint, which suits short questions. Long answers go to chat. A fully conversational voice agent would need Recall's Output Media (webpage) mode, which isn't built here.
- **Low-latency transcription is English only.**
- **Genspark** has no public API that I could find. Any service with an OpenAI-compatible API (Genspark if they offer one, OpenRouter, a local model) plugs in through `CUSTOM_LLM_*`.
- **The assistant isn't Siri.** A web page can't wake on a spoken word while it's closed, so hands-free only works while the page is open.
- **Learned skills are AI-written.** Review them before copying them into the main `skills/` library.
- **Everyone in the meeting should know it's there.** It posts and pins a notice on joining. Some jurisdictions require consent to record.

## Development

```
pip install -r requirements-dev.txt
python -m pytest
```

The tests simulate whole meetings against fake Recall and Claude clients: answering when addressed, the unprompted-contribution policy, research agents, hindsight questions, the memo, notes and learned skills, webhook auth, and the assistant's tool loop. They haven't been run against live Recall or Anthropic APIs.

Code map: `consultant/brain.py` (meeting logic) · `agents.py` (research agents) · `providers.py` (ChatGPT, Perplexity, custom) · `assistant.py` (standalone agent) · `skills.py` (index, retrieval, learned skills) · `recall.py` · `llm.py` · `app.py` (web server and pages).
