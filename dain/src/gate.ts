// Action & Approval Gate. Every external write (publish, send, share) needs a
// single-use approval token bound to the exact content hash, plus an idempotency key,
// so an approved post cannot be published twice or published after edits.
import { createHash, randomUUID } from "node:crypto";
import type { Approval, Brain } from "./brain/store.js";
import type { EventLog } from "./events.js";

export const TOKEN_TTL_MS = 72 * 60 * 60 * 1000;

export const hashContent = (content: string) => createHash("sha256").update(content, "utf8").digest("hex");

export interface ApprovalToken {
  id: string;
  item_id: string;
  content_hash: string;
  approver: string;
  role: Approval["role"];
  expires_at: string;
  used: boolean;
  voided: boolean;
}

/** An external system. `findExisting` lets the gate reconcile after a crash mid-call. */
export interface ActionAdapter {
  action: "publish" | "send" | "share";
  execute(payload: { item_id: string; content: string; idempotency_key: string }): Promise<string>;
  findExisting?(idempotency_key: string): Promise<string | null>;
}

interface ExecutionRecord {
  idempotency_key: string;
  token_id: string;
  status: "pending" | "done";
  result?: string;
}

export class GateError extends Error {}

export class ActionGate {
  constructor(
    private brain: Brain,
    private log: EventLog,
  ) {}

  private tokens(): Map<string, ApprovalToken> {
    if (!this.brain.kv.has("gate.tokens")) this.brain.kv.set("gate.tokens", new Map());
    return this.brain.kv.get("gate.tokens") as Map<string, ApprovalToken>;
  }

  private executions(): Map<string, ExecutionRecord> {
    if (!this.brain.kv.has("gate.exec")) this.brain.kv.set("gate.exec", new Map());
    return this.brain.kv.get("gate.exec") as Map<string, ExecutionRecord>;
  }

  issue(itemId: string, content: string, approval: Approval): ApprovalToken {
    if (!approval.approver) throw new GateError("approval needs a named human");
    // A new approval for the same item supersedes any earlier one.
    for (const t of this.tokens().values()) if (t.item_id === itemId && !t.used) t.voided = true;
    const token: ApprovalToken = {
      id: randomUUID(),
      item_id: itemId,
      content_hash: hashContent(content),
      approver: approval.approver,
      role: approval.role,
      expires_at: new Date(this.brain.clock().getTime() + TOKEN_TTL_MS).toISOString(),
      used: false,
      voided: false,
    };
    this.tokens().set(token.id, token);
    this.log.emit({ type: "approval.token_issued", item_id: itemId, content_hash: token.content_hash, approver: approval.approver, expires_at: token.expires_at });
    return token;
  }

  /** Any edit after approval voids the token. */
  voidFor(itemId: string): void {
    for (const t of this.tokens().values()) if (t.item_id === itemId && !t.used) t.voided = true;
  }

  validate(tokenId: string, itemId: string, content: string): ApprovalToken {
    const t = this.tokens().get(tokenId);
    if (!t) throw new GateError("unknown approval token");
    if (t.item_id !== itemId) throw new GateError("token belongs to a different item");
    if (t.voided) throw new GateError("token was voided by an edit or a newer approval");
    if (new Date(t.expires_at).getTime() <= this.brain.clock().getTime()) throw new GateError("token expired (72 h)");
    if (t.content_hash !== hashContent(content)) throw new GateError("content changed after approval");
    return t;
  }

  /**
   * Execute an external action at most once per idempotency key.
   * Order: record intent → call adapter → record result. If the process dies between
   * the call and the record, the retry finds a pending intent and asks the adapter
   * whether the action already happened before calling it again.
   */
  async execute(adapter: ActionAdapter, args: { item_id: string; content: string; token_id: string; idempotency_key: string }): Promise<string> {
    const execs = this.executions();
    const prior = execs.get(args.idempotency_key);
    if (prior?.status === "done") return prior.result!;

    if (prior?.status === "pending") {
      const found = adapter.findExisting ? await adapter.findExisting(args.idempotency_key) : null;
      if (found) return this.finish(prior, args, adapter.action, found);
      if (!adapter.findExisting)
        throw new GateError(`cannot reconcile pending ${adapter.action} for ${args.item_id}: adapter has no lookup; escalate to a human`);
    } else {
      const token = this.validate(args.token_id, args.item_id, args.content);
      if (token.used) throw new GateError("token already used");
      token.used = true;
      execs.set(args.idempotency_key, { idempotency_key: args.idempotency_key, token_id: token.id, status: "pending" });
    }

    const result = await adapter.execute({ item_id: args.item_id, content: args.content, idempotency_key: args.idempotency_key });
    return this.finish(execs.get(args.idempotency_key)!, args, adapter.action, result);
  }

  private finish(rec: ExecutionRecord, args: { item_id: string; token_id: string; idempotency_key: string }, action: string, result: string): string {
    rec.status = "done";
    rec.result = result;
    this.log.emit({ type: "action.executed", item_id: args.item_id, action, token_id: args.token_id, idempotency_key: args.idempotency_key, result: "ok" });
    return result;
  }
}
