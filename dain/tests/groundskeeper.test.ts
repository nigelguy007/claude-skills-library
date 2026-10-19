import { describe, expect, it } from "vitest";
import { applyConfirmation } from "../src/agents/a1.js";
import { nightlySweep, onboardingCap, specialistMustReview } from "../src/agents/groundskeeper.js";
import { Brain } from "../src/brain/store.js";
import { EventLog } from "../src/events.js";
import { helenBlueprint, helenDecisions } from "../src/fixtures/helen.js";
import { StateMachines } from "../src/state.js";

const DAY = 86400000;

describe("groundskeeper", () => {
  it("escalates items stuck 7 days, not 6, and pauses a speaker who left their own queue", () => {
    let now = new Date("2026-11-02T09:00:00Z");
    const brain = new Brain(() => now);
    const log = new EventLog(() => now);
    const sm = new StateMachines(brain, log);
    sm.create("Speaker", "helen", "helen");
    for (const to of ["INTERVIEW_BOOKED", "INTERVIEWED", "BLUEPRINT_DRAFT"]) sm.transition("Speaker", "helen", to);
    sm.transition("Speaker", "helen", "BLUEPRINT_APPROVED", { approver: "Helen", role: "speaker" });
    sm.transition("Speaker", "helen", "ACTIVE");
    sm.create("ContentItem", "c1", "helen");
    for (const to of ["DRAFTED", "SCORED", "SPECIALIST_REVIEW"]) sm.transition("ContentItem", "c1", to);
    sm.transition("ContentItem", "c1", "SPEAKER_REVIEW", { approver: "Sam", role: "specialist" });

    now = new Date(now.getTime() + 6 * DAY);
    expect(nightlySweep(brain, sm, log).escalated).toEqual([]);
    now = new Date(now.getTime() + 1 * DAY + 1);
    const r = nightlySweep(brain, sm, log);
    expect(r.escalated).toEqual(["c1"]);
    expect(r.paused_speakers).toEqual(["helen"]);
    expect(sm.get("Speaker", "helen").state).toBe("PAUSED");
  });

  it("flags unconfirmed claims, angles without fresh evidence, and a provisional rubric", () => {
    const brain = new Brain(() => new Date("2026-11-02T09:00:00Z"));
    brain.promote("blueprint", "helen", applyConfirmation(helenBlueprint(), { ...helenDecisions }), { approver: "Helen", role: "speaker" });
    brain.promote("angle_evidence", "helen:A1", { date: "2026-10-01" }, { approver: "Sam", role: "specialist" });
    const r = nightlySweep(brain, new StateMachines(brain, new EventLog()), new EventLog());
    expect(r.unconfirmed_claims).toEqual([{ speaker_id: "helen", claim_ids: ["C4"] }]);
    expect(r.stale_angle_evidence.map((x) => x.angle_id)).toEqual(["A2", "A3"]);
    expect(r.rubric_provisional).toBe(true);
  });

  it("onboarding cap uses measured minutes (F8's arithmetic: 30 h, 22 min → 81)", () => {
    expect(onboardingCap(30 * 60, 22 * 0.8)).toBe(81);
    expect(onboardingCap(30 * 60, 22)).toBe(65);
    expect(() => onboardingCap(1800, 0)).toThrow(/measured/);
  });

  it("risk-based review never skips flagged items or new speakers", () => {
    const base = { risk_based_enabled: true, speaker_weeks_active: 6, min_criterion_score: 4, new_claim_type: false, sensitive_topic: false, sample_failure_rate: 0.02, rand: () => 0.5 };
    expect(specialistMustReview(base)).toBe(false);
    expect(specialistMustReview({ ...base, rand: () => 0.05 })).toBe(true);
    expect(specialistMustReview({ ...base, speaker_weeks_active: 3 })).toBe(true);
    expect(specialistMustReview({ ...base, min_criterion_score: 2 })).toBe(true);
    expect(specialistMustReview({ ...base, sample_failure_rate: 0.06 })).toBe(true);
    expect(specialistMustReview({ ...base, risk_based_enabled: false })).toBe(true);
  });
});
