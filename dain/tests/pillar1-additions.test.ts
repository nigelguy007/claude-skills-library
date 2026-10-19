// The five Pillar I additions from the full read of the Drive folder: Blueprint document,
// operational boundaries, email/form approval, the 70% approval gate, and the 4 h review ceiling.
import { describe, expect, it } from "vitest";
import { applyConfirmation } from "../src/agents/a1.js";
import { boundaryFlags } from "../src/agents/a2.js";
import { RUBRIC_V0 } from "../src/agents/b2.js";
import { renderBlueprintDocument } from "../src/agents/blueprint-doc.js";
import { runContentLoop } from "../src/agents/content-loop.js";
import { reviewOverBudget } from "../src/agents/groundskeeper.js";
import { Brain } from "../src/brain/store.js";
import { Conductor } from "../src/conductor/conductor.js";
import { checkLaunchGates, dashboard, EventLog } from "../src/events.js";
import type { ActionAdapter } from "../src/gate.js";
import { HELEN_ID, helenBlueprint, helenDecisions, helenProfile, helenScreener, helenTranscript, helenWorld, PROMPT } from "../src/fixtures/helen.js";
import { newText, parseForm, parseReply } from "../src/review-reply.js";

const bp = applyConfirmation(helenBlueprint(), { ...helenDecisions });
const BS = { approver: "Sam (specialist)", role: "specialist" as const };

describe("1 · Blueprint document", () => {
  it("shows confirmed proof only, the claims ledger with status, and the boundaries", () => {
    const html = renderBlueprintDocument("Helen Marsh", bp, 1, "2026-11-02T09:00:00Z");
    expect(html).toContain("Personal Blueprint · version 1 · approved 2026-11-02");
    expect(html).toContain("Never named:");
    expect(html).toContain("St Aldric's");
    // C4 is unconfirmed: it appears in the ledger, flagged, but never as proof under a talk.
    expect(html).toContain("Not yet confirmed: we won't use this until you do");
    const talks = html.split("<h2>How you sound</h2>")[0]!;
    expect(talks).not.toContain("~30%");
  });
});

describe("2 · Operational boundaries", () => {
  it("flags a draft that touches an avoided topic or names a protected organisation", () => {
    expect(boundaryFlags("Pay disputes are the real story here.", bp)).toEqual(['breaks boundary: avoid topic "pay disputes"']);
    expect(boundaryFlags("At St Aldric's we changed the rota.", bp)).toEqual(['breaks boundary: names "St Aldric\'s"']);
    expect(boundaryFlags("The rota was the problem, not the people.", bp)).toEqual([]);
  });

  it("blocks the draft without spending a score, then asks for a fix", async () => {
    const llm = helenWorld().on(PROMPT.draft, (inp) =>
      inp.revision
        ? { text: "Heroics aren't a staffing plan.", hook_line: "Heroics", angle_id: "A1", claim_ids: ["C2"], self_flags: [] }
        : { text: "At St Aldric's the rota was the problem.", hook_line: "At St Aldric's", angle_id: "A1", claim_ids: ["C2"], self_flags: [] },
    );
    const log = new EventLog();
    const r = await runContentLoop({ llm, log, speaker_id: "helen", canon_version: "bp1" }, log, {
      item_id: "i1", speaker_id: "helen", blueprint: bp, slot: { angle_id: "A1", format: "story" }, rubric: RUBRIC_V0, recent_posts: [], voice_samples: [],
    });
    expect(r.passes[0]!.blocked_reason).toMatch(/names "St Aldric's"/);
    expect(r.status).toBe("pass");
    expect(llm.count(PROMPT.score)).toBe(1);
    expect(JSON.parse(llm.calls.find((c) => c.system.includes(PROMPT.draft))!.user).boundaries.do_not_name).toEqual(["St Aldric's"]);
  });
});

describe("3 · Approve / Edit / Reject by email or form", () => {
  it("parses replies and ignores quoted history", () => {
    expect(parseReply("Approve\n\nOn Mon, Sam wrote:\n> APPROVE?")).toEqual({ decision: "approve" });
    expect(parseReply("EDIT: Try one change on Monday.")).toEqual({ decision: "edit", text: "Try one change on Monday." });
    expect(parseReply("Reject - off voice, too salesy")).toMatchObject({ decision: "reject", reason: "off_voice" });
    expect(parseReply("EDIT")).toBeNull();
    expect(parseReply("Looks great but can we talk?")).toBeNull();
    expect(newText("hi\n-- \nHelen Marsh\nSpeaker")).toBe("hi");
    expect(parseForm({ decision: "edit", text: "  " })).toBeNull();
  });

  async function inSpeakerReview(boundaries?: { avoid_topics: string[]; do_not_name: string[]; notes: string[] }) {
    const brain = new Brain(() => new Date("2026-11-02T09:00:00Z"));
    const log = new EventLog(() => new Date("2026-11-02T09:00:00Z"));
    const posts: string[] = [];
    const linkedin: ActionAdapter = { action: "publish", execute: async ({ content }) => (posts.push(content), `p${posts.length}`), findExisting: async () => null };
    const email: ActionAdapter = { action: "send", execute: async () => "e1" };
    brain.promote("rubric", "current", RUBRIC_V0, { approver: "PL", role: "product_lead" });
    const c = new Conductor({ brain, log, llm: helenWorld(), adapters: { linkedin, email } });
    await c.dispatch("speaker.onboard", { speaker_id: HELEN_ID, profile: { ...helenProfile, bureau_ids: [] }, screener: helenScreener });
    await c.dispatch("interview.transcript", { speaker_id: HELEN_ID, transcript: helenTranscript });
    await c.dispatch("blueprint.confirm", { speaker_id: HELEN_ID, decisions: helenDecisions, boundaries, approval: { approver: "Helen Marsh", role: "speaker" } });
    await c.dispatch("content.weekly", { speaker_id: HELEN_ID, week: "2026-W45" });
    const id = c.review.queue("specialist").find((i) => i.entity === "ContentItem")!.id;
    c.review.open(id, "specialist", 0);
    c.review.approve(id, BS, 60000);
    return { c, brain, log, posts, id };
  }

  it("the speaker's edit by email is published exactly as typed, and is not counted as a 0-minute edit", async () => {
    const { c, log, posts, id } = await inSpeakerReview();
    const r = await c.dispatch("review.reply", { item_id: id, from: "Helen@Example.com", at_ms: 1, body: "EDIT\nMy own words, thanks.\n\n> original draft" });
    expect(r).toMatchObject({ value: { status: "published" } });
    expect(posts).toEqual(["My own words, thanks."]);
    const d = dashboard(log);
    expect(d.edit_time_min_median).toBeNull();
    expect(d.untimed_review_share).toBe(1);
  });

  it("refuses a reply from anyone but the speaker, and asks again when unclear", async () => {
    const { c, posts, id } = await inSpeakerReview();
    await expect(c.dispatch("review.reply", { item_id: id, from: "someone@else.com", at_ms: 1, body: "APPROVE" })).rejects.toThrow(/not the speaker/);
    expect(await c.dispatch("review.reply", { item_id: id, from: "helen@example.com", at_ms: 1, body: "hmm, maybe?" })).toMatchObject({ status: "unclear" });
    expect(await c.dispatch("review.reply", { item_id: id, from: "helen@example.com", at_ms: 1, form: { decision: "reject", reason: "tone" } })).toEqual({ status: "rejected", reason: "tone" });
    expect(posts).toEqual([]);
  });

  it("the speaker can replace their boundaries when confirming, and the document records it", async () => {
    const { brain } = await inSpeakerReview({ avoid_topics: ["pay disputes", "unions"], do_not_name: [], notes: ["No political comment"] });
    expect(brain.get<{ boundaries: { avoid_topics: string[]; do_not_name: string[] } }>("blueprint", HELEN_ID)!.value.boundaries).toMatchObject({ avoid_topics: ["pay disputes", "unions"], do_not_name: [] });
    const doc = brain.read<{ html: string }>("blueprint.document", HELEN_ID)[0]!.payload.html;
    expect(doc).toContain("unions");
    expect(doc).toContain("No political comment");
    expect(doc).not.toContain("St Aldric");
  });
});

describe("4 · Launch gate at 70% approval", () => {
  it("fails at 66%, passes at 70% with edits under 15 minutes", () => {
    const base = dashboard(new EventLog());
    expect(checkLaunchGates({ ...base, keep_rate: 0.66, edit_time_min_median: 9 }).failures).toEqual(["approval rate 66% (need ≥ 70%)"]);
    expect(checkLaunchGates({ ...base, keep_rate: 0.7, edit_time_min_median: 14.9 }).pass).toBe(true);
    expect(checkLaunchGates({ ...base, keep_rate: 0.8, edit_time_min_median: 15 }).failures[0]).toMatch(/median edit 15.0 min/);
  });
});

describe("5 · Review ceiling: 4 h per speaker per month", () => {
  it("flags a speaker over 4 specialist hours in 30 days, ignoring older reviews and speaker time", () => {
    const now = new Date("2026-11-30T00:00:00Z");
    let t = new Date("2026-10-01T00:00:00Z");
    const log = new EventLog(() => t);
    const close = (speaker_id: string, role: string, mins: number) =>
      log.emit({ type: "review.closed", item_id: "x", speaker_id, channel: "screen", reviewer_role: role, active_ms: mins * 60000, idle_excluded_ms: 0, diff_chars: 0, copied_out: false, outcome: "approved" });
    close("helen", "specialist", 600); // 10 h, but 60 days ago
    t = new Date("2026-11-20T00:00:00Z");
    close("helen", "specialist", 250);
    close("helen", "speaker", 500);
    close("raj", "specialist", 200);
    expect(reviewOverBudget(log, now.getTime())).toEqual([{ speaker_id: "helen", hours_30d: 4.17 }]);
  });
});
