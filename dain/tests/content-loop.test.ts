import { describe, expect, it } from "vitest";
import { applyConfirmation } from "../src/agents/a1.js";
import { planWeek } from "../src/agents/a2.js";
import { RUBRIC_V0 } from "../src/agents/b2.js";
import { runContentLoop } from "../src/agents/content-loop.js";
import { EventLog } from "../src/events.js";
import { goodScores, helenBlueprint, helenDecisions, helenWorld, PROMPT } from "../src/fixtures/helen.js";

const bp = applyConfirmation(helenBlueprint(), { ...helenDecisions });
const base = { item_id: "helen:w1:1", speaker_id: "helen", blueprint: bp, rubric: RUBRIC_V0, recent_posts: [], voice_samples: [] };

describe("weekly plan", () => {
  it("three slots, three angles, at least one proof post", () => {
    const slots = planWeek(bp, []);
    expect(slots).toHaveLength(3);
    expect(new Set(slots.map((s) => s.angle_id)).size).toBe(3);
    expect(slots.some((s) => s.format === "proof")).toBe(true);
  });

  it("never repeats an (angle, format) pair from the last six posts", () => {
    const recent = [
      { angle_id: "A1", format: "story" as const },
      { angle_id: "A2", format: "proof" as const },
      { angle_id: "A3", format: "contrarian" as const },
      { angle_id: "A1", format: "lesson" as const },
    ];
    const slots = planWeek(bp, recent);
    for (const s of slots) expect(recent.some((r) => r.angle_id === s.angle_id && r.format === s.format)).toBe(false);
  });
});

describe("A2 ↔ B2 loop", () => {
  it("blocks a draft that uses an unconfirmed claim without spending a B2 call", async () => {
    const llm = helenWorld().on(PROMPT.draft, (inp) =>
      inp.revision
        ? { text: "Heroics aren't a staffing plan. Ask who owns the handover.", hook_line: "Heroics aren't a staffing plan.", angle_id: "A2", claim_ids: ["C7"], self_flags: [] }
        : { text: "Agency spend fell by about 30%. Nobody was made redundant.", hook_line: "Agency spend fell", angle_id: "A2", claim_ids: ["C4"], self_flags: [] },
    );
    const log = new EventLog();
    const r = await runContentLoop({ llm, log, speaker_id: "helen", canon_version: "bp1" }, log, { ...base, slot: { angle_id: "A2", format: "proof" } });
    expect(r.passes[0]!.blocked_reason).toMatch(/unconfirmed claim C4/);
    expect(r.passes[0]!.score).toBeUndefined();
    expect(r.status).toBe("pass");
    expect(llm.count(PROMPT.score)).toBe(1);
  });

  it("feeds back only the lowest criterion and escalates after 3 passes", async () => {
    const llm = helenWorld().on(PROMPT.score, (inp) => goodScores(inp.draft_text, { outcome_clarity: 2 }));
    const log = new EventLog();
    const r = await runContentLoop({ llm, log, speaker_id: "helen", canon_version: "bp1" }, log, { ...base, slot: { angle_id: "A1", format: "story" } });
    expect(r.status).toBe("escalated");
    expect(r.passes).toHaveLength(3);
    const second = JSON.parse(llm.calls.filter((c) => c.system.includes(PROMPT.draft))[1]!.user);
    expect(second.revision.request).toMatch(/three changes/);
    expect(log.of("item.escalated")).toHaveLength(1);
  });
});
