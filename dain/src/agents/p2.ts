// P2 · Bureau & Bio Asset Pack. Pure code: templates filled from the Canon, rendered in
// each bureau's format, with a templated cover note listing what changed. A human sends it.
// (The spec drafts the cover note with a prompt; it fails R1's judgement test, so it's a template.)
import type { Blueprint } from "../contracts.js";
import { guardReply } from "./p1.js";

export interface BureauProfile {
  id: string;
  name: string;
  contact: string;
  channel: "email" | "portal";
  bio_lengths: ("short" | "medium" | "long")[];
  wants_one_sheet: boolean;
  photo_spec: string;
  cadence_days: number;
}

export interface PackFile {
  name: string;
  content: string;
}

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const confirmed = (bp: Blueprint) => bp.claims.filter((c) => c.status === "speaker_confirmed");
const REPUTATION = new Set(["testimonial", "rebooking", "client"]);

export function renderPack(speakerName: string, bp: Blueprint, packVersion: string, clips: string[]): PackFile[] {
  const ok = confirmed(bp);
  const talks = bp.angles
    .map((a) => {
      const proof = ok.filter((c) => a.proof_claim_ids.includes(c.id)).map((c) => `- ${c.text}`);
      return [`## ${a.title}`, `**For:** ${a.audience}`, `**The problem:** ${a.problem}`, `**Attendees leave with:** ${a.promise}`, ...(proof.length ? ["", "**Proof:**", ...proof] : [])].join("\n");
    })
    .join("\n\n");
  const rep = ok.filter((c) => REPUTATION.has(c.type));
  const oneSheet = `<!doctype html><html><head><meta charset="utf-8"><title>${esc(speakerName)} · one-sheet</title>
<style>body{font:15px/1.5 Georgia,serif;max-width:720px;margin:32px auto;color:#1d1d1f}h1{margin:0}h2{font-size:17px;margin:20px 0 4px}small{color:#666}</style></head><body>
<h1>${esc(speakerName)}</h1><p>${esc(bp.positioning)}</p>
${bp.angles.map((a) => `<h2>${esc(a.title)}</h2><p><b>For</b> ${esc(a.audience)}. <b>Attendees leave with</b> ${esc(a.promise)}</p>`).join("\n")}
${rep.length ? `<h2>What clients say and do</h2><ul>${rep.map((c) => `<li>${esc(c.text)}</li>`).join("")}</ul>` : ""}
${clips.length ? `<h2>Clips</h2><ul>${clips.map((u) => `<li>${esc(u)}</li>`).join("")}</ul>` : ""}
<small>Pack ${esc(packVersion)}. Print to PDF for bureaus that want a PDF.</small></body></html>`;
  return [
    { name: "bio_short.txt", content: bp.bio.short_50w },
    { name: "bio_medium.txt", content: bp.bio.medium_150w },
    { name: "bio_long.txt", content: bp.bio.long_300w },
    { name: "talks.md", content: `# ${speakerName}: talks\n\n${talks}\n` },
    { name: "one_sheet.html", content: oneSheet },
  ];
}

/** What changed between two approved Blueprints, in words a bureau agent can scan. */
export function changesSince(prev: Blueprint | undefined, cur: Blueprint): string[] {
  if (!prev) return ["First pack: full bios, talk descriptions and one-sheet"];
  const out: string[] = [];
  if (prev.positioning !== cur.positioning) out.push("Updated positioning line");
  const prevAngles = new Map(prev.angles.map((a) => [a.id, a]));
  for (const a of cur.angles) {
    const p = prevAngles.get(a.id);
    if (!p) out.push(`New talk: ${a.title}`);
    else if (p.title !== a.title || p.promise !== a.promise || p.audience !== a.audience) out.push(`Refreshed talk: ${a.title}`);
  }
  for (const p of prev.angles) if (!cur.angles.some((a) => a.id === p.id)) out.push(`Retired talk: ${p.title}`);
  const prevOk = new Set(confirmed(prev).map((c) => c.id));
  const added = confirmed(cur).filter((c) => !prevOk.has(c.id));
  if (added.some((c) => REPUTATION.has(c.type))) out.push("New testimonials or rebookings");
  if (added.some((c) => !REPUTATION.has(c.type))) out.push("New results and credentials");
  if (prev.bio.medium_150w !== cur.bio.medium_150w) out.push("Updated bios");
  return out;
}

export function coverNote(bureau: BureauProfile, speakerName: string, changes: string[], packVersion: string): string {
  const note = [
    `Hi ${bureau.contact.split(" ")[0]},`,
    "",
    `Here is an updated pack for ${speakerName} (version ${packVersion}). What's new:`,
    ...changes.map((c) => `- ${c}`),
    "",
    bureau.channel === "portal" ? "Files are attached in the formats your portal takes." : "Files are attached in the formats you asked for.",
    "Shout if anything needs a different format or length.",
  ].join("\n");
  const fees = guardReply(note).filter((h) => h.kind === "fee");
  if (fees.length) throw new Error(`cover note must not contain fees: ${fees.map((f) => f.match).join(", ")}`);
  return note;
}

export function packFor(bureau: BureauProfile, files: PackFile[]): PackFile[] {
  const lengths = new Set(bureau.bio_lengths.map((l) => `bio_${l}.txt`));
  return files.filter((f) => lengths.has(f.name) || f.name === "talks.md" || (bureau.wants_one_sheet && f.name === "one_sheet.html"));
}
