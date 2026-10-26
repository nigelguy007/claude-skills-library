---
name: selfhost-pipecat-receptionist
description: Build and deploy a phone-answering AI receptionist for a trades business (plumber, electrician, HVAC) with Pipecat + Twilio - answers calls, captures job details, books or takes messages, texts the owner. Use when the user says "AI receptionist", "answer missed calls", "voice agent for a plumber", "Pipecat phone bot", or "deploy Pipecat for a client".
---

# Pipecat AI receptionist (trades)

Pipecat (github.com/pipecat-ai/pipecat, BSD-2 licence) is a **Python framework, not an app**. There is no admin UI. You write and maintain a bot. That is real engineering work, so price it that way.

Run `selfhost-vps-base` first.

## Architecture

```
Caller -> Twilio number -> TwiML <Connect><Stream> -> wss://bot.clientdomain.com/ws
       -> Pipecat pipeline: STT (Deepgram) -> LLM -> TTS (Cartesia / ElevenLabs)
       -> tools: create_booking(), take_message(), transfer_to_owner()
       -> SMS summary to the owner via the Twilio API after each call
```

Start from the official example rather than writing from scratch:
`github.com/pipecat-ai/pipecat-examples/tree/main/twilio-chatbot/inbound`

## Build

```bash
git clone https://github.com/pipecat-ai/pipecat-examples.git
cd pipecat-examples/twilio-chatbot/inbound
cp env.example .env        # TWILIO_*, DEEPGRAM_API_KEY, OPENAI/ANTHROPIC key, CARTESIA_API_KEY
uv sync
uv run bot.py -t twilio    # local test; expose with ngrok or cloudflared
```

Check the README in the cloned example for the current file names and environment variables. They change between releases.

Then customise:
1. **System prompt:** business name, service area, services offered and not offered, hours, emergency policy, call-out fee wording. Keep it short, because long prompts add latency.
2. **Function tools:**
   - `take_message(name, phone, address, problem, urgency)`: always available, and the fallback for everything.
   - `book_job(...)`: write to their real calendar or field-service tool (Google Calendar, Jobber, Housecall Pro, ServiceTitan) through its API. If they have no API-capable system, take a message and don't pretend to book.
   - `transfer_to_owner()`: Twilio call update to `<Dial>` their mobile for emergencies such as burst pipes, no heat in winter, or sparking.
3. **Post-call:** SMS or email the owner a summary with the caller's number, plus a call log row (Google Sheet or a small DB).

## Deploy

Pick one:
- **Your VPS:** containerise `bot.py`, put Caddy in front for `wss://`, and set the Twilio number's voice webhook / TwiML Bin to that URL. You own uptime.
- **Pipecat Cloud:** managed hosting with less ops. Its per-minute cost becomes another line item.

Keep the client's existing number. Set **conditional call forwarding** (no answer / busy) from their mobile or carrier to the Twilio number, so the bot only picks up calls they miss. Port the number only if they want the bot to answer everything.

## Things that will break it if you skip them

- **Latency:** over ~1 s of silence feels broken on a phone. Use streaming STT and TTS, a fast LLM, and a VPS region close to Twilio's media region. Test on a real phone over cellular, not a laptop.
- **Interruptions and noise:** callers ring from vans and job sites. Test barge-in and background noise.
- **Wrong bookings cost more than missed calls.** Confirm the address and time back to the caller, and have the bot read the details back.
- **Recording and AI disclosure:** several US states (CA, FL, IL, PA, WA and others) require all-party consent to record. Open with "This call may be recorded; I'm the virtual assistant for ...". Check the client's jurisdiction.
- **Outbound SMS in the US** needs A2P 10DLC registration on Twilio. It takes days to weeks, so start it on day one.

## Cost line items (variable, re-check current prices)

Telephony per minute (Twilio), STT per minute, LLM tokens, TTS per character or minute, the phone number per month, and hosting. Meter real calls for a week and bill usage as a pass-through or a capped bundle. Don't guess a flat number up front.

## Handover checklist

- [ ] 20+ test calls covering an emergency, an out-of-area caller, a price shopper, a hang-up, silence, and an angry caller
- [ ] Owner gets an SMS within 1 minute of every call
- [ ] Fallback: if the bot process is down, Twilio fails over to voicemail (set a fallback URL)
- [ ] Monthly call report: calls answered, messages taken, jobs booked. This report is your renewal pitch.
