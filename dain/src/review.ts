// B3 · Human-in-the-loop review: the service behind the review screen. Two stages for
// content (specialist, then speaker), one for replies and packs. The edit timer counts
// active time only, an edit voids any token, and the final approval issues the token the
// Action Gate needs. Not an agent: no model is called here.
import type { Approval, Brain, HumanRole } from "./brain/store.js";
import { activeTime, type EventLog } from "./events.js";
import type { ActionGate, ApprovalToken } from "./gate.js";
import type { Entity, StateMachines } from "./state.js";

export const REASON_CODES = ["off_voice", "unconfirmed_claim", "not_booker_relevant", "factual_error", "tone", "duplicate", "other"] as const;
export type ReasonCode = (typeof REASON_CODES)[number];

export const SLA_HOURS: Record<HumanRole, number> = { specialist: 24, speaker: 72, product_lead: 24 };

export interface ReviewItem {
  id: string;
  entity: Entity;
  speaker_id: string;
  content: string;
  original: string;
  context: Record<string, unknown>; // claims used, B2 reasons, evidence links
  blocked: { kind: string; match: string }[]; // P1 guard hits; cleared only by a human edit
  label?: "provisional" | "calibrated";
}

export type ReviewChannel = "screen" | "email" | "form";

interface Session {
  role: HumanRole;
  channel: ReviewChannel;
  activity: number[];
  copied_out: boolean;
}

/** Which state an approval moves the item to, and whether it is the final one (token). */
const APPROVE: Record<string, { to: string; final: boolean }> = {
  "ContentItem:SPECIALIST_REVIEW": { to: "SPEAKER_REVIEW", final: false },
  "ContentItem:SPEAKER_REVIEW": { to: "APPROVED", final: true },
  "Enquiry:REPLY_DRAFTED": { to: "APPROVED", final: true },
  "AssetPack:RENDERED": { to: "APPROVED", final: true },
};

export class ReviewError extends Error {}

export class ReviewService {
  private sessions = new Map<string, Session>();

  constructor(
    private brain: Brain,
    private log: EventLog,
    private gate: ActionGate,
    private sm: StateMachines,
  ) {}

  private items(): Map<string, ReviewItem> {
    if (!this.brain.kv.has("review.items")) this.brain.kv.set("review.items", new Map());
    return this.brain.kv.get("review.items") as Map<string, ReviewItem>;
  }

  enqueue(item: Omit<ReviewItem, "original" | "blocked"> & { blocked?: ReviewItem["blocked"] }): ReviewItem {
    const full: ReviewItem = { ...item, original: item.content, blocked: item.blocked ?? [] };
    this.items().set(item.id, full);
    return full;
  }

  item(id: string): ReviewItem {
    const i = this.items().get(id);
    if (!i) throw new ReviewError(`no review item ${id}`);
    return i;
  }

  /** The queue a reviewer sees, oldest first, with how long each has waited. */
  queue(role: HumanRole): (ReviewItem & { state: string; waiting_h: number; sla_breached: boolean })[] {
    const wantState = (e: Entity, s: string) =>
      role === "specialist" ? (e === "ContentItem" ? s === "SPECIALIST_REVIEW" || s === "ESCALATED" : s === "REPLY_DRAFTED" || s === "RENDERED") : e === "ContentItem" && s === "SPEAKER_REVIEW";
    const now = this.brain.clock().getTime();
    return [...this.items().values()]
      .map((i) => {
        const st = this.sm.get(i.entity, i.id);
        const waiting_h = (now - new Date(st.entered_at).getTime()) / 3600000;
        return { ...i, state: st.state, waiting_h, sla_breached: waiting_h > SLA_HOURS[role] };
      })
      .filter((i) => wantState(i.entity, i.state))
      .sort((a, b) => b.waiting_h - a.waiting_h);
  }

  open(id: string, role: HumanRole, atMs: number, channel: ReviewChannel = "screen"): void {
    this.item(id);
    this.sessions.set(id, { role, channel, activity: [atMs], copied_out: false });
    this.log.emit({ type: "review.opened", item_id: id, reviewer_role: role });
  }

  /** The screen reports every keystroke, scroll and focus as activity. */
  activity(id: string, atMs: number): void {
    this.session(id).activity.push(atMs);
  }

  copiedOut(id: string, atMs: number): void {
    const s = this.session(id);
    s.copied_out = true;
    s.activity.push(atMs);
  }

  edit(id: string, content: string, atMs: number): void {
    const item = this.item(id);
    this.session(id).activity.push(atMs);
    item.content = content;
    item.blocked = []; // a human has looked at and changed the text
    this.gate.voidFor(id);
  }

  approve(id: string, approval: Approval, atMs: number): ApprovalToken | null {
    const item = this.item(id);
    const st = this.sm.get(item.entity, item.id);
    const route = APPROVE[`${item.entity}:${st.state}`];
    if (!route) throw new ReviewError(`${item.entity} ${id} in ${st.state} is not awaiting approval`);
    if (item.blocked.length) throw new ReviewError(`blocked until edited: ${item.blocked.map((b) => `${b.kind} "${b.match}"`).join(", ")}`);
    if (item.entity === "ContentItem" && st.state === "SPEAKER_REVIEW" && approval.role !== "speaker")
      throw new ReviewError("only the speaker can give final approval to publish in their name");
    this.close(id, approval.role, atMs, "approved");
    this.sm.transition(item.entity, item.id, route.to, approval);
    return route.final ? this.gate.issue(id, item.content, approval) : null;
  }

  requestChange(id: string, role: HumanRole, reason: ReasonCode, atMs: number): void {
    const item = this.item(id);
    const st = this.sm.get(item.entity, item.id);
    this.close(id, role, atMs, `change:${reason}`);
    if (item.entity === "ContentItem") this.sm.transition("ContentItem", id, st.state === "SPEAKER_REVIEW" ? "SPECIALIST_REVIEW" : "REVISE");
  }

  reject(id: string, role: HumanRole, reason: ReasonCode, atMs: number): void {
    const item = this.item(id);
    this.close(id, role, atMs, `reject:${reason}`);
    if (item.entity === "ContentItem") this.sm.transition("ContentItem", id, "REJECTED");
    if (item.entity === "Enquiry") this.sm.transition("Enquiry", id, "ESCALATED");
  }

  private session(id: string): Session {
    const s = this.sessions.get(id);
    if (!s) throw new ReviewError(`review of ${id} was not opened`);
    return s;
  }

  private close(id: string, role: HumanRole, atMs: number, outcome: string): void {
    const s = this.sessions.get(id) ?? { role, channel: "screen" as const, activity: [atMs], copied_out: false };
    s.activity.push(atMs);
    const { active_ms, idle_excluded_ms } = activeTime(s.activity);
    const item = this.item(id);
    this.log.emit({ type: "review.closed", item_id: id, speaker_id: item.speaker_id, channel: s.channel, reviewer_role: role, active_ms, idle_excluded_ms, diff_chars: diffChars(item.original, item.content), copied_out: s.copied_out, outcome });
    this.sessions.delete(id);
  }
}

/** Characters changed between draft and final: the voice-learning signal. */
export function diffChars(a: string, b: string): number {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  let j = 0;
  while (j < a.length - i && j < b.length - i && a[a.length - 1 - j] === b[b.length - 1 - j]) j++;
  return Math.max(a.length, b.length) - i - j;
}
