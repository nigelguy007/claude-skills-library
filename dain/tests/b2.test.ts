import { describe, expect, it } from "vitest";
import { RUBRIC_V0, scoreDraft, unquotedReasons, verdictFor } from "../src/agents/b2.js";
import { EventLog } from "../src/events.js";
import { FakeLLM, goodScores, helenBlueprint, PROMPT } from "../src/fixtures/helen.js";

const draft = "Eighteen months ago a large NHS trust was spending more on agency staff every quarter. We changed three things.";
const angle = helenBlueprint().angles[1]!;
const input = { draft_text: draft, angle, claims: [], rubric: RUBRIC_V0, voice_samples: [] };
const ctx = (llm: FakeLLM) => ({ llm, log: new EventLog(), speaker_id: "helen", canon_version: "bp1" });

describe("B2 scorer", () => {
  it("pass needs every criterion ≥ 3 and a mean ≥ 3.8", () => {
    const all = (n: number) => ({ audience_fit: n, outcome_clarity: n, credibility: n, distinctiveness: n, timeliness: n, voice_match: n });
    expect(verdictFor(all(3), RUBRIC_V0)).toBe("revise");
    expect(verdictFor(all(4), RUBRIC_V0)).toBe("pass");
    expect(verdictFor({ ...all(5), timeliness: 2 }, RUBRIC_V0)).toBe("revise");
  });

  it("a reason must quote the draft word for word", () => {
    const reasons = goodScores(draft).reasons as Record<string, string>;
    expect(unquotedReasons(reasons as never, draft)).toEqual([]);
    expect(unquotedReasons({ ...reasons, credibility: "strong proof point" } as never, draft)).toEqual(["credibility"]);
    expect(unquotedReasons({ ...reasons, credibility: '"a huge saving for the NHS"' } as never, draft)).toEqual(["credibility"]);
  });

  it("accepts quotes that contain apostrophes, curly or straight", () => {
    const d = "What's the one rota rule your team would change tomorrow? Nobody's job was cut.";
    const r = { audience_fit: "“What’s the one rota rule” names a room", outcome_clarity: '"Nobody\'s job was cut" is an outcome' };
    expect(unquotedReasons({ ...goodScores(d).reasons, ...r } as never, d)).toEqual([]);
  });

  it("retries when reasons don't quote, and overrides the model's own verdict", async () => {
    let n = 0;
    const llm = new FakeLLM().on(PROMPT.score, () => {
      n++;
      if (n === 1) return { ...goodScores(draft), reasons: { ...goodScores(draft).reasons, voice_match: "sounds like her" } };
      return { ...goodScores(draft, { outcome_clarity: 2 }), verdict: "pass" }; // model says pass; code says revise
    });
    const r = await scoreDraft(ctx(llm), input);
    expect(llm.count(PROMPT.score)).toBe(2);
    expect(r.verdict).toBe("revise");
    expect(r.label).toBe("provisional");
    expect(r.revision_request).toMatch(/three changes/);
  });

  it("never sees the drafting conversation", async () => {
    const llm = new FakeLLM().on(PROMPT.score, () => goodScores(draft));
    await scoreDraft(ctx(llm), input);
    const sent = JSON.parse(llm.calls[0]!.user);
    expect(Object.keys(sent).sort()).toEqual(["angle", "claims", "draft_text", "rubric", "voice_samples"]);
  });
});
