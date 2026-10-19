// End to end through the one front door: onboarding → Blueprint → weekly content →
// two-stage review → publish; enquiry → reply → send; restarts mid-flow; budgets.
import { describe, expect, it } from "vitest";
import { RUBRIC_V0 } from "../src/agents/b2.js";
import { Brain } from "../src/brain/store.js";
import { Conductor } from "../src/conductor/conductor.js";
import { runStatus } from "../src/conductor/runner.js";
import { dashboard, EventLog } from "../src/events.js";
import type { ActionAdapter } from "../src/gate.js";
import type { LLM } from "../src/llm.js";
import { FakeLLM, HELEN_ID, helenBlueprint, helenDecisions, helenProfile, helenScreener, helenTranscript, helenWorld, leedsEnquiry, PROMPT } from "../src/fixtures/helen.js";

const PL = { approver: "Priya (product lead)", role: "product_lead" as const };
const BS = { approver: "Sam (specialist)", role: "specialist" as const };
const HELEN = { approver: "Helen Marsh", role: "speaker" as const };

function adapter(action: "publish" | "send") {
  const sent: string[] = [];
  const byKey = new Map<string, string>();
  const a: ActionAdapter & { sent: string[] } = {
    action,
    sent,
    async execute({ content, idempotency_key }) {
      sent.push(content);
      const id = `${action}-${sent.length}`;
      byKey.set(idempotency_key, id);
      return id;
    },
    findExisting: async (k) => byKey.get(k) ?? null,
  };
  return a;
}

function world(llm: LLM = helenWorld()) {
  const brain = new Brain(() => new Date("2026-11-02T09:00:00Z"));
  const log = new EventLog(() => new Date("2026-11-02T09:00:00Z"));
  const adapters = { linkedin: adapter("publish"), email: adapter("send") };
  brain.promote("rubric", "current", RUBRIC_V0, PL);
  brain.promote("policy", "referral_consent", "If [Speaker] isn't free, we may suggest another speaker from our network. We'll only share your details with them if you agree. [ ] Yes", PL);
  brain.promote("bureau", "bureau-north", { id: "bureau-north", name: "North Speakers", contact: "Priya Shah", channel: "email", bio_lengths: ["short", "medium"], wants_one_sheet: true, photo_spec: "2000px", cadence_days: 90 }, BS);
  const make = () => new Conductor({ brain, log, llm, adapters });
  return { brain, log, adapters, make, c: make() };
}

async function onboardHelen(c: Conductor) {
  await c.dispatch("speaker.onboard", { speaker_id: HELEN_ID, profile: helenProfile, screener: helenScreener });
  await c.dispatch("interview.transcript", { speaker_id: HELEN_ID, transcript: helenTranscript });
  return c.dispatch("blueprint.confirm", { speaker_id: HELEN_ID, decisions: helenDecisions, approval: HELEN });
}

describe("conductor", () => {
  it("screens out speakers outside the pilot segment", async () => {
    const { c } = world();
    const r = await c.dispatch("speaker.onboard", { speaker_id: "x", profile: helenProfile, screener: { ...helenScreener, keynote_fee_gbp: 2000, goal: "new_work" } });
    expect(r).toMatchObject({ status: "done", value: { status: "screened_out" } });
  });

  it("refuses unknown commands and malformed payloads", async () => {
    const { c } = world();
    await expect(c.dispatch("publish.now" as never, {})).rejects.toThrow(/unknown command/);
    await expect(c.dispatch("content.weekly", { speaker_id: 1 })).rejects.toThrow();
  });

  it("onboards: pauses for the transcript and the speaker's confirmation, and only the speaker can confirm", async () => {
    const { c, brain } = world();
    expect(await c.dispatch("speaker.onboard", { speaker_id: HELEN_ID, profile: helenProfile, screener: helenScreener })).toEqual({ status: "paused", waiting_for: "interview.transcript" });
    expect(await c.dispatch("interview.transcript", { speaker_id: HELEN_ID, transcript: helenTranscript })).toEqual({ status: "paused", waiting_for: "blueprint.confirmation" });
    expect(c.sm.get("Speaker", HELEN_ID).state).toBe("BLUEPRINT_DRAFT");
    await expect(c.dispatch("blueprint.confirm", { speaker_id: HELEN_ID, decisions: helenDecisions, approval: BS })).rejects.toThrow(/speaker, not the team/);
    const r = await c.dispatch("blueprint.confirm", { speaker_id: HELEN_ID, decisions: helenDecisions, approval: HELEN });
    expect(r).toMatchObject({ status: "done", value: { status: "active" } });
    expect(brain.get("blueprint", HELEN_ID)?.approved_role).toBe("speaker");
    // A Canon change triggers a bureau pack, queued for a human.
    expect(c.review.queue("specialist").map((i) => i.entity)).toEqual(["AssetPack"]);
  });

  it("asks follow-up questions when the Blueprint is thin, then continues", async () => {
    let round = 0;
    const llm = helenWorld().on(PROMPT.writer, () => {
      const bp = helenBlueprint();
      return round++ === 0 ? { ...bp, claims: bp.claims.filter((c) => c.type !== "rebooking" && c.type !== "testimonial" && c.type !== "client"), angles: bp.angles.map((a) => ({ ...a, proof_claim_ids: ["C2"] })) } : bp;
    });
    const { c, brain } = world(llm);
    await c.dispatch("speaker.onboard", { speaker_id: HELEN_ID, profile: helenProfile, screener: helenScreener });
    expect(await c.dispatch("interview.transcript", { speaker_id: HELEN_ID, transcript: helenTranscript })).toEqual({ status: "paused", waiting_for: "interview.followup.1" });
    const asked = brain.read<{ questions: string[] }>("blueprint.draft", HELEN_ID)[0]!.payload.questions;
    expect(asked.some((q) => q.includes("rebooked"))).toBe(true);
    expect(await c.dispatch("interview.followup", { speaker_id: HELEN_ID, round: 1, segments: [] })).toEqual({ status: "paused", waiting_for: "blueprint.confirmation" });
  });

  it("weekly cycle: 3 drafts → specialist → speaker → published once, surviving a restart", async () => {
    const w = world();
    await onboardHelen(w.c);
    const weekly = await w.c.dispatch("content.weekly", { speaker_id: HELEN_ID, week: "2026-W45" });
    expect(weekly).toMatchObject({ status: "done", value: { status: "queued" } });
    const queue = w.c.review.queue("specialist").filter((i) => i.entity === "ContentItem");
    expect(queue).toHaveLength(3);
    expect(queue.every((i) => i.label === "provisional")).toBe(true);

    // The worker restarts: a new conductor over the same store.
    const c2 = w.make();
    const id = queue[0]!.id;
    await c2.dispatch("review.open", { item_id: id, role: "specialist", at_ms: 0 });
    expect(await c2.dispatch("review.approve", { item_id: id, approval: BS, at_ms: 4 * 60000 })).toEqual({ status: "moved_to_next_reviewer" });
    await c2.dispatch("review.open", { item_id: id, role: "speaker", at_ms: 0 });
    await c2.dispatch("review.edit", { item_id: id, content: `${queue[0]!.content}\n\nOne small change.`, at_ms: 60000 });
    const pub = await c2.dispatch("review.approve", { item_id: id, approval: HELEN, at_ms: 6 * 60000 });
    expect(pub).toMatchObject({ status: "done", value: { status: "published" } });
    expect(w.adapters.linkedin.sent).toEqual([`${queue[0]!.content}\n\nOne small change.`]);
    expect(c2.sm.get("ContentItem", id).state).toBe("PUBLISHED");
    expect(w.brain.canonOf("voice_sample")).toHaveLength(1);

    // The same weekly trigger firing twice does not draft again.
    const calls = (c2 as unknown as { deps: { llm: FakeLLM } }).deps.llm.calls.length;
    await c2.dispatch("content.weekly", { speaker_id: HELEN_ID, week: "2026-W45" });
    expect((c2 as unknown as { deps: { llm: FakeLLM } }).deps.llm.calls.length).toBe(calls);

    const d = dashboard(w.log);
    // Speaker opened at 0, edited at 1 min, approved at 6 min with no activity between:
    // the 5-minute gap is idle (> 2 min) and excluded, so the edit took 1 minute.
    expect(d.edit_time_min_median).toBe(1);
    expect(d.keep_rate).toBeCloseTo(1 / 3);
    expect(d.b2_first_pass_rate).toBe(1);
  });

  it("enquiry: captured, reply blocked until edited, approved, sent once", async () => {
    const llm = helenWorld().on(PROMPT.reply, () => ({ reply_draft: "Thanks! I'm available on 12 March. How did you come across me?" }));
    const w = world(llm);
    await onboardHelen(w.c);
    await w.c.dispatch("enquiry.capture", { speaker_id: HELEN_ID, enquiry_id: "enq-1", raw: { channel: "email", raw_text: leedsEnquiry, completeness: "full", received_at: "2026-11-02T08:30:00Z" } });
    expect(w.c.sm.get("Enquiry", "enq-1").state).toBe("REPLY_DRAFTED");
    const item = w.c.review.item("enq-1");
    expect(item.blocked.map((b) => b.kind).sort()).toEqual(["commitment", "date"]);
    expect(item.content).toContain("We'll only share your details");
    await w.c.dispatch("review.open", { item_id: "enq-1", role: "specialist", at_ms: 0 });
    await expect(w.c.dispatch("review.approve", { item_id: "enq-1", approval: BS, at_ms: 1000 })).rejects.toThrow(/blocked until edited/);
    await w.c.dispatch("review.edit", { item_id: "enq-1", content: "Thanks for thinking of me. Could you share the session length? How did you come across me?", at_ms: 2000 });
    expect(await w.c.dispatch("review.approve", { item_id: "enq-1", approval: BS, at_ms: 3000 })).toMatchObject({ value: { status: "sent" } });
    expect(w.adapters.email.sent).toHaveLength(1);
    expect(dashboard(w.log).capture_latency_ms_p90).toBe(30 * 60000);
  });

  it("a budget breach escalates the item instead of retrying silently", async () => {
    const inner = helenWorld();
    const greedy: LLM = { complete: async (r) => ({ ...(await inner.complete(r)), input_tokens: r.node === "A2" ? 50000 : 10 }) };
    const w = world(greedy);
    await onboardHelen(w.c);
    const r = (await w.c.dispatch("content.weekly", { speaker_id: HELEN_ID, week: "2026-W46" })) as { value: { items: { status: string; reason?: string }[] } };
    expect(r.value.items.every((i) => i.status === "escalated" && /budget/.test(i.reason ?? ""))).toBe(true);
    expect(runStatus(w.brain, `weekly:${HELEN_ID}:2026-W46`)?.status).toBe("done");
  });
});
