// C0 state machines. Routes are fixed in these tables; nothing reads text to decide
// where an item goes next. Edges marked `gated` need a named human approval.
import type { Approval, Brain } from "./brain/store.js";
import type { EventLog } from "./events.js";

type Edge = [from: string, to: string, gated?: "gated"];

const ANY_OPEN = "*";

const MACHINES = {
  Speaker: [
    ["ONBOARDING", "INTERVIEW_BOOKED"],
    ["INTERVIEW_BOOKED", "INTERVIEWED"],
    ["INTERVIEWED", "BLUEPRINT_DRAFT"],
    ["BLUEPRINT_DRAFT", "INTERVIEWED"], // follow-up round
    ["BLUEPRINT_DRAFT", "BLUEPRINT_APPROVED", "gated"],
    ["BLUEPRINT_APPROVED", "ACTIVE"],
    ["ACTIVE", "PAUSED"],
    ["PAUSED", "ACTIVE"],
    [ANY_OPEN, "ESCALATED"],
  ],
  ContentItem: [
    ["PLANNED", "DRAFTED"],
    ["DRAFTED", "SCORED"],
    ["SCORED", "REVISE"],
    ["REVISE", "DRAFTED"],
    ["SCORED", "SPECIALIST_REVIEW"],
    ["SPECIALIST_REVIEW", "SPEAKER_REVIEW", "gated"],
    ["SPECIALIST_REVIEW", "REVISE"],
    ["SPECIALIST_REVIEW", "REJECTED"],
    ["SPEAKER_REVIEW", "APPROVED", "gated"],
    ["SPEAKER_REVIEW", "SPECIALIST_REVIEW"], // speaker asks for a change
    ["SPEAKER_REVIEW", "REJECTED"],
    ["APPROVED", "SCHEDULED"],
    ["APPROVED", "PUBLISHED"],
    ["SCHEDULED", "PUBLISHED"],
    ["ESCALATED", "SPECIALIST_REVIEW"], // specialist takes the item over by hand
    ["ESCALATED", "REJECTED"],
    [ANY_OPEN, "ESCALATED"],
  ],
  Enquiry: [
    ["NEW", "EXTRACTED"],
    ["EXTRACTED", "QUALIFIED"],
    ["QUALIFIED", "REPLY_DRAFTED"],
    ["REPLY_DRAFTED", "APPROVED", "gated"],
    ["APPROVED", "SENT"],
    ["SENT", "NEGOTIATING"],
    ["NEGOTIATING", "WON"],
    ["NEGOTIATING", "LOST"],
    ["NEGOTIATING", "REFERRED"],
    ["SENT", "LOST"],
    [ANY_OPEN, "ESCALATED"],
  ],
  AssetPack: [
    ["RENDERED", "APPROVED", "gated"],
    ["APPROVED", "SENT"],
    ["RENDERED", "RENDERED"], // Canon changed again before approval
  ],
} satisfies Record<string, Edge[]>;

export type Entity = keyof typeof MACHINES;

const INITIAL: Record<Entity, string> = { Speaker: "ONBOARDING", ContentItem: "PLANNED", Enquiry: "NEW", AssetPack: "RENDERED" };
const TERMINAL = new Set(["PUBLISHED", "REJECTED", "WON", "LOST", "REFERRED"]);

export const MAX_REVISE_PASSES = 3;

export class TransitionError extends Error {}

export interface ItemState {
  entity: Entity;
  id: string;
  speaker_id: string;
  state: string;
  revise_count: number;
  entered_at: string;
  history: { from: string; to: string; at: string; by?: string }[];
}

export class StateMachines {
  constructor(
    private brain: Brain,
    private log: EventLog,
  ) {}

  private table(): Map<string, ItemState> {
    if (!this.brain.kv.has("state.items")) this.brain.kv.set("state.items", new Map());
    return this.brain.kv.get("state.items") as Map<string, ItemState>;
  }

  create(entity: Entity, id: string, speakerId: string): ItemState {
    const existing = this.table().get(`${entity}:${id}`);
    if (existing) return existing;
    const s: ItemState = { entity, id, speaker_id: speakerId, state: INITIAL[entity], revise_count: 0, entered_at: this.brain.clock().toISOString(), history: [] };
    this.table().set(`${entity}:${id}`, s);
    return s;
  }

  get(entity: Entity, id: string): ItemState {
    const s = this.table().get(`${entity}:${id}`);
    if (!s) throw new TransitionError(`no ${entity} ${id}`);
    return s;
  }

  all(): ItemState[] {
    return [...this.table().values()];
  }

  can(entity: Entity, from: string, to: string): Edge | undefined {
    return (MACHINES[entity] as Edge[]).find(
      ([f, t]) => t === to && (f === from || (f === ANY_OPEN && !TERMINAL.has(from) && from !== "ESCALATED")),
    );
  }

  transition(entity: Entity, id: string, to: string, approval?: Approval): ItemState {
    const s = this.get(entity, id);
    if (s.state === to && to !== "RENDERED") return s; // idempotent on replay
    const edge = this.can(entity, s.state, to);
    if (!edge) throw new TransitionError(`${entity} ${id}: ${s.state} → ${to} is not a route`);
    if (edge[2] === "gated" && !approval?.approver)
      throw new TransitionError(`${entity} ${id}: ${s.state} → ${to} needs a human approval`);
    if (to === "REVISE") {
      if (s.revise_count >= MAX_REVISE_PASSES) throw new TransitionError(`${id}: revise limit reached; escalate`);
      s.revise_count++;
    }
    const at = this.brain.clock().toISOString();
    s.history.push({ from: s.state, to, at, by: approval?.approver });
    this.log.emit({ type: "item.state_changed", entity, item_id: id, from: s.state, to });
    s.state = to;
    s.entered_at = at;
    return s;
  }
}

/** States where an item waits on a human; the groundskeeper sweeps these for stuck items. */
export const HUMAN_WAIT_STATES = new Set(["BLUEPRINT_DRAFT", "SPECIALIST_REVIEW", "SPEAKER_REVIEW", "REPLY_DRAFTED", "RENDERED", "ESCALATED"]);
