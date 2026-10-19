import { describe, expect, it } from "vitest";
import { applyConfirmation, confirmedShare, coverageGaps, followUpQuestions, writeBlueprint } from "../src/agents/a1.js";
import { EventLog } from "../src/events.js";
import { ContractError } from "../src/llm.js";
import { FakeLLM, helenBlueprint, helenDecisions, helenTranscript, PROMPT } from "../src/fixtures/helen.js";

const input = { transcript: helenTranscript, existing_assets: [], writing_samples: [], fee_band: "£5k–£8k", formats: ["keynote"], blueprint_version: "draft-0" };
const ctx = (llm: FakeLLM) => ({ llm, log: new EventLog(), speaker_id: "helen", canon_version: "bp0" });

describe("A1 Blueprint writer", () => {
  it("forces every claim to needs_evidence, whatever the model says", async () => {
    const llm = new FakeLLM().on(PROMPT.writer, () => {
      const bp = helenBlueprint();
      bp.claims[0]!.status = "speaker_confirmed";
      return bp;
    });
    const bp = await writeBlueprint(ctx(llm), input);
    expect(bp.claims.every((c) => c.status === "needs_evidence")).toBe(true);
  });

  it("rejects a claim cited to the interviewer's words, retries once, then fails the contract", async () => {
    const llm = new FakeLLM().on(PROMPT.writer, () => {
      const bp = helenBlueprint();
      bp.claims[3]!.source_quote_ts = "00:14:10"; // the interviewer's question, not Helen
      return bp;
    });
    await expect(writeBlueprint(ctx(llm), input)).rejects.toThrow(ContractError);
    expect(llm.count(PROMPT.writer)).toBe(2);
  });

  it("rejects an angle that cites a claim that doesn't exist", async () => {
    const llm = new FakeLLM().on(PROMPT.writer, () => {
      const bp = helenBlueprint();
      bp.angles[0]!.proof_claim_ids = ["C99"];
      return bp;
    });
    await expect(writeBlueprint(ctx(llm), input)).rejects.toThrow(/unknown claim C99/);
  });

  it("coverage checklist finds thin Blueprints and turns gaps into questions", () => {
    const bp = helenBlueprint();
    expect(coverageGaps(bp)).toEqual([]);
    const thin = { ...bp, claims: bp.claims.filter((c) => c.type === "metric" || c.type === "story") };
    const gaps = coverageGaps(thin);
    expect(gaps.some((g) => g.startsWith("only"))).toBe(true);
    expect(gaps.some((g) => g.startsWith("no reputation"))).toBe(true);
    const qs = followUpQuestions(gaps, { unsupported: [{ field: "claims.C3", statement: "fell to 4.5%", reason: "said about 4.5%" }] }, thin);
    expect(qs.some((q) => q.includes("rebooked"))).toBe(true);
    expect(qs.some((q) => q.includes("fell to 4.5%"))).toBe(true);
  });

  it("applies the speaker's ticks; unticked claims stay unconfirmed", () => {
    const bp = applyConfirmation(helenBlueprint(), { ...helenDecisions });
    expect(bp.claims.find((c) => c.id === "C4")!.status).toBe("needs_evidence");
    expect(confirmedShare(bp)).toBeCloseTo(6 / 7);
  });
});
