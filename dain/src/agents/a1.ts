// A1 · Voice-Interview & Blueprint. The live interview runs on the voice transport
// (Vapi or OpenAI Realtime) with interview.prompt.md; this module turns the timestamped
// transcript into a Blueprint, checks it against the transcript in a fresh context, and
// applies the speaker's claim-by-claim confirmation.
import { Blueprint, TranscriptCheck, type Claim, type TranscriptSegment } from "../contracts.js";
import { callNode, type NodeContext } from "../llm.js";
import { loadPrompt } from "../prompts.js";

export const MAX_FOLLOW_UP_ROUNDS = 2;
export const MIN_CLAIMS = 6;

export interface InterviewInput {
  transcript: TranscriptSegment[];
  existing_assets: string[]; // text of old bios / talk pages
  writing_samples: string[];
  fee_band: string;
  formats: string[];
  blueprint_version: string;
}

export async function writeBlueprint(ctx: NodeContext, input: InterviewInput): Promise<Blueprint> {
  const stamps = new Set(input.transcript.filter((s) => s.speaker === "speaker").map((s) => s.ts));
  const bp = await callNode(
    ctx,
    { node: "A1", system: loadPrompt("content/a1-voice-interview/blueprint-writer"), user: JSON.stringify(input), maxTokens: 6000 },
    Blueprint,
    (out) => {
      const bad = out.claims.filter((c) => !stamps.has(c.source_quote_ts)).map((c) => `${c.id}@${c.source_quote_ts}`);
      return bad.length ? `claims cite timestamps where the speaker did not speak: ${bad.join(", ")}` : null;
    },
  );
  // The writer cannot confirm anything. Only the speaker's tick in the portal does.
  return { ...bp, claims: bp.claims.map((c) => ({ ...c, status: c.status === "rejected" ? "rejected" : "needs_evidence" })) };
}

/** Independent checker: sees the transcript and the Blueprint text only, never the writer's reasoning. */
export async function checkAgainstTranscript(ctx: NodeContext, transcript: TranscriptSegment[], bp: Blueprint): Promise<TranscriptCheck> {
  const statements = {
    positioning: bp.positioning,
    angles: bp.angles.map(({ id, title, audience, problem, promise }) => ({ id, title, audience, problem, promise })),
    claims: bp.claims.map(({ id, text }) => ({ id, text })),
    bio: bp.bio,
  };
  return callNode(
    ctx,
    { node: "A1", system: loadPrompt("content/a1-voice-interview/checker"), user: JSON.stringify({ transcript, statements }) },
    TranscriptCheck,
  );
}

/** Coverage checklist: the loop's check that can fail. Returns the gaps. */
export function coverageGaps(bp: Blueprint): string[] {
  const gaps: string[] = [];
  if (!bp.positioning.trim()) gaps.push("positioning is empty");
  if (bp.angles.length !== 3) gaps.push("needs exactly 3 angles");
  const live = bp.claims.filter((c) => c.status !== "rejected");
  if (live.length < MIN_CLAIMS) gaps.push(`only ${live.length} claims; need ≥ ${MIN_CLAIMS}`);
  if (!live.some((c) => c.type === "testimonial" || c.type === "rebooking" || c.type === "client"))
    gaps.push("no reputation proof (testimonial, rebooking or client)");
  if (bp.voice.traits.length < 3) gaps.push("voice traits missing");
  return gaps;
}

/** Follow-up questions for the next round, built from the gaps and the checker's flags. */
export function followUpQuestions(gaps: string[], check: TranscriptCheck, bp: Blueprint): string[] {
  const qs = [...bp.open_questions];
  for (const g of gaps) {
    if (g.startsWith("only")) qs.push("Can you give me two more concrete results, with a number or a client name for each?");
    if (g.startsWith("no reputation")) qs.push("Which clients have rebooked you, and who would give you a reference?");
    if (g.startsWith("positioning")) qs.push("If a booker had one sentence to describe you to their CEO, what should it be?");
  }
  for (const u of check.unsupported) qs.push(`You're down as saying "${u.statement}". Did you say that, and can you put it in your own words?`);
  return [...new Set(qs)];
}

export type ClaimDecision = Claim["status"];

/** Apply the speaker's portal ticks. Unticked claims stay needs_evidence. */
export function applyConfirmation(bp: Blueprint, decisions: Record<string, ClaimDecision>): Blueprint {
  const claims = bp.claims.map((c) => ({ ...c, status: decisions[c.id] ?? c.status }));
  return Blueprint.parse({ ...bp, claims });
}

export function confirmedShare(bp: Blueprint): number {
  const live = bp.claims.filter((c) => c.status !== "rejected");
  return live.length ? live.filter((c) => c.status === "speaker_confirmed").length / live.length : 0;
}
