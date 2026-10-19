// R2 calibration and L1's first questions. Day 18: first check the humans agree
// (Cohen's kappa ≥ 0.6 on pass/revise); then B2 must sit within one point of the human
// consensus on ≥ 80% of criterion scores. Only then may B2 output label "calibrated".
import { CRITERIA, type Criterion, type Scores } from "../src/contracts.js";

export function cohensKappa(a: string[], b: string[]): number {
  if (a.length !== b.length || !a.length) throw new Error("need two equal, non-empty rating lists");
  const n = a.length;
  const cats = [...new Set([...a, ...b])];
  const po = a.filter((x, i) => x === b[i]).length / n;
  const pe = cats.reduce((s, c) => s + (a.filter((x) => x === c).length / n) * (b.filter((x) => x === c).length / n), 0);
  return pe === 1 ? 1 : (po - pe) / (1 - pe);
}

/** Share of criterion scores where B2 is within 1 point of the mean of the two humans. */
export function withinOneAgreement(b2: Scores[], humanA: Scores[], humanB: Scores[]): number {
  let hits = 0;
  let total = 0;
  b2.forEach((s, i) => {
    for (const c of CRITERIA) {
      const consensus = (humanA[i]![c] + humanB[i]![c]) / 2;
      if (Math.abs(s[c] - consensus) <= 1) hits++;
      total++;
    }
  });
  return total ? hits / total : 0;
}

/** Where B2 misses by more than a point, which criterion? Shows which one is mis-specified. */
export function overrideShareByCriterion(b2: Scores[], specialist: Scores[]): Record<Criterion, number> {
  const out = Object.fromEntries(CRITERIA.map((c) => [c, 0])) as Record<Criterion, number>;
  let misses = 0;
  b2.forEach((s, i) => {
    for (const c of CRITERIA)
      if (Math.abs(s[c] - specialist[i]![c]) > 1) {
        out[c]++;
        misses++;
      }
  });
  if (misses) for (const c of CRITERIA) out[c] /= misses;
  return out;
}

export interface CalibrationResult {
  kappa: number;
  within_one: number;
  label: "provisional" | "calibrated";
  action: string;
}

export function calibrate(args: { b2: Scores[]; humanA: Scores[]; humanB: Scores[]; humanAVerdicts: string[]; humanBVerdicts: string[] }): CalibrationResult {
  const kappa = cohensKappa(args.humanAVerdicts, args.humanBVerdicts);
  const within_one = withinOneAgreement(args.b2, args.humanA, args.humanB);
  if (kappa < 0.6) return { kappa, within_one, label: "provisional", action: "Humans disagree: the rubric is ambiguous. Reword criteria; don't tune B2." };
  if (within_one < 0.8) return { kappa, within_one, label: "provisional", action: "B2 misses human consensus. Inspect override share by criterion and fix the prompt." };
  return { kappa, within_one, label: "calibrated", action: "Promote the rubric with label calibrated (human approval)." };
}
