// B2 · Bookability Scoring. An independent checker: it receives the draft, the angle,
// the claims, the rubric and voice samples, and never A2's conversation. The verdict is
// computed in code from the scores, so the model cannot talk a draft through.
import { CRITERIA, ScoreResult, type Angle, type Claim, type Criterion, type Scores } from "../contracts.js";
import { callNode, type NodeContext } from "../llm.js";
import { loadPrompt } from "../prompts.js";

export interface Rubric {
  version: string;
  label: "provisional" | "calibrated";
  criteria: { id: Criterion; question: string }[];
  pass: { min_each: number; min_mean: number };
}

export const RUBRIC_V0: Rubric = {
  version: "v0",
  label: "provisional",
  criteria: [
    { id: "audience_fit", question: "Does it name a room an organiser would book for, and that room's problem?" },
    { id: "outcome_clarity", question: "Could a planner lift one line into a session description as 'attendees will leave with…'?" },
    { id: "credibility", question: "Is there a confirmed proof point from the Canon, stated no stronger than the claim?" },
    { id: "distinctiveness", question: "Would this read the same with another speaker's name on it? (5 = no, unmistakably theirs)" },
    { id: "timeliness", question: "Does it connect to a dated signal or current pressure?" },
    { id: "voice_match", question: "Does it sound like the speaker's samples (phrases, rhythm, register)?" },
  ],
  pass: { min_each: 3, min_mean: 3.8 },
};

const norm = (s: string) =>
  s
    .toLowerCase()
    .replace(/[‘’`]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/\s+/g, " ")
    .trim();

/** RULE: a score without a quote from the draft is rejected. Returns the criteria that fail. */
export function unquotedReasons(reasons: Record<Criterion, string>, draft: string): Criterion[] {
  const d = norm(draft);
  return CRITERIA.filter((c) => {
    // Double quotes per the prompt; apostrophes inside a quote ("What's…") are part of it.
    const r = norm(reasons[c] ?? "");
    const quotes = [...r.matchAll(/"([^"]{6,})"/g), ...r.matchAll(/(?:^|\s)'([^"]{6,}?)'(?=[\s.,;:!?]|$)/g)].map((m) => m[1]!.trim());
    return !quotes.some((q) => d.includes(q));
  });
}

export function verdictFor(scores: Scores, rubric: Rubric): "pass" | "revise" {
  const vals = CRITERIA.map((c) => scores[c]);
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  return vals.every((v) => v >= rubric.pass.min_each) && mean >= rubric.pass.min_mean ? "pass" : "revise";
}

export function lowestCriterion(scores: Scores): Criterion {
  return CRITERIA.reduce((lo, c) => (scores[c] < scores[lo] ? c : lo), CRITERIA[0]);
}

export interface ScoreInput {
  draft_text: string;
  angle: Angle;
  claims: Pick<Claim, "id" | "text" | "status">[];
  rubric: Rubric;
  voice_samples: string[];
}

export async function scoreDraft(ctx: NodeContext, input: ScoreInput): Promise<ScoreResult> {
  const out = await callNode(
    ctx,
    { node: "B2", system: loadPrompt("bookability/b2-scoring/score"), user: JSON.stringify(input) },
    ScoreResult,
    (o) => {
      const bad = unquotedReasons(o.reasons, input.draft_text);
      return bad.length ? `reasons must quote the draft; no draft quote found for: ${bad.join(", ")}` : null;
    },
  );
  const verdict = verdictFor(out.scores, input.rubric);
  const low = lowestCriterion(out.scores);
  return {
    ...out,
    verdict,
    revision_request: verdict === "pass" ? "" : out.revision_request || `Raise ${low}: ${out.reasons[low]}`,
    rubric_version: input.rubric.version,
    label: input.rubric.label,
  };
}
