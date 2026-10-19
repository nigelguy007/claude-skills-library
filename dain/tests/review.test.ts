import { describe, expect, it } from "vitest";
import { Brain } from "../src/brain/store.js";
import { activeTime, EventLog, IDLE_GAP_MS } from "../src/events.js";
import { ActionGate } from "../src/gate.js";
import { diffChars, ReviewService } from "../src/review.js";
import { StateMachines, TransitionError } from "../src/state.js";

function setup() {
  const brain = new Brain();
  const log = new EventLog();
  const gate = new ActionGate(brain, log);
  const sm = new StateMachines(brain, log);
  return { brain, log, gate, sm, review: new ReviewService(brain, log, gate, sm) };
}

const specialist = { approver: "Sam (specialist)", role: "specialist" as const };
const speaker = { approver: "Helen Marsh", role: "speaker" as const };

function contentInReview(s: ReturnType<typeof setup>, id = "c1") {
  s.sm.create("ContentItem", id, "helen");
  for (const to of ["DRAFTED", "SCORED", "SPECIALIST_REVIEW"]) s.sm.transition("ContentItem", id, to);
  s.review.enqueue({ id, entity: "ContentItem", speaker_id: "helen", content: "Draft post", context: {} });
}

describe("edit time", () => {
  it("counts active time only, excluding idle gaps over 2 minutes", () => {
    const m = 60000;
    // open, typing for 3 minutes, 9 hours away, 1 more minute, approve
    const r = activeTime([0, m, 2 * m, 3 * m, 3 * m + 9 * 60 * m, 4 * m + 9 * 60 * m]);
    expect(r.active_ms).toBe(4 * m);
    expect(r.idle_excluded_ms).toBe(9 * 60 * m);
    expect(activeTime([0, IDLE_GAP_MS]).active_ms).toBe(IDLE_GAP_MS);
  });

  it("diffChars measures the changed span", () => {
    expect(diffChars("The rota was the problem.", "The rota was always the problem.")).toBe(7);
    expect(diffChars("same", "same")).toBe(0);
  });
});

describe("review module", () => {
  it("specialist approval moves to the speaker; only the speaker's approval issues a token", () => {
    const s = setup();
    contentInReview(s);
    expect(s.review.queue("specialist").map((i) => i.id)).toEqual(["c1"]);
    s.review.open("c1", "specialist", 0);
    expect(s.review.approve("c1", specialist, 60000)).toBeNull();
    expect(s.sm.get("ContentItem", "c1").state).toBe("SPEAKER_REVIEW");
    s.review.open("c1", "speaker", 0);
    expect(() => s.review.approve("c1", specialist, 1000)).toThrow(/only the speaker/);
    const token = s.review.approve("c1", speaker, 5 * 60000);
    expect(token?.content_hash).toBeTruthy();
    expect(s.sm.get("ContentItem", "c1").state).toBe("APPROVED");
    const closed = s.log.of("review.closed");
    expect(closed.map((e) => e.reviewer_role)).toEqual(["specialist", "speaker"]);
  });

  it("an edit after approval voids the token", () => {
    const s = setup();
    contentInReview(s);
    s.review.approve("c1", specialist, 0);
    s.review.open("c1", "speaker", 0);
    const t = s.review.approve("c1", speaker, 1000)!;
    s.review.open("c1", "speaker", 1500);
    s.review.edit("c1", "Changed after approval", 2000);
    expect(() => s.gate.validate(t.id, "c1", "Changed after approval")).toThrow(/voided/);
  });

  it("a guard-blocked reply cannot be approved until a human edits it", () => {
    const s = setup();
    s.sm.create("Enquiry", "e1", "helen");
    for (const to of ["EXTRACTED", "QUALIFIED", "REPLY_DRAFTED"]) s.sm.transition("Enquiry", "e1", to);
    s.review.enqueue({ id: "e1", entity: "Enquiry", speaker_id: "helen", content: "My fee is £6,000.", context: {}, blocked: [{ kind: "fee", match: "£6" }] });
    s.review.open("e1", "specialist", 0);
    expect(() => s.review.approve("e1", specialist, 1000)).toThrow(/blocked until edited/);
    s.review.edit("e1", "I'll come back with options once I know a little more.", 2000);
    expect(s.review.approve("e1", specialist, 3000)).not.toBeNull();
  });
});

describe("state machines", () => {
  it("refuses routes that don't exist and gated edges without a human", () => {
    const s = setup();
    s.sm.create("ContentItem", "c1", "helen");
    expect(() => s.sm.transition("ContentItem", "c1", "PUBLISHED")).toThrow(TransitionError);
    for (const to of ["DRAFTED", "SCORED", "SPECIALIST_REVIEW"]) s.sm.transition("ContentItem", "c1", to);
    expect(() => s.sm.transition("ContentItem", "c1", "SPEAKER_REVIEW")).toThrow(/needs a human approval/);
  });

  it("caps revise passes at 3", () => {
    const s = setup();
    s.sm.create("ContentItem", "c1", "helen");
    for (let i = 0; i < 3; i++) for (const to of ["DRAFTED", "SCORED", "REVISE"]) s.sm.transition("ContentItem", "c1", to);
    s.sm.transition("ContentItem", "c1", "DRAFTED");
    s.sm.transition("ContentItem", "c1", "SCORED");
    expect(() => s.sm.transition("ContentItem", "c1", "REVISE")).toThrow(/revise limit/);
    expect(s.sm.transition("ContentItem", "c1", "ESCALATED").state).toBe("ESCALATED");
  });

  it("the Canon refuses writes without a named human", () => {
    const s = setup();
    expect(() => s.brain.promote("blueprint", "helen", {}, { approver: "", role: "speaker" })).toThrow(/named human/);
    expect(() => s.brain.promote("blueprint", "helen", {}, { approver: "A2", role: "agent" as never })).toThrow(/named human/);
  });
});
