import { describe, expect, it } from "vitest";
import { applyConfirmation } from "../src/agents/a1.js";
import { ATTRIBUTION_LINE, captureEnquiry, guardReply, isQualified, nullUnstated } from "../src/agents/p1.js";
import { EventLog } from "../src/events.js";
import { helenBlueprint, helenDecisions, helenWorld, leedsEnquiry, PROMPT } from "../src/fixtures/helen.js";

const bp = applyConfirmation(helenBlueprint(), { ...helenDecisions });
const ctx = (llm = helenWorld()) => ({ llm, log: new EventLog(), speaker_id: "helen", canon_version: "bp1" });
const raw = { channel: "email" as const, raw_text: leedsEnquiry, completeness: "full" as const, received_at: "2026-11-02T09:00:00Z" };

describe("reply guard", () => {
  it.each([
    ["My fee is £6,000 plus VAT.", "fee"],
    ["Usually around 6k for a keynote.", "fee"],
    ["I could do the 12th March.", "date"],
    ["How about 12/03?", "date"],
    ["I'm free on Thursday.", "date"],
    ["Consider it confirmed!", "commitment"],
    ["I'm available that week.", "commitment"],
    ["Happy to pencil it in.", "commitment"],
  ])("blocks %s", (text, kind) => {
    expect(guardReply(text).map((h) => h.kind)).toContain(kind);
  });

  it("passes a clean reply", () => {
    expect(guardReply("Thanks for thinking of me. Could you share the session length and your budget range? I'll come back with options.")).toEqual([]);
  });
});

describe("P1 capture", () => {
  it("nulls anything the enquiry didn't say", () => {
    const x = nullUnstated(
      {
        organiser: { name: "Jane Smith", org: "Leeds Council", role: null, email: null },
        event: { name: null, date: "2027-03-12", location: "Manchester", format: "keynote", audience_size: 500, audience_type: null },
        budget_signal: "none", deadline: null, angle_match: [], fit: "strong", missing_questions: [],
      },
      leedsEnquiry,
    );
    expect(x.organiser.name).toBeNull();
    expect(x.organiser.org).toBeNull();
    expect(x.event.location).toBeNull();
    expect(x.event.audience_size).toBeNull();
    expect(x.event.date).toBe("2027-03-12"); // "12 March" is in the text
  });

  it("drafts a reply with attribution and the approved consent line, and is not qualified yet", async () => {
    const r = await captureEnquiry(ctx(), raw, { name: "Helen Marsh", blueprint: bp, consent_line: "If Helen Marsh isn't free, we may suggest another speaker. We'll only share your details if you agree. [ ] Yes, that's fine" });
    expect(r.stage).toBe("REPLY_DRAFTED");
    expect(r.reply_draft).toContain(ATTRIBUTION_LINE);
    expect(r.reply_draft).toContain("only share your details if you agree");
    expect(r.blocked).toEqual([]);
    expect(r.extraction!.fit).toBe("strong");
    expect(isQualified(r.extraction!, false)).toBe(false); // no organiser or organisation named
  });

  it("blocks a reply that quotes the fee the organiser asked for", async () => {
    const llm = helenWorld().on(PROMPT.reply, () => ({ reply_draft: "Thanks! My fee for a closing keynote is £6,000. How did you come across me?" }));
    const r = await captureEnquiry(ctx(llm), raw, { name: "Helen Marsh", blueprint: bp });
    expect(r.blocked.map((b) => b.kind)).toContain("fee");
    expect(r.warnings[0]).toMatch(/consent wording not yet approved/);
  });

  it("never drafts from a LinkedIn snippet", async () => {
    const llm = helenWorld();
    const r = await captureEnquiry(ctx(llm), { ...raw, channel: "li_notification", completeness: "snippet" }, { name: "Helen Marsh", blueprint: bp });
    expect(r.stage).toBe("NEW");
    expect(r.reply_draft).toBeNull();
    expect(llm.calls).toHaveLength(0);
  });
});
