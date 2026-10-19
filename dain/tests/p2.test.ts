import { describe, expect, it } from "vitest";
import { applyConfirmation } from "../src/agents/a1.js";
import { changesSince, coverNote, packFor, renderPack, type BureauProfile } from "../src/agents/p2.js";
import { helenBlueprint, helenDecisions } from "../src/fixtures/helen.js";

const bp = applyConfirmation(helenBlueprint(), { ...helenDecisions });
const bureau: BureauProfile = { id: "bureau-north", name: "North Speakers", contact: "Priya Shah", channel: "email", bio_lengths: ["short", "long"], wants_one_sheet: true, photo_spec: "2000px", cadence_days: 90 };

describe("P2 asset pack", () => {
  it("uses only confirmed claims, and includes reputation proof", () => {
    const files = renderPack("Helen Marsh", bp, "bp1", []);
    const all = files.map((f) => f.content).join("\n");
    expect(all).not.toContain("~30%"); // C4 is still needs_evidence
    expect(all).toContain("Rebooked by the CIPD regional group");
    expect(files.find((f) => f.name === "one_sheet.html")!.content).toContain("What clients say and do");
  });

  it("lists what changed in plain words", () => {
    const next = structuredClone(bp);
    next.angles[0]!.promise = "A new promise";
    next.claims.find((c) => c.id === "C4")!.status = "speaker_confirmed";
    expect(changesSince(bp, next)).toEqual(["Refreshed talk: Rotas, Not Heroes", "New results and credentials"]);
    expect(changesSince(undefined, bp)[0]).toMatch(/First pack/);
  });

  it("packs only what the bureau asked for, with a fee-free cover note", () => {
    const files = packFor(bureau, renderPack("Helen Marsh", bp, "bp1", []));
    expect(files.map((f) => f.name).sort()).toEqual(["bio_long.txt", "bio_short.txt", "one_sheet.html", "talks.md"]);
    expect(coverNote(bureau, "Helen Marsh", ["Updated bios"], "bp2")).toMatch(/^Hi Priya,/);
    expect(() => coverNote(bureau, "Helen Marsh", ["New fee: £8,000"], "bp2")).toThrow(/must not contain fees/);
  });
});
