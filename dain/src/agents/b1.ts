// B1 · Relevance Radar (with the former A3 as its inside-out mode). A diamond graph:
//   FAN OUT     one worker per sector × source type → raw signals
//   REDUCE      code: dedupe, drop > 180 days, cluster by theme
//   VERIFY      per signal: correct? (fresh-context skeptic) · current? (code) · real? (code: page has the quote); keep if 2 of 3
//   SYNTHESISE  code ranks; one call maps ranked themes to each speaker's confirmed expertise
// Output goes to the Chronicle only. A specialist promotes; the speaker approves angle changes.
import { SkepticOut, SynthOut, WorkerOut, type Blueprint, type InsideOutConcept, type RawSignal } from "../contracts.js";
import type { Brain } from "../brain/store.js";
import { callNode, type NodeContext } from "../llm.js";
import { loadPrompt } from "../prompts.js";

export const MAX_AGE_DAYS = 180;
export const HIGH_CONFIDENCE_WINDOW_DAYS = 90;
const DAY = 86400000;

export interface Source {
  sector: string;
  source_type: "agenda" | "call_for_speakers" | "bureau_trending" | "enquiries" | "booker_interviews";
  url: string;
  fee_paying?: boolean;
}

/** The fetch tool (Firecrawl, Apify…). Bought, not built. Logged-in sites are out of scope. */
export interface Fetcher {
  fetch(url: string): Promise<string | null>;
}

export interface Proposal {
  theme: string;
  action: "add" | "refresh" | "retire";
  angle_id?: string;
  evidence: { url: string; quote: string; date: string; event: string }[];
  evidence_count: number;
  confidence: "low" | "med" | "high";
  weak_evidence: boolean;
  inside_out_concept?: InsideOutConcept;
}

const themeKey = (t: string) => t.toLowerCase().replace(/[^a-z0-9 ]/g, "").replace(/\s+/g, " ").trim();
const host = (u: string) => new URL(u).hostname.replace(/^www\./, "");
const ageDays = (date: string, now: Date) => (now.getTime() - new Date(date).getTime()) / DAY;

export function reduceSignals(signals: RawSignal[], now: Date): Map<string, RawSignal[]> {
  const seen = new Set<string>();
  const clusters = new Map<string, RawSignal[]>();
  for (const s of signals) {
    const age = ageDays(s.date, now);
    if (!Number.isFinite(age) || age > MAX_AGE_DAYS || age < -1) continue;
    const id = `${s.url}|${themeKey(s.quote)}`;
    if (seen.has(id)) continue;
    seen.add(id);
    const k = themeKey(s.theme);
    clusters.set(k, [...(clusters.get(k) ?? []), s]);
  }
  return clusters;
}

export function confidenceFor(evidence: RawSignal[], now: Date): Proposal["confidence"] {
  const recentHosts = new Set(evidence.filter((e) => ageDays(e.date, now) <= HIGH_CONFIDENCE_WINDOW_DAYS).map((e) => host(e.url)));
  if (recentHosts.size >= 3) return "high";
  return new Set(evidence.map((e) => host(e.url))).size >= 2 ? "med" : "low";
}

/** Rank by evidence count × recency (newest evidence counts most). */
export function rankThemes(clusters: Map<string, RawSignal[]>, now: Date): { theme: string; signals: RawSignal[]; score: number }[] {
  return [...clusters.entries()]
    .map(([theme, signals]) => ({
      theme,
      signals,
      score: signals.reduce((s, x) => s + Math.max(0, 1 - ageDays(x.date, now) / MAX_AGE_DAYS), 0),
    }))
    .sort((a, b) => b.score - a.score);
}

export async function runRadar(
  ctx: NodeContext,
  brain: Brain,
  args: { sources: Source[]; fetcher: Fetcher; speakers: { speaker_id: string; blueprint: Blueprint }[]; week: string; top_n?: number },
): Promise<Map<string, Proposal[]>> {
  const now = brain.clock();
  const pages = new Map<string, string>();

  // FAN OUT
  const groups = new Map<string, Source[]>();
  for (const s of args.sources) groups.set(`${s.sector}×${s.source_type}`, [...(groups.get(`${s.sector}×${s.source_type}`) ?? []), s]);
  const workerOutputs = await Promise.all(
    [...groups.entries()].map(async ([group, sources]) => {
      const fetched = [];
      for (const s of sources) {
        const text = await args.fetcher.fetch(s.url);
        if (text) {
          pages.set(s.url, text);
          fetched.push({ url: s.url, text: text.slice(0, 20000) });
        }
      }
      if (!fetched.length) return [];
      const out = await callNode(
        { ...ctx, speaker_id: null },
        { node: "B1", system: loadPrompt("bookability/b1-radar/worker"), user: JSON.stringify({ group, today: now.toISOString().slice(0, 10), pages: fetched }) },
        WorkerOut,
      );
      return out.signals;
    }),
  );
  const raw = workerOutputs.flat();
  brain.append("radar.raw_signals", null, { week: args.week, signals: raw });

  // REDUCE
  const clusters = reduceSignals(raw, now);

  // VERIFY
  const verified = new Map<string, RawSignal[]>();
  await Promise.all(
    [...clusters.entries()].map(async ([theme, signals]) => {
      const kept: RawSignal[] = [];
      for (const s of signals) {
        const current = ageDays(s.date, now) <= MAX_AGE_DAYS;
        const real = (pages.get(s.url) ?? "").toLowerCase().includes(s.quote.toLowerCase().slice(0, 80));
        const skeptic = await callNode(
          { ...ctx, speaker_id: null },
          { node: "B1", system: loadPrompt("bookability/b1-radar/skeptic"), user: JSON.stringify({ theme: s.theme, quote: s.quote }) },
          SkepticOut,
        );
        if ([skeptic.supports, current, real].filter(Boolean).length >= 2) kept.push(s);
      }
      if (kept.length) verified.set(theme, kept);
    }),
  );
  brain.append("radar.verified", null, { week: args.week, themes: [...verified.keys()] });

  // SYNTHESISE
  const ranked = rankThemes(verified, now).slice(0, args.top_n ?? 8);
  const result = new Map<string, Proposal[]>();
  for (const sp of args.speakers) {
    const confirmed = sp.blueprint.claims.filter((c) => c.status === "speaker_confirmed");
    const out = await callNode(
      { ...ctx, speaker_id: sp.speaker_id },
      {
        node: "B1",
        system: loadPrompt("bookability/b1-radar/synthesise"),
        user: JSON.stringify({
          themes: ranked.map((r) => ({ theme: r.theme, evidence: r.signals.map(({ quote, event, date }) => ({ quote, event, date })) })),
          angles: sp.blueprint.angles,
          confirmed_claims: confirmed.map(({ id, text }) => ({ id, text })),
        }),
      },
      SynthOut,
    );
    const confirmedIds = new Set(confirmed.map((c) => c.id));
    const angleIds = new Set(sp.blueprint.angles.map((a) => a.id));
    const proposals: Proposal[] = [];
    for (const m of out.mappings) {
      const r = ranked.find((x) => x.theme === themeKey(m.theme));
      if (!r) continue; // the model named a theme the evidence doesn't contain
      if (m.angle_id && !angleIds.has(m.angle_id)) continue;
      // A3 rule: no concept without both a signal and ≥ 1 confirmed claim.
      const concept = m.inside_out_concept && m.inside_out_concept.claim_ids.every((id) => confirmedIds.has(id)) ? m.inside_out_concept : undefined;
      const confidence = confidenceFor(r.signals, now);
      proposals.push({
        theme: r.theme,
        action: m.action,
        angle_id: m.angle_id,
        evidence: r.signals.map(({ url, quote, date, event }) => ({ url, quote, date, event })),
        evidence_count: r.signals.length,
        confidence,
        weak_evidence: confidence !== "high",
        inside_out_concept: concept,
      });
    }
    brain.append("radar.proposals", sp.speaker_id, { week: args.week, proposals });
    result.set(sp.speaker_id, proposals);
  }
  return result;
}
