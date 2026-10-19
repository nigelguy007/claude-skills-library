// The conductor's front door: every command it accepts, validated at the boundary.
import { z } from "zod";
import { RawEnquiry, TranscriptSegment } from "../contracts.js";

const ApprovalIn = z.object({ approver: z.string().min(1), role: z.enum(["speaker", "specialist", "product_lead"]) });

export const SpeakerProfile = z.object({
  name: z.string().min(1),
  fee_band: z.string(),
  tier: z.enum(["T1", "T2", "T3"]),
  voice_samples: z.array(z.string()),
  bureau_ids: z.array(z.string()),
  clips: z.array(z.string()),
  baseline_enquiries_6m: z.number().int().min(0),
});
export type SpeakerProfile = z.infer<typeof SpeakerProfile>;

// R11 screener. The thresholds are the spec's proposed segment; the client sets the final ones.
export const Screener = z.object({
  keynote_fee_gbp: z.number(),
  paid_talks_12m: z.number().int(),
  speaking_income_share: z.number().min(0).max(1),
  bureaus: z.array(z.string()),
  goal: z.enum(["more_bookings", "higher_fees", "new_work"]),
});
export type Screener = z.infer<typeof Screener>;

export function screen(s: Screener): { pass: boolean; reasons: string[] } {
  const reasons: string[] = [];
  if (s.keynote_fee_gbp < 5000 || s.keynote_fee_gbp > 15000) reasons.push("keynote fee outside £5k–£15k");
  if (s.paid_talks_12m < 10) reasons.push("fewer than 10 paid talks in 12 months");
  if (s.speaking_income_share < 0.5) reasons.push("speaking is not their main income");
  if (s.bureaus.length < 1) reasons.push("no bureau lists them");
  if (s.goal !== "more_bookings") reasons.push("goal is not more bookings (a different product; see R11)");
  return { pass: reasons.length === 0, reasons };
}

export const COMMANDS = {
  "speaker.onboard": z.object({ speaker_id: z.string().min(1), profile: SpeakerProfile, screener: Screener }),
  "interview.transcript": z.object({
    speaker_id: z.string(),
    transcript: z.array(TranscriptSegment).min(1),
    existing_assets: z.array(z.string()).default([]),
    writing_samples: z.array(z.string()).default([]),
    formats: z.array(z.string()).default(["keynote"]),
  }),
  "interview.followup": z.object({ speaker_id: z.string(), round: z.number().int().min(1), segments: z.array(TranscriptSegment) }),
  "blueprint.confirm": z.object({
    speaker_id: z.string(),
    decisions: z.record(z.enum(["speaker_confirmed", "needs_evidence", "rejected"])),
    approval: ApprovalIn,
  }),
  "content.weekly": z.object({ speaker_id: z.string(), week: z.string() }),
  "review.open": z.object({ item_id: z.string(), role: ApprovalIn.shape.role, at_ms: z.number() }),
  "review.edit": z.object({ item_id: z.string(), content: z.string().min(1), at_ms: z.number() }),
  "review.approve": z.object({ item_id: z.string(), approval: ApprovalIn, at_ms: z.number() }),
  "enquiry.capture": z.object({ speaker_id: z.string(), enquiry_id: z.string(), raw: RawEnquiry }),
  "radar.weekly": z.object({
    week: z.string(),
    sources: z.array(z.object({ sector: z.string(), source_type: z.enum(["agenda", "call_for_speakers", "bureau_trending", "enquiries", "booker_interviews"]), url: z.string().url(), fee_paying: z.boolean().optional() })),
  }),
  "radar.promote": z.object({ speaker_id: z.string(), angle_id: z.string(), evidence: z.array(z.object({ url: z.string(), quote: z.string(), date: z.string(), event: z.string() })).min(1), approval: ApprovalIn }),
  "pack.render": z.object({ speaker_id: z.string() }),
  "pack.sent": z.object({ speaker_id: z.string(), bureau_id: z.string(), pack_version: z.string(), approval: ApprovalIn }),
  "sweep.answer": z.object({ speaker_id: z.string(), week: z.string(), missed_count: z.number().int().min(0) }),
  nightly: z.object({}),
} as const;

export type Command = keyof typeof COMMANDS;
export type Payload<C extends Command> = z.infer<(typeof COMMANDS)[C]>;

/** Schedules for the workflow engine's cron triggers (Europe/London). */
export const SCHEDULES = [
  { command: "content.weekly", cron: "0 7 * * 1", note: "per ACTIVE speaker, Monday 07:00" },
  { command: "radar.weekly", cron: "0 6 * * 0", note: "Sunday 06:00, from Day 16" },
  { command: "nightly", cron: "0 2 * * *", note: "groundskeeper sweep" },
  { command: "sweep.ask", cron: "0 16 * * 5", note: "P1 'any enquiries we missed?' Friday 16:00" },
] as const;
