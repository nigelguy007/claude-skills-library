// P1 · Lead Capture & Pipeline. One extraction node and one reply node, wrapped in code
// that nulls anything the enquiry didn't say, refuses to reply to a snippet, and blocks
// any reply that quotes a fee, names a date or makes a commitment.
import { Extraction, ReplyDraft, type Blueprint, type RawEnquiry } from "../contracts.js";
import { callNode, type NodeContext } from "../llm.js";
import { loadPrompt } from "../prompts.js";

const MONTHS = "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?";

export const GUARD_RULES: { kind: "fee" | "date" | "commitment"; re: RegExp }[] = [
  { kind: "fee", re: /[£$€]\s?\d/ },
  { kind: "fee", re: /\b\d[\d,.]*\s?k\b/i },
  { kind: "fee", re: /\b(gbp|usd|eur|pounds|dollars|euros)\b/i },
  { kind: "fee", re: /\b(my|our) (fee|rate)s?\b|\bfees? (is|are|start|from)\b/i },
  { kind: "date", re: new RegExp(`\\b\\d{1,2}(st|nd|rd|th)?\\s+(of\\s+)?(${MONTHS})\\b`, "i") },
  { kind: "date", re: new RegExp(`\\b(${MONTHS})\\s+\\d{1,2}(st|nd|rd|th)?\\b`, "i") },
  { kind: "date", re: /\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/.]\d{1,2}([/.]\d{2,4})?\b/ },
  { kind: "date", re: /\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i },
  { kind: "commitment", re: /\bconfirm(ed|ing)?\b/i },
  { kind: "commitment", re: /\b(i'?m|i am|we'?re|we are) (available|free)\b/i },
  { kind: "commitment", re: /\b(booked|pencil(?:l?ed)?|hold (?:the|that) (?:date|day)|we accept|i accept|agreed|see you (?:on|there))\b/i },
];

/** Code check on every reply draft. Any hit blocks the draft until a human edits it. */
export function guardReply(text: string): { kind: string; match: string }[] {
  const hits: { kind: string; match: string }[] = [];
  for (const r of GUARD_RULES) {
    const m = text.match(r.re);
    if (m) hits.push({ kind: r.kind, match: m[0] });
  }
  return hits;
}

const ATTRIBUTION = /how (did you|you) (come across|hear about|find|came across)/i;
export const ATTRIBUTION_LINE = "Could I ask how you came across me? It helps me understand where bookers find my work.";

const present = (raw: string, v: string | null) => (v && raw.toLowerCase().includes(v.toLowerCase()) ? v : null);
const hasDateToken = (raw: string) => GUARD_RULES.filter((r) => r.kind === "date").some((r) => r.re.test(raw));

/** RULE: fields not in raw_text are null, never guessed. */
export function nullUnstated(x: Extraction, raw: string): Extraction {
  const sizeStated = x.event.audience_size !== null && raw.replace(/,/g, "").includes(String(x.event.audience_size));
  return {
    ...x,
    organiser: { name: present(raw, x.organiser.name), org: present(raw, x.organiser.org), role: present(raw, x.organiser.role), email: present(raw, x.organiser.email) },
    event: {
      ...x.event,
      name: present(raw, x.event.name),
      location: present(raw, x.event.location),
      date: hasDateToken(raw) ? x.event.date : null,
      audience_size: sizeStated ? x.event.audience_size : null,
    },
  };
}

/** R10 definition: organiser and organisation named, a date or window, and a paid format. */
export function isQualified(x: Extraction, paidFormatKnown: boolean): boolean {
  return Boolean(x.organiser.name && x.organiser.org && (x.event.date || x.deadline) && paidFormatKnown);
}

export interface CaptureResult {
  stage: "NEW" | "REPLY_DRAFTED";
  extraction: Extraction | null;
  reply_draft: string | null;
  blocked: { kind: string; match: string }[];
  warnings: string[];
  next_action: { what: string; due_hours: number };
}

export async function captureEnquiry(
  ctx: NodeContext,
  raw: RawEnquiry,
  speaker: { name: string; blueprint: Blueprint; consent_line?: string },
): Promise<CaptureResult> {
  if (raw.completeness === "snippet")
    return {
      stage: "NEW",
      extraction: null,
      reply_draft: null,
      blocked: [],
      warnings: ["snippet only"],
      next_action: { what: `Ask ${speaker.name} to paste the full LinkedIn thread`, due_hours: 4 },
    };

  const angles = speaker.blueprint.angles.map(({ id, title, audience, problem }) => ({ id, title, audience, problem }));
  const extracted = await callNode(
    ctx,
    { node: "P1", system: loadPrompt("pipeline/p1-capture/extract"), user: JSON.stringify({ raw_text: raw.raw_text, channel: raw.channel, received_at: raw.received_at, angles }) },
    Extraction,
  );
  const extraction = nullUnstated(extracted, raw.raw_text);

  const { reply_draft } = await callNode(
    ctx,
    {
      node: "P1",
      system: loadPrompt("pipeline/p1-capture/reply"),
      user: JSON.stringify({ speaker_name: speaker.name, voice: speaker.blueprint.voice, raw_text: raw.raw_text, extraction }),
    },
    ReplyDraft,
  );

  const warnings: string[] = [];
  let reply = reply_draft.trim();
  if (!ATTRIBUTION.test(reply)) reply += `\n\n${ATTRIBUTION_LINE}`;
  if (speaker.consent_line) reply += `\n\n${speaker.consent_line}`;
  else warnings.push("referral consent wording not yet approved in the Canon; acknowledgement sent without it");

  const blocked = guardReply(reply);
  return {
    stage: "REPLY_DRAFTED",
    extraction,
    reply_draft: reply,
    blocked,
    warnings,
    next_action: { what: blocked.length ? "Specialist edits blocked reply" : "Specialist approves reply", due_hours: 4 },
  };
}
