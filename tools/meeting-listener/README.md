# MVP Meeting Listener

A single HTML page that listens through your laptop mic during a meeting, transcribes it live, and keeps a running MVP brief (scope, decisions, open questions, risky assumptions, pushback, action items) updated by Claude.

## Use
1. Open `index.html` in **Chrome or Edge** (live speech needs one of these).
2. Open **Setup**, paste an Anthropic API key (stored only in your browser), and add a line of meeting context.
3. Press **Start listening** and allow the microphone.
4. The brief updates automatically every 60 s. Use **Ask** for questions mid-meeting.
5. Afterwards: **Download .md** for the brief and full transcript.

## Limits
- It only hears what your mic hears. On a video call with headphones it will only catch your voice. Play the call through your speakers, or paste the platform's live captions into the box.
- No speaker labels, and some words will be misheard.
- Tell attendees the meeting is being transcribed.
