// Groundskeepers (Agentic OS): keep the machine from rotting. All code, all fully autonomous,
// all reversible: they flag, escalate and pause; they never publish, send or edit the Canon.
import type { Brain } from "../brain/store.js";
import type { Blueprint } from "../contracts.js";
import type { EventLog } from "../events.js";
import { HUMAN_WAIT_STATES, type StateMachines } from "../state.js";

const DAY = 86400000;
export const STUCK_DAYS = 7;
export const REINTERVIEW_DAYS = 182;
export const EVIDENCE_FRESH_DAYS = 90;
export const PACK_STALE_DAYS = 90;

export interface HealthReport {
  escalated: string[];
  paused_speakers: string[];
  reinterview_due: string[];
  unconfirmed_claims: { speaker_id: string; claim_ids: string[] }[];
  stale_angle_evidence: { speaker_id: string; angle_id: string }[];
  stale_bureau_packs: { speaker_id: string; bureau: string }[];
  rubric_provisional: boolean;
}

/** Nightly sweep: stuck items, stale facts, stale packs. */
export function nightlySweep(brain: Brain, sm: StateMachines, log: EventLog): HealthReport {
  const now = brain.clock().getTime();
  const r: HealthReport = { escalated: [], paused_speakers: [], reinterview_due: [], unconfirmed_claims: [], stale_angle_evidence: [], stale_bureau_packs: [], rubric_provisional: false };

  for (const item of sm.all()) {
    if (!HUMAN_WAIT_STATES.has(item.state) || item.state === "ESCALATED") continue;
    if (now - new Date(item.entered_at).getTime() < STUCK_DAYS * DAY) continue;
    if (item.entity === "ContentItem" || item.entity === "Enquiry") {
      const waiting = item.state;
      sm.transition(item.entity, item.id, "ESCALATED");
      log.emit({ type: "item.escalated", item_id: item.id, reason: `waiting in ${waiting} for ${STUCK_DAYS}+ days` });
      r.escalated.push(item.id);
      // A speaker who has gone quiet on their own review queue is paused, not nagged forever.
      if (waiting === "SPEAKER_REVIEW") {
        const sp = sm.all().find((s) => s.entity === "Speaker" && s.id === item.speaker_id && s.state === "ACTIVE");
        if (sp) {
          sm.transition("Speaker", sp.id, "PAUSED");
          r.paused_speakers.push(sp.id);
        }
      }
    }
  }

  for (const bp of brain.canonOf<Blueprint>("blueprint")) {
    if (now - new Date(bp.approved_at).getTime() > REINTERVIEW_DAYS * DAY) r.reinterview_due.push(bp.key);
    const pending = bp.value.claims.filter((c) => c.status === "needs_evidence").map((c) => c.id);
    if (pending.length) r.unconfirmed_claims.push({ speaker_id: bp.key, claim_ids: pending });
    for (const a of bp.value.angles) {
      const ev = brain.get<{ date: string }>("angle_evidence", `${bp.key}:${a.id}`);
      if (!ev || now - new Date(ev.value.date).getTime() > EVIDENCE_FRESH_DAYS * DAY) r.stale_angle_evidence.push({ speaker_id: bp.key, angle_id: a.id });
    }
  }

  const lastSent = new Map<string, number>();
  for (const e of brain.read<{ bureau: string }>("p2.sent")) {
    const k = `${e.speaker_id}|${e.payload.bureau}`;
    lastSent.set(k, Math.max(lastSent.get(k) ?? 0, new Date(e.at).getTime()));
  }
  for (const [k, t] of lastSent) {
    if (now - t > PACK_STALE_DAYS * DAY) {
      const [speaker_id, bureau] = k.split("|") as [string, string];
      r.stale_bureau_packs.push({ speaker_id, bureau });
    }
  }

  r.rubric_provisional = brain.get<{ label: string }>("rubric", "current")?.value.label !== "calibrated";
  brain.append("groundskeeper.report", null, r);
  return r;
}

/** R8: cap = floor(specialist minutes per week × 0.8 ÷ measured specialist minutes per speaker per week). */
export function onboardingCap(specialistMinutesPerWeek: number, measuredMinutesPerSpeakerPerWeek: number): number {
  if (measuredMinutesPerSpeakerPerWeek <= 0) throw new Error("need measured review minutes from R5 data, not an assumption");
  return Math.floor((specialistMinutesPerWeek * 0.8) / measuredMinutesPerSpeakerPerWeek);
}

/**
 * R8 risk-based routing, used only if the client approves it. After a speaker's first
 * 4 weeks the specialist sees B2-flagged items plus a random 10%. If the sample's failure
 * rate passes 5%, that speaker goes back to full review. Speaker approval is never skipped.
 */
export function specialistMustReview(args: {
  risk_based_enabled: boolean;
  speaker_weeks_active: number;
  min_criterion_score: number;
  new_claim_type: boolean;
  sensitive_topic: boolean;
  sample_failure_rate: number;
  rand: () => number;
}): boolean {
  if (!args.risk_based_enabled || args.speaker_weeks_active < 4 || args.sample_failure_rate > 0.05) return true;
  if (args.min_criterion_score < 3 || args.new_claim_type || args.sensitive_topic) return true;
  return args.rand() < 0.1;
}
