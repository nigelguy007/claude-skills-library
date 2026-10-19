// Fixtures for tests and the offline demo. "Helen Marsh" is the spec's fictional speaker:
// a former NHS operations director who speaks on resilience in overstretched teams at
// about £6k a keynote. She is not a real person.
import type { Blueprint, TranscriptSegment } from "../contracts.js";
import type { LLM, LLMRequest, LLMResponse } from "../llm.js";

export const HELEN_ID = "helen";

export const helenTranscript: TranscriptSegment[] = [
  { ts: "00:01:50", speaker: "agent", text: "What did you do before speaking?" },
  { ts: "00:02:10", speaker: "speaker", text: "I was director of operations at an NHS trust for eleven years." },
  { ts: "00:06:30", speaker: "agent", text: "When did your view change?" },
  { ts: "00:06:45", speaker: "speaker", text: "The night we had four wards short and nobody would say no to overtime, I realised the rota was the problem, not the people." },
  { ts: "00:09:50", speaker: "agent", text: "What result are you proudest of?" },
  { ts: "00:10:05", speaker: "speaker", text: "Sickness absence on my wards dropped from about 7% to about 4.5% in a year." },
  { ts: "00:14:10", speaker: "agent", text: "And on agency spend?" },
  { ts: "00:14:32", speaker: "speaker", text: "We cut agency-staff spend by about 30% in eighteen months without losing anyone." },
  { ts: "00:21:20", speaker: "agent", text: "Who has booked you this year?" },
  { ts: "00:21:40", speaker: "speaker", text: "I've spoken for three NHS trusts and two housing associations this year." },
  { ts: "00:33:00", speaker: "agent", text: "Has anyone rebooked you?" },
  { ts: "00:33:15", speaker: "speaker", text: "The CIPD regional group has had me back three years running." },
  { ts: "00:35:50", speaker: "agent", text: "Any testimonial you're proud of?" },
  { ts: "00:36:02", speaker: "speaker", text: "One HR director wrote: 'Helen gave my managers three things they used the next morning.'" },
  { ts: "00:38:00", speaker: "agent", text: "Anything we must never say or name on your behalf?" },
  { ts: "00:38:12", speaker: "speaker", text: "Stay out of NHS pay disputes, and never name St Aldric's, my old trust." },
];

export function helenBlueprint(): Blueprint {
  return {
    blueprint_version: "draft-0",
    positioning: "Helen Marsh helps NHS and public-sector operations leaders stop burnout and agency costs rising together, using rota and handover changes she ran for eleven years as an NHS operations director.",
    angles: [
      { id: "A1", title: "Rotas, Not Heroes", audience: "NHS and care operations managers", problem: "Teams rely on goodwill overtime that burns people out", promise: "A rota rule set that stops heroics becoming the plan", proof_claim_ids: ["C2", "C3"] },
      { id: "A2", title: "The Overstretched Team Playbook", audience: "HR and ops leaders in public-sector and healthcare", problem: "Burnout and agency costs rising together", promise: "Three rota and handover changes teams can start on Monday", proof_claim_ids: ["C4", "C7"] },
      { id: "A3", title: "Saying No Without Losing People", audience: "Line managers in stretched public services", problem: "Managers can't refuse extra work without losing staff goodwill", promise: "Scripts for saying no to overtime that keep the team together", proof_claim_ids: ["C2", "C6"] },
    ],
    claims: [
      { id: "C1", text: "Director of operations at an NHS trust for eleven years", type: "credential", status: "needs_evidence", source_quote_ts: "00:02:10" },
      { id: "C2", text: "Realised during a four-wards-short night that the rota, not the people, was the problem", type: "story", status: "needs_evidence", source_quote_ts: "00:06:45" },
      { id: "C3", text: "Sickness absence on her wards fell from about 7% to about 4.5% in a year", type: "metric", status: "needs_evidence", source_quote_ts: "00:10:05" },
      { id: "C4", text: "Cut agency staffing spend ~30% in 18 months with no redundancies", type: "metric", status: "needs_evidence", source_quote_ts: "00:14:32" },
      { id: "C5", text: "Spoke for three NHS trusts and two housing associations this year", type: "client", status: "needs_evidence", source_quote_ts: "00:21:40" },
      { id: "C6", text: "Rebooked by the CIPD regional group three years running", type: "rebooking", status: "needs_evidence", source_quote_ts: "00:33:15" },
      { id: "C7", text: "An HR director: 'Helen gave my managers three things they used the next morning.'", type: "testimonial", status: "needs_evidence", source_quote_ts: "00:36:02" },
    ],
    voice: {
      traits: ["plain-spoken", "warm", "practical"],
      do: ["short sentences", "start from a real shift or ward", "end on something to try Monday"],
      dont: ["game-changer", "unlock", "in today's fast-paced world"],
      sample_sentences: [
        "The rota was the problem, not the people.",
        "Nobody would say no to overtime.",
        "Try one change on Monday.",
        "Heroics aren't a staffing plan.",
        "Ask who owns the handover.",
      ],
    },
    bio: {
      short_50w: "Helen Marsh spent eleven years as an NHS operations director. She speaks on resilience in overstretched teams.",
      medium_150w: "Helen Marsh spent eleven years as director of operations at an NHS trust. She now helps public-sector and healthcare leaders cut burnout and agency costs with practical rota and handover changes.",
      long_300w: "Helen Marsh spent eleven years as director of operations at an NHS trust, where she learned that the rota, not the people, is usually the problem. She now speaks to NHS trusts, housing associations and HR groups on resilience in overstretched teams, with changes managers can start the next morning.",
    },
    boundaries: { avoid_topics: ["pay disputes"], do_not_name: ["St Aldric's"], notes: [] },
    open_questions: ["Can C4 be cited publicly, or only as 'a large NHS trust'?"],
  };
}

/** Speaker ticks: everything confirmed except C4, which still needs evidence. */
export const helenDecisions = { C1: "speaker_confirmed", C2: "speaker_confirmed", C3: "speaker_confirmed", C5: "speaker_confirmed", C6: "speaker_confirmed", C7: "speaker_confirmed" } as const;

export const helenProfile = {
  name: "Helen Marsh",
  email: "helen@example.com",
  fee_band: "£5k–£8k",
  tier: "T2" as const,
  voice_samples: ["The rota was the problem, not the people.", "Try one change on Monday. Just one."],
  bureau_ids: ["bureau-north"],
  clips: ["https://example.com/clips/helen-cipd-2026"],
  baseline_enquiries_6m: 4,
};

export const helenScreener = { keynote_fee_gbp: 6000, paid_talks_12m: 14, speaking_income_share: 0.7, bureaus: ["bureau-north"], goal: "more_bookings" as const };

export const leedsEnquiry =
  "Hi Helen, we're running our regional workforce summit in Leeds on 12 March, about 300 HR and ops leads. Would you be interested in the closing keynote? What are your fees?";

// ---------------- Scripted model ----------------

type Handler = (input: any, req: LLMRequest) => unknown;

/** A deterministic stand-in for Claude. Routes on which prompt is in the system message. */
export class FakeLLM implements LLM {
  calls: LLMRequest[] = [];
  private handlers: [string, Handler][] = [];

  on(systemIncludes: string, h: Handler): this {
    this.handlers.unshift([systemIncludes, h]);
    return this;
  }

  count(systemIncludes: string): number {
    return this.calls.filter((c) => c.system.includes(systemIncludes)).length;
  }

  async complete(req: LLMRequest): Promise<LLMResponse> {
    this.calls.push(req);
    const h = this.handlers.find(([k]) => req.system.includes(k));
    if (!h) throw new Error(`FakeLLM: no handler for ${req.node}: ${req.system.slice(0, 60)}`);
    const input = (() => {
      try {
        return JSON.parse(req.user.split("\n\nYour previous reply was rejected")[0]!);
      } catch {
        return req.user;
      }
    })();
    const out = h[1](input, req);
    const text = typeof out === "string" ? out : JSON.stringify(out);
    return { text, input_tokens: Math.ceil(req.user.length / 4), output_tokens: Math.ceil(text.length / 4), model: "fake" };
  }
}

export const PROMPT = {
  writer: "You are the Dain Blueprint writer",
  checker: "You are a fact checker",
  draft: "You are the Dain Content agent",
  score: "You are the Dain Bookability scorer",
  extract: "You extract a speaking enquiry",
  reply: "You draft a first reply",
  worker: "You are a research worker",
  skeptic: "You are a skeptic",
  synth: "You map verified market themes",
} as const;

const firstWords = (s: string, n = 8) => s.split(/\s+/).slice(0, n).join(" ");

export function goodScores(text: string, scores: Partial<Record<string, number>> = {}) {
  const q = `"${firstWords(text)}"`;
  const base = { audience_fit: 4, outcome_clarity: 4, credibility: 4, distinctiveness: 4, timeliness: 4, voice_match: 4, ...scores };
  return {
    scores: base,
    reasons: Object.fromEntries(Object.keys(base).map((k) => [k, `${q} reads well for this criterion`])),
    verdict: "pass",
    revision_request: "Name the three changes in one line each so a planner can quote them.",
    rubric_version: "v0",
    label: "provisional",
  };
}

/** A model that behaves well end to end, for the demo and the conductor tests. */
export function helenWorld(): FakeLLM {
  return new FakeLLM()
    .on(PROMPT.writer, () => helenBlueprint())
    .on(PROMPT.checker, () => ({ unsupported: [] }))
    .on(PROMPT.draft, (inp) => {
      const claim = inp.confirmed_claims.find((c: { id: string }) => inp.angle.proof_claim_ids.includes(c.id));
      const text = `${inp.angle.title}: what I learned the hard way.\n\n${claim ? `${claim.text}.` : "The rota was the problem, not the people."}\n\n${inp.angle.promise}. Try one on Monday.`;
      return { text, hook_line: text.split("\n")[0], angle_id: inp.slot.angle_id, claim_ids: claim ? [claim.id] : [], self_flags: [] };
    })
    .on(PROMPT.score, (inp) => goodScores(inp.draft_text))
    .on(PROMPT.extract, () => ({
      organiser: { name: null, org: null, role: null, email: null },
      event: { name: "regional workforce summit", date: "2027-03-12", location: "Leeds", format: "keynote", audience_size: 300, audience_type: "HR and operations leaders" },
      budget_signal: "none",
      deadline: null,
      angle_match: [{ angle_id: "A2", reason: "audience and burnout/agency-cost problem match" }],
      fit: "strong",
      missing_questions: ["Organisation and your role?", "Session length?", "Budget range?", "In person or hybrid?"],
    }))
    .on(PROMPT.reply, () => ({
      reply_draft:
        "Thanks for thinking of me. A closing slot at a workforce summit for HR and ops leads is exactly the room I enjoy. Could you tell me your organisation and role, the session length, your budget range, and whether it's in person or hybrid? I'll come back with options.",
    }));
}
