---
name: dain-p3-referral
description: Manual v0 of "Pass the Gig". When a speaker declines an enquiry, they name a peer and Dain drafts an intro with a redacted brief for the speaker to send. The matching agent stays locked until 25 active speakers, 5 manual referrals, a signed referral agreement and approved consent wording.
component: P3
department: pipeline
archetype: builder
owner: PL
---

# P3 · Pass the Gig (manual v0)

## Purpose
- **Role:** keeps the client relationship with the referrer when a speaker can't take a job.
- **Goal (pilot):** find out whether speakers actually pass work on, before building anything.
- **Success:** referral accepted rate; client retained by referrer; consent rate per enquiry.

## 1 · Name and trigger
Speaker moves an enquiry to declined and names a peer.

## 2 · When to use
Pilot only, by hand. **Not** automatic matching. With 5–10 pilot speakers the pool is nearly empty (F7).

## 3 · Inputs
The enquiry's extraction; the peer's name; whether consent is on record (the opt-in line P1 adds from Day 14).

## 4 · Steps
1. `redactBrief` strips the organiser's name, organisation and contact.
2. `manualIntro` drafts the email for the speaker to send.
3. Organiser details are shared only after both the referrer approves and consent is on record.

## 5 · Handoffs
To the speaker, who sends it. Counted toward the 5-manual-referrals entry criterion.

## Entry criteria for the agent (`referralAgentUnlocked`)
≥ 25 active speakers · ≥ 5 manual referrals · referral agreement signed · consent wording approved by legal.

## Rules
UK GDPR: no organiser personal data to a third party without a lawful basis and a privacy notice that covers it. The consent wording is a draft, not legal advice. Referral fees (who invoices, VAT) are a client decision.

## Test
`tests/p3.test.ts`: the redacted brief contains no organiser fields; the gate stays shut until every criterion holds.

## Workflows and autonomy
| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Speaker names a peer; redacted intro drafted | human-led | yes |
