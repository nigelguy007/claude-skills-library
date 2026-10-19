import { describe, expect, it } from "vitest";
import { manualIntro, redactBrief, referralAgentUnlocked } from "../src/agents/p3.js";
import type { Extraction } from "../src/contracts.js";

const x: Extraction = {
  organiser: { name: "Jane Smith", org: "Leeds Council", role: "Head of L&D", email: "jane@leeds.example" },
  event: { name: "Workforce Summit", date: "2027-03-12", location: "Leeds", format: "keynote", audience_size: 300, audience_type: "HR leaders" },
  budget_signal: "none", deadline: null, angle_match: [], fit: "strong", missing_questions: [],
};

describe("P3 manual referral", () => {
  it("the redacted brief carries no organiser data", () => {
    const s = JSON.stringify(redactBrief(x));
    for (const v of ["Jane", "Leeds Council", "jane@", "Head of L&D"]) expect(s).not.toContain(v);
    expect(manualIntro("Helen", "Sam Okafor", x, false)).not.toContain("Jane");
  });

  it("the agent stays locked until every entry criterion holds", () => {
    expect(referralAgentUnlocked({ active_speakers: 8, manual_referrals_done: 1, referral_agreement_signed: false, consent_wording_approved: true })).toEqual({
      open: false,
      missing: ["8/25 active speakers", "1/5 manual referrals", "referral agreement not signed"],
    });
    expect(referralAgentUnlocked({ active_speakers: 25, manual_referrals_done: 5, referral_agreement_signed: true, consent_wording_approved: true }).open).toBe(true);
  });
});
