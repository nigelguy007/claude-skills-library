// The A2 ↔ B2 loop: generate → check (fresh context) → fix the lowest criterion → stop
// at a pass or after 3 passes, then escalate with every version and score.
import type { Blueprint, Draft, ScoreResult, Slot } from "../contracts.js";
import type { EventLog } from "../events.js";
import type { NodeContext } from "../llm.js";
import { MAX_REVISE_PASSES } from "../state.js";
import { claimFlags, draftPost, isBlocked } from "./a2.js";
import { scoreDraft, type Rubric } from "./b2.js";

export interface LoopPass {
  pass_no: number;
  draft: Draft;
  score?: ScoreResult;
  blocked_reason?: string;
}

export interface LoopResult {
  item_id: string;
  status: "pass" | "escalated";
  final: Draft;
  passes: LoopPass[];
}

export interface LoopInput {
  item_id: string;
  speaker_id: string;
  blueprint: Blueprint;
  slot: Slot;
  rubric: Rubric;
  recent_posts: string[];
  voice_samples: string[];
}

export async function runContentLoop(ctx: NodeContext, log: EventLog, input: LoopInput): Promise<LoopResult> {
  const passes: LoopPass[] = [];
  const angle = input.blueprint.angles.find((a) => a.id === input.slot.angle_id)!;
  let revision: { previous: string; request: string; scores?: Record<string, number> } | undefined;

  for (let pass = 1; pass <= MAX_REVISE_PASSES; pass++) {
    const draft = await draftPost(ctx, { ...input, revision }, `${input.item_id}.v${pass}`);
    log.emit({ type: "draft.created", draft_id: draft.draft_id, item_id: input.item_id, angle_id: draft.angle_id, pass_no: pass });

    if (isBlocked(draft)) {
      const reason = claimFlags(draft.claim_ids, input.blueprint).join("; ");
      passes.push({ pass_no: pass, draft, blocked_reason: reason });
      revision = { previous: draft.text, request: `Remove or replace these: ${reason}. Use only the confirmed claims you were given.` };
      continue;
    }

    const claims = input.blueprint.claims.filter((c) => draft.claim_ids.includes(c.id)).map(({ id, text, status }) => ({ id, text, status }));
    const score = await scoreDraft(ctx, { draft_text: draft.text, angle, claims, rubric: input.rubric, voice_samples: input.voice_samples });
    log.emit({ type: "draft.scored", draft_id: draft.draft_id, item_id: input.item_id, rubric_version: score.rubric_version, label: score.label, scores: score.scores, verdict: score.verdict, pass_no: pass });
    passes.push({ pass_no: pass, draft, score });

    if (score.verdict === "pass") return { item_id: input.item_id, status: "pass", final: draft, passes };
    revision = { previous: draft.text, request: score.revision_request, scores: score.scores };
  }

  log.emit({ type: "item.escalated", item_id: input.item_id, reason: `no pass after ${MAX_REVISE_PASSES} passes` });
  return { item_id: input.item_id, status: "escalated", final: passes[passes.length - 1]!.draft, passes };
}
