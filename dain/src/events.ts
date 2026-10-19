// R5 · Instrument from the first call. Event names and fields follow the C0 sheet.
// The pilot dashboard metrics are computed here, from events only, so there is one
// definition of each number.

export type DainEvent =
  | { type: "speaker.onboarded"; speaker_id: string; tier: string; baseline_enquiries_6m: number }
  | { type: "node.called"; node: string; speaker_id: string | null; canon_version: string; model: string; tokens: number; cost_gbp: number; ms: number; verdict: string }
  | { type: "draft.created"; draft_id: string; item_id: string; angle_id: string; pass_no: number }
  | { type: "draft.scored"; draft_id: string; item_id: string; rubric_version: string; label: string; scores: Record<string, number>; verdict: string; pass_no: number }
  | { type: "review.opened"; item_id: string; reviewer_role: string }
  | { type: "review.closed"; item_id: string; speaker_id: string; channel: "screen" | "email" | "form"; reviewer_role: string; active_ms: number; idle_excluded_ms: number; diff_chars: number; copied_out: boolean; outcome: string }
  | { type: "approval.token_issued"; item_id: string; content_hash: string; approver: string; expires_at: string }
  | { type: "action.executed"; item_id: string; action: string; token_id: string; idempotency_key: string; result: string }
  | { type: "enquiry.created"; enquiry_id: string; speaker_id: string; channel: string; completeness: string; latency_ms: number }
  | { type: "enquiry.stage_changed"; enquiry_id: string; from: string; to: string; qualified: boolean; source_answer: string | null }
  | { type: "sweep.answered"; speaker_id: string; week: string; missed_count: number }
  | { type: "item.state_changed"; entity: string; item_id: string; from: string; to: string }
  | { type: "item.escalated"; item_id: string; reason: string };

export type Logged = DainEvent & { at: string };

export class EventLog {
  readonly events: Logged[] = [];
  constructor(private now: () => Date = () => new Date()) {}

  emit(e: DainEvent): void {
    this.events.push({ ...e, at: this.now().toISOString() });
  }

  of<T extends DainEvent["type"]>(type: T): Extract<Logged, { type: T }>[] {
    return this.events.filter((e) => e.type === type) as Extract<Logged, { type: T }>[];
  }
}

export const IDLE_GAP_MS = 2 * 60 * 1000;

/**
 * Edit time = active time on the review screen, open to approve, excluding idle gaps
 * over 2 minutes. `activity` holds the timestamps (ms) of every input/scroll/focus
 * event the review screen reported, including open and close.
 */
export function activeTime(activity: number[]): { active_ms: number; idle_excluded_ms: number } {
  const ts = [...activity].sort((a, b) => a - b);
  let active = 0;
  let idle = 0;
  for (let i = 1; i < ts.length; i++) {
    const gap = ts[i]! - ts[i - 1]!;
    if (gap > IDLE_GAP_MS) idle += gap;
    else active += gap;
  }
  return { active_ms: active, idle_excluded_ms: idle };
}

export function percentile(xs: number[], p: number): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const idx = Math.min(s.length - 1, Math.max(0, Math.ceil((p / 100) * s.length) - 1));
  return s[idx]!;
}

/** The pilot dashboard (R5). Every value is derived from the event log. */
export function dashboard(log: EventLog) {
  const speakerReviews = log.of("review.closed").filter((e) => e.reviewer_role === "speaker");
  // Email and form replies have no screen timer: count them, but never as a 0-minute edit.
  const timed = speakerReviews.filter((e) => e.channel === "screen");
  const editMins = timed.map((e) => e.active_ms / 60000);

  const items = new Set(log.of("draft.created").map((e) => e.item_id));
  const published = log.of("action.executed").filter((e) => e.action === "publish" && e.result === "ok");
  const approvedItems = new Set(published.map((e) => e.item_id));

  const firstScores = log.of("draft.scored").filter((e) => e.pass_no === 1);
  const firstPass = firstScores.filter((e) => e.verdict === "pass").length;

  const contentCost = log
    .of("node.called")
    .filter((e) => e.node === "A2" || e.node === "B2")
    .reduce((s, e) => s + e.cost_gbp, 0);

  const enquiries = log.of("enquiry.created");
  const missed = log.of("sweep.answered").reduce((s, e) => s + e.missed_count, 0);

  const specialistMs = log
    .of("review.closed")
    .filter((e) => e.reviewer_role === "specialist")
    .reduce((s, e) => s + e.active_ms, 0);

  return {
    edit_time_min_median: percentile(editMins, 50),
    edit_time_min_p90: percentile(editMins, 90),
    copied_out_share: timed.length ? timed.filter((e) => e.copied_out).length / timed.length : null,
    untimed_review_share: speakerReviews.length ? (speakerReviews.length - timed.length) / speakerReviews.length : null,
    keep_rate: items.size ? approvedItems.size / items.size : null,
    b2_first_pass_rate: firstScores.length ? firstPass / firstScores.length : null,
    cost_per_approved_post_gbp: approvedItems.size ? contentCost / approvedItems.size : null,
    capture_latency_ms_p90: percentile(enquiries.map((e) => e.latency_ms), 90),
    capture_coverage: enquiries.length + missed ? enquiries.length / (enquiries.length + missed) : null,
    specialist_minutes_total: specialistMs / 60000,
    escalations: log.of("item.escalated").length,
  };
}

/**
 * Pass criteria from the decks (BE8, launch blueprint): ≥ 70% of drafts approved and a
 * median edit under 15 minutes per post. The spec's 66% keep-rate is superseded by 70%.
 * The 4 h/speaker/month review ceiling is checked nightly by the groundskeeper.
 */
export const LAUNCH_GATES = { keep_rate_min: 0.7, edit_time_median_max_min: 15 } as const;

export function checkLaunchGates(d: ReturnType<typeof dashboard>): { pass: boolean; failures: string[] } {
  const failures: string[] = [];
  if (d.keep_rate === null || d.keep_rate < LAUNCH_GATES.keep_rate_min)
    failures.push(`approval rate ${d.keep_rate === null ? "not measured" : `${Math.round(d.keep_rate * 100)}%`} (need ≥ 70%)`);
  if (d.edit_time_min_median === null || d.edit_time_min_median >= LAUNCH_GATES.edit_time_median_max_min)
    failures.push(`median edit ${d.edit_time_min_median === null ? "not measured" : `${d.edit_time_min_median.toFixed(1)} min`} (need < 15 min per post)`);
  return { pass: failures.length === 0, failures };
}
