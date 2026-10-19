// A2 · Content & Drafting. Plans the week in code, drafts each slot from the Canon
// only, and blocks any draft that leans on a claim the speaker has not confirmed.
import { Draft, PostFormat, type Blueprint, type Slot } from "../contracts.js";
import { callNode, type NodeContext } from "../llm.js";
import { loadPrompt } from "../prompts.js";

export const FORMATS = PostFormat.options;
export const RECENT_WINDOW = 6;

export interface PastPost {
  angle_id: string;
  format: Slot["format"];
  text?: string;
}

const confirmedClaimsFor = (bp: Blueprint, angleId: string) => {
  const angle = bp.angles.find((a) => a.id === angleId);
  return bp.claims.filter((c) => c.status === "speaker_confirmed" && angle?.proof_claim_ids.includes(c.id));
};

/**
 * Weekly plan (code, not a model): three slots, least-recently-used angles first,
 * formats rotated, no (angle, format) pair from the last six posts, at least one proof
 * post when any angle has a confirmed claim to prove it with.
 */
export function planWeek(bp: Blueprint, recent: PastPost[], n = 3): Slot[] {
  const window = recent.slice(-RECENT_WINDOW);
  const lastUse = (id: string) => window.map((p) => p.angle_id).lastIndexOf(id);
  const angles = [...bp.angles].sort((a, b) => lastUse(a.id) - lastUse(b.id));
  const used = new Set(window.map((p) => `${p.angle_id}:${p.format}`));
  const lastFormat = window[window.length - 1]?.format;
  let f = lastFormat ? FORMATS.indexOf(lastFormat) + 1 : 0;

  const slots: Slot[] = [];
  for (let i = 0; i < n; i++) {
    const angle = angles[i % angles.length]!;
    let format: Slot["format"] = FORMATS[f % FORMATS.length]!;
    for (let tries = 0; tries < FORMATS.length && used.has(`${angle.id}:${format}`); tries++) format = FORMATS[++f % FORMATS.length]!;
    f++;
    slots.push({ angle_id: angle.id, format });
  }

  if (!slots.some((s) => s.format === "proof")) {
    const provable = slots.find((s) => confirmedClaimsFor(bp, s.angle_id).length > 0);
    if (provable) provable.format = "proof";
  }
  return slots;
}

export interface DraftInput {
  speaker_id: string;
  blueprint: Blueprint;
  slot: Slot;
  recent_posts: string[];
  voice_samples: string[];
  revision?: { previous: string; request: string; scores?: Record<string, number> };
  radar_signal?: { id: string; theme: string; quote: string };
}

export async function draftPost(ctx: NodeContext, input: DraftInput, draftId: string): Promise<Draft> {
  const bp = input.blueprint;
  const angle = bp.angles.find((a) => a.id === input.slot.angle_id);
  if (!angle) throw new Error(`angle ${input.slot.angle_id} is not in the approved Blueprint`);
  const payload = {
    slot: input.slot,
    angle,
    // Only confirmed claims are shown to the drafter at all.
    confirmed_claims: bp.claims.filter((c) => c.status === "speaker_confirmed").map(({ id, text, type }) => ({ id, text, type })),
    boundaries: bp.boundaries,
    voice: bp.voice,
    voice_samples: input.voice_samples.slice(-5),
    recent_posts: input.recent_posts.slice(-RECENT_WINDOW),
    radar_signal: input.radar_signal,
    revision: input.revision,
  };
  const out = await callNode(
    ctx,
    { node: "A2", system: loadPrompt("content/a2-drafting/draft"), user: JSON.stringify(payload) },
    Draft.omit({ draft_id: true, self_flags: true }).extend({ self_flags: Draft.shape.self_flags.default([]) }),
  );
  return {
    ...out,
    draft_id: draftId,
    angle_id: input.slot.angle_id,
    self_flags: [...out.self_flags, ...claimFlags(out.claim_ids, bp), ...boundaryFlags(out.text, bp)],
  };
}

/** RULE: a draft may not touch a topic the speaker ruled out or name anyone they asked not to be named. */
export function boundaryFlags(text: string, bp: Blueprint): string[] {
  const t = text.toLowerCase();
  return [
    ...bp.boundaries.avoid_topics.filter((x) => x.trim() && t.includes(x.toLowerCase())).map((x) => `breaks boundary: avoid topic "${x}"`),
    ...bp.boundaries.do_not_name.filter((x) => x.trim() && t.includes(x.toLowerCase())).map((x) => `breaks boundary: names "${x}"`),
  ];
}

/** RULE: every claim used must exist in the Canon with status speaker_confirmed. */
export function claimFlags(claimIds: string[], bp: Blueprint): string[] {
  const flags: string[] = [];
  for (const id of claimIds) {
    const c = bp.claims.find((x) => x.id === id);
    if (!c) flags.push(`uses claim ${id}, which is not in the Canon`);
    else if (c.status !== "speaker_confirmed") flags.push(`uses unconfirmed claim ${id}`);
  }
  return flags;
}

const BLOCKING = (f: string) => f.startsWith("uses ") || f.startsWith("breaks boundary");
export const isBlocked = (d: Draft) => d.self_flags.some(BLOCKING);
export const blockingFlags = (d: Draft) => d.self_flags.filter(BLOCKING);
