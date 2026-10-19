---
name: dain-p1-capture
description: Turn every forwarded email, web-form submission, pasted or shared LinkedIn message into a structured enquiry on the booking board, with missing questions and a reply draft that cannot quote a fee, name a date or commit the speaker. Use whenever an enquiry arrives at the speaker's Dain address, form or paste box. Not for outbound prospecting or sending anything.
component: P1
department: pipeline
archetype: analyst
owner: TL
---

# P1 · Lead Capture & Pipeline

## Purpose
- **Role:** the front desk that never forgets and never over-promises.
- **Goal:** no enquiry waits; speed of reply becomes the advantage.
- **For:** the speaker and the booking specialist.
- **Success:** 100% of forwarded enquiries logged within 1 h; reply drafted within 4 h; ≥ 95% field accuracy on the 50-enquiry test set; zero drafts with a commitment.

## 1 · Name and trigger
`enquiry.capture { speaker_id, enquiry_id, raw }`, fired by the inbound email parser, the web form, the paste box or the phone share target.

## 2 · When to use
Every inbound enquiry, on any channel Dain can legally reach.
**Not** LinkedIn inbox reading: there is no API for it, and scraping breaches the User Agreement and puts the speaker's account at risk.

## 3 · Inputs (knowledge)
The raw text and channel; the speaker's approved angles (for fit); the approved referral-consent wording (Canon `policy/referral_consent`).

### The LinkedIn capture ladder (R3)
1. **Notification forward:** an email rule forwards LinkedIn's "new message" emails → `completeness: snippet` → no reply; ask the speaker to paste the thread.
2. **Paste or share:** paste box, or "Share → Dain" from the LinkedIn app.
3. **Move enquiries off LinkedIn:** A2 suggests a profile line "For bookings: [form link]".
4. **Weekly sweep:** Friday "any enquiries we missed?" → `sweep.answer`, which measures coverage.

## 4 · Steps
1. Snippet? Stop at stage NEW and ask for the full thread.
2. `extract.prompt.md` fills the contract. Code nulls any organiser, location or size the text didn't state.
3. `reply.prompt.md` drafts a reply asking the missing questions.
4. Code appends the attribution question ("how did you come across me?", R10) if missing, and the approved consent line (R7).
5. Code guard scans for fees, dates and commitment words. Any hit blocks approval until a human edits it.
6. Card lands on the board at REPLY_DRAFTED with a next action due in 4 h.

## 5 · Handoffs
- **To B3:** the reply, with blocked hits shown, in the specialist queue.
- **To the Action Gate:** only after approval, as an email send.
- **To B1 (later):** anonymised enquiry themes.

## Rules
- Fields not in the text are null, never guessed.
- No fee, date, availability or "confirmed" in any draft, ever. Humans own pricing and commitments.
- Every reply asks how the organiser found the speaker.

## Examples
"…regional workforce summit in Leeds on 12 March, about 300 HR and ops leads… closing keynote? What are your fees?" → organiser name and org null, location Leeds, size 300, budget_signal none, fit strong (angle A2), missing: organisation and role, session length, budget range, in person or hybrid.

## Tools
Inbound email parsing, calendar (read only), internal board for the pilot; CRM connectors (Composio) after launch for speakers who ask.

## Test before real speakers
50 real past enquiries, names removed. Almost every field correct, no draft makes a commitment. `tests/p1.test.ts` covers the guard and the null rule.

- [ ] Correct: nothing guessed
- [ ] Uses tools: never sends
- [ ] Edge cases: snippet only; fee asked directly; date in the enquiry echoed in the reply (blocked)

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Capture and extract an enquiry onto the board | fully-autonomous | no |
| Draft the reply | human-assisted | no |
| Quote fees, hold dates, accept terms | human-led | yes |
