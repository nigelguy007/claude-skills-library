import { describe, expect, it } from "vitest";
import { calibrate, cohensKappa, overrideShareByCriterion, withinOneAgreement } from "../evals/calibration.js";

const s = (n: number, o: Partial<Record<string, number>> = {}) => ({ audience_fit: n, outcome_clarity: n, credibility: n, distinctiveness: n, timeliness: n, voice_match: n, ...o });

describe("calibration (R2, Day 18)", () => {
  it("kappa: 1 for identical, ≤ 0 for chance-level ratings", () => {
    expect(cohensKappa(["pass", "revise", "pass"], ["pass", "revise", "pass"])).toBe(1);
    expect(cohensKappa(["pass", "pass", "revise", "revise"], ["pass", "revise", "pass", "revise"])).toBeCloseTo(0);
  });

  it("within-one agreement and override share point at the mis-specified criterion", () => {
    const b2 = [s(4), s(4, { timeliness: 1 })];
    const h = [s(4), s(4)];
    expect(withinOneAgreement(b2, h, h)).toBeCloseTo(11 / 12);
    expect(overrideShareByCriterion(b2, h).timeliness).toBe(1);
  });

  it("humans who disagree mean reword the rubric, not tune B2", () => {
    const r = calibrate({ b2: [s(4)], humanA: [s(4)], humanB: [s(4)], humanAVerdicts: ["pass", "pass", "revise", "revise"], humanBVerdicts: ["pass", "revise", "pass", "revise"] });
    expect(r.label).toBe("provisional");
    expect(r.action).toMatch(/Reword/);
    expect(calibrate({ b2: [s(4)], humanA: [s(4)], humanB: [s(4)], humanAVerdicts: ["pass", "revise"], humanBVerdicts: ["pass", "revise"] }).label).toBe("calibrated");
  });
});
