// Node contracts from the Dain Agent Specification (Rev 3). Every LLM output is
// parsed against one of these schemas; a mismatch is rejected and retried once.
import { z } from "zod";

const TIMESTAMP = /^\d{2}:\d{2}:\d{2}$/;
const words = (s: string) => s.trim().split(/\s+/).filter(Boolean).length;

// ---------- A1 · Voice-Interview & Blueprint ----------

export const ClaimType = z.enum(["credential", "metric", "story", "client", "testimonial", "rebooking"]);
export const ClaimStatus = z.enum(["speaker_confirmed", "needs_evidence", "rejected"]);

export const Claim = z.object({
  id: z.string().regex(/^C\d+$/),
  text: z.string().min(1),
  type: ClaimType,
  status: ClaimStatus,
  source_quote_ts: z.string().regex(TIMESTAMP, "every claim cites a transcript timestamp"),
});
export type Claim = z.infer<typeof Claim>;

export const Angle = z.object({
  id: z.string().regex(/^A\d+$/),
  title: z.string().min(1),
  audience: z.string().min(1),
  problem: z.string().min(1),
  promise: z.string().min(1),
  proof_claim_ids: z.array(z.string()).min(1, "every angle cites at least one claim"),
});
export type Angle = z.infer<typeof Angle>;

export const Voice = z.object({
  traits: z.array(z.string()).min(3).max(5),
  do: z.array(z.string()),
  dont: z.array(z.string()),
  sample_sentences: z.array(z.string()).length(5),
});

export const Blueprint = z
  .object({
    blueprint_version: z.string(),
    positioning: z.string().refine((s) => words(s) <= 40, "positioning is at most 40 words"),
    angles: z.array(Angle).length(3),
    claims: z.array(Claim),
    voice: Voice,
    bio: z.object({ short_50w: z.string(), medium_150w: z.string(), long_300w: z.string() }),
    // Operational boundaries the speaker confirms (deck BP6): no content may cross them.
    boundaries: z
      .object({
        avoid_topics: z.array(z.string()),
        do_not_name: z.array(z.string()),
        notes: z.array(z.string()),
      })
      .default({ avoid_topics: [], do_not_name: [], notes: [] }),
    open_questions: z.array(z.string()),
  })
  .superRefine((bp, ctx) => {
    const ids = new Set(bp.claims.map((c) => c.id));
    for (const a of bp.angles)
      for (const cid of a.proof_claim_ids)
        if (!ids.has(cid)) ctx.addIssue({ code: "custom", message: `angle ${a.id} cites unknown claim ${cid}` });
  });
export type Blueprint = z.infer<typeof Blueprint>;

export const TranscriptSegment = z.object({ ts: z.string().regex(TIMESTAMP), speaker: z.enum(["agent", "speaker"]), text: z.string() });
export type TranscriptSegment = z.infer<typeof TranscriptSegment>;

// Independent checker: re-reads the transcript only and lists Blueprint lines it cannot find there.
export const TranscriptCheck = z.object({
  unsupported: z.array(z.object({ field: z.string(), statement: z.string(), reason: z.string() })),
});
export type TranscriptCheck = z.infer<typeof TranscriptCheck>;

// ---------- A2 · Content & Drafting ----------

export const PostFormat = z.enum(["story", "proof", "contrarian", "lesson"]);
export type PostFormat = z.infer<typeof PostFormat>;

export const Slot = z.object({ angle_id: z.string(), format: PostFormat });
export type Slot = z.infer<typeof Slot>;

export const Draft = z.object({
  draft_id: z.string(),
  text: z.string().max(1300),
  hook_line: z.string(),
  angle_id: z.string(),
  claim_ids: z.array(z.string()),
  signal_id: z.string().optional(),
  self_flags: z.array(z.string()),
});
export type Draft = z.infer<typeof Draft>;

// ---------- B2 · Bookability Scoring ----------

export const CRITERIA = ["audience_fit", "outcome_clarity", "credibility", "distinctiveness", "timeliness", "voice_match"] as const;
export type Criterion = (typeof CRITERIA)[number];

const score = z.number().int().min(1).max(5);
export const Scores = z.object(Object.fromEntries(CRITERIA.map((c) => [c, score])) as Record<Criterion, typeof score>);
export type Scores = z.infer<typeof Scores>;

export const ScoreResult = z.object({
  scores: Scores,
  reasons: z.object(Object.fromEntries(CRITERIA.map((c) => [c, z.string()])) as Record<Criterion, z.ZodString>),
  verdict: z.enum(["pass", "revise"]),
  revision_request: z.string(),
  rubric_version: z.string(),
  label: z.enum(["provisional", "calibrated"]),
});
export type ScoreResult = z.infer<typeof ScoreResult>;

// ---------- P1 · Lead Capture & Pipeline ----------

export const Channel = z.enum(["email", "form", "paste", "share", "csv", "li_notification"]);
export const RawEnquiry = z.object({
  channel: Channel,
  raw_text: z.string().min(1),
  completeness: z.enum(["full", "snippet"]),
  received_at: z.string(),
});
export type RawEnquiry = z.infer<typeof RawEnquiry>;

const nstr = z.string().nullable();
export const Extraction = z.object({
  organiser: z.object({ name: nstr, org: nstr, role: nstr, email: nstr }),
  event: z.object({
    name: nstr,
    date: nstr,
    location: nstr,
    format: nstr,
    audience_size: z.number().int().nullable(),
    audience_type: nstr,
  }),
  budget_signal: z.enum(["none", "stated", "implied"]),
  deadline: nstr,
  angle_match: z.array(z.object({ angle_id: z.string(), reason: z.string() })),
  fit: z.enum(["strong", "possible", "weak"]),
  missing_questions: z.array(z.string()),
});
export type Extraction = z.infer<typeof Extraction>;

export const ReplyDraft = z.object({ reply_draft: z.string().min(1) });

// ---------- B1 · Relevance Radar ----------

export const RawSignal = z.object({ theme: z.string(), quote: z.string(), url: z.string().url(), event: z.string(), date: z.string() });
export type RawSignal = z.infer<typeof RawSignal>;
export const WorkerOut = z.object({ signals: z.array(RawSignal) });

export const SkepticOut = z.object({ supports: z.boolean(), reason: z.string() });

export const InsideOutConcept = z.object({
  concept_id: z.string(),
  title: z.string(),
  why_now: z.string(),
  why_this_speaker: z.string(),
  claim_ids: z.array(z.string()).min(1),
  lens: z.enum(["analogy", "inversion", "adjacency", "cross-industry transfer"]),
  adjacent_domains: z.array(z.string()),
  risk: z.string(),
});
export type InsideOutConcept = z.infer<typeof InsideOutConcept>;

export const SynthOut = z.object({
  mappings: z.array(
    z.object({
      theme: z.string(),
      action: z.enum(["add", "refresh", "retire"]),
      angle_id: z.string().optional(),
      inside_out_concept: InsideOutConcept.optional(),
    }),
  ),
});
