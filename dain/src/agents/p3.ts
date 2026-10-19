// P3 · "Pass the Gig" referral. Deferred: no matching agent until the entry criteria hold.
// What exists now is the manual v0: the speaker names a peer, and this drafts an intro
// with a redacted brief for the speaker to send.
import type { Extraction } from "../contracts.js";

export interface ReferralReadiness {
  active_speakers: number;
  manual_referrals_done: number;
  referral_agreement_signed: boolean;
  consent_wording_approved: boolean;
}

export function referralAgentUnlocked(r: ReferralReadiness): { open: boolean; missing: string[] } {
  const missing: string[] = [];
  if (r.active_speakers < 25) missing.push(`${r.active_speakers}/25 active speakers`);
  if (r.manual_referrals_done < 5) missing.push(`${r.manual_referrals_done}/5 manual referrals`);
  if (!r.referral_agreement_signed) missing.push("referral agreement not signed");
  if (!r.consent_wording_approved) missing.push("consent wording not approved by legal");
  return { open: missing.length === 0, missing };
}

/** No organiser name, organisation or contact leaves until both sides approve and consent is on record. */
export function redactBrief(x: Extraction): Record<string, unknown> {
  return {
    event: { date: x.event.date, location: x.event.location, format: x.event.format, audience_size: x.event.audience_size, audience_type: x.event.audience_type },
    budget_signal: x.budget_signal,
  };
}

export function manualIntro(referrer: string, peer: string, x: Extraction, consentOnRecord: boolean): string {
  const b = redactBrief(x).event as Record<string, unknown>;
  const facts = [
    b.format && `a ${b.format}`,
    b.audience_type && `for ${b.audience_type}`,
    b.audience_size && `(about ${b.audience_size} people)`,
    b.location && `in ${b.location}`,
  ]
    .filter(Boolean)
    .join(" ");
  return [
    `Hi ${peer.split(" ")[0]},`,
    "",
    `I've been asked to speak at ${facts || "an event"} that I can't take on. I think it suits you.`,
    consentOnRecord
      ? "The organiser has agreed to be introduced. If you're interested, I'll connect you directly."
      : "I haven't shared the organiser's details. If you're interested, I'll ask whether they'd like an introduction.",
    "",
    referrer,
  ].join("\n");
}
