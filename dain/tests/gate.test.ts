import { describe, expect, it } from "vitest";
import { Brain } from "../src/brain/store.js";
import { EventLog } from "../src/events.js";
import { ActionGate, GateError, type ActionAdapter } from "../src/gate.js";

const approval = { approver: "Helen Marsh", role: "speaker" as const };

function setup(start = new Date("2026-11-02T09:00:00Z")) {
  let now = start;
  const brain = new Brain(() => now);
  const log = new EventLog(() => now);
  return { brain, log, gate: new ActionGate(brain, log), advance: (ms: number) => (now = new Date(now.getTime() + ms)) };
}

/** A LinkedIn stand-in that records every real post and can crash after posting. */
function flakyLinkedIn(crashAfterPost: () => boolean, withLookup = true): ActionAdapter & { posts: string[] } {
  const posts: string[] = [];
  const byKey = new Map<string, string>();
  return {
    action: "publish",
    posts,
    async execute({ content, idempotency_key }) {
      const id = `urn:li:share:${posts.length + 1}`;
      posts.push(content);
      byKey.set(idempotency_key, id);
      if (crashAfterPost()) throw new Error("worker killed after the API call, before recording");
      return id;
    },
    findExisting: withLookup ? async (key) => byKey.get(key) ?? null : undefined,
  };
}

describe("Action Gate", () => {
  it("publishes once with a valid token", async () => {
    const { gate } = setup();
    const li = flakyLinkedIn(() => false);
    const t = gate.issue("item-1", "post text", approval);
    const r = await gate.execute(li, { item_id: "item-1", content: "post text", token_id: t.id, idempotency_key: "publish:item-1" });
    expect(r).toBe("urn:li:share:1");
    expect(await gate.execute(li, { item_id: "item-1", content: "post text", token_id: t.id, idempotency_key: "publish:item-1" })).toBe(r);
    expect(li.posts).toHaveLength(1);
  });

  it("refuses content that changed after approval", async () => {
    const { gate } = setup();
    const t = gate.issue("item-1", "approved text", approval);
    await expect(gate.execute(flakyLinkedIn(() => false), { item_id: "item-1", content: "edited text", token_id: t.id, idempotency_key: "k" })).rejects.toThrow(/content changed/);
  });

  it("refuses an expired token (72 h)", async () => {
    const { gate, advance } = setup();
    const t = gate.issue("item-1", "x", approval);
    advance(72 * 3600 * 1000 + 1);
    expect(() => gate.validate(t.id, "item-1", "x")).toThrow(/expired/);
  });

  it("an edit voids the token, and a token can't be reused for a second action", async () => {
    const { gate } = setup();
    const t = gate.issue("item-1", "x", approval);
    gate.voidFor("item-1");
    expect(() => gate.validate(t.id, "item-1", "x")).toThrow(/voided/);
    const t2 = gate.issue("item-1", "x", approval);
    await gate.execute(flakyLinkedIn(() => false), { item_id: "item-1", content: "x", token_id: t2.id, idempotency_key: "a" });
    await expect(gate.execute(flakyLinkedIn(() => false), { item_id: "item-1", content: "x", token_id: t2.id, idempotency_key: "b" })).rejects.toThrow(GateError);
  });

  it("chaos: 20 crashes between the API call and the record produce zero duplicates", async () => {
    const { gate } = setup();
    for (let i = 0; i < 20; i++) {
      let crashed = false;
      const li = flakyLinkedIn(() => (crashed ? false : (crashed = true)));
      const item = `item-${i}`;
      const t = gate.issue(item, `post ${i}`, approval);
      const args = { item_id: item, content: `post ${i}`, token_id: t.id, idempotency_key: `publish:${item}` };
      await expect(gate.execute(li, args)).rejects.toThrow(/worker killed/);
      await gate.execute(li, args); // the restarted worker retries
      await gate.execute(li, args); // and a duplicate trigger arrives
      expect(li.posts).toHaveLength(1);
    }
  });

  it("without a lookup it escalates instead of risking a duplicate", async () => {
    const { gate } = setup();
    let crashed = false;
    const li = flakyLinkedIn(() => (crashed ? false : (crashed = true)), false);
    const t = gate.issue("item-1", "x", approval);
    const args = { item_id: "item-1", content: "x", token_id: t.id, idempotency_key: "publish:item-1" };
    await expect(gate.execute(li, args)).rejects.toThrow(/worker killed/);
    await expect(gate.execute(li, args)).rejects.toThrow(/cannot reconcile/);
    expect(li.posts).toHaveLength(1);
  });
});
