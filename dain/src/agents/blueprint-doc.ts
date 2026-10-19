// The Personal Blueprint as a document the speaker receives: the Tier 1 deliverable
// (£995) and the "Blueprints out to pilots" step. Pure code, rendered from the Canon record,
// so it can never say anything the approved Blueprint doesn't.
import type { Blueprint, Claim } from "../contracts.js";

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const list = (xs: string[]) => (xs.length ? `<ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "<p class=\"none\">None recorded.</p>");

const STATUS: Record<Claim["status"], string> = {
  speaker_confirmed: "Confirmed by you",
  needs_evidence: "Not yet confirmed: we won't use this until you do",
  rejected: "Rejected: never used",
};

export function renderBlueprintDocument(speakerName: string, bp: Blueprint, version: number, approvedAt: string): string {
  const claim = (id: string) => bp.claims.find((c) => c.id === id);
  const angles = bp.angles
    .map((a) => {
      const proof = a.proof_claim_ids.map(claim).filter((c): c is Claim => Boolean(c && c.status === "speaker_confirmed"));
      return `<section class="angle"><h3>${esc(a.title)}</h3>
<p><b>For:</b> ${esc(a.audience)}</p><p><b>The problem in the room:</b> ${esc(a.problem)}</p><p><b>Attendees leave with:</b> ${esc(a.promise)}</p>
${proof.length ? `<p><b>Proof:</b></p>${list(proof.map((c) => c.text))}` : `<p class="none">No confirmed proof yet for this talk.</p>`}</section>`;
    })
    .join("\n");
  const ledger = bp.claims
    .map((c) => `<tr><td>${esc(c.id)}</td><td>${esc(c.text)}</td><td>${esc(c.type)}</td><td>${esc(STATUS[c.status])}</td><td>${esc(c.source_quote_ts)}</td></tr>`)
    .join("");

  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(speakerName)} · Personal Blueprint v${version}</title>
<style>body{font:15px/1.55 Georgia,serif;max-width:760px;margin:40px auto;padding:0 16px;color:#1d1d1f}h1{margin:0 0 4px}h2{margin-top:32px;font-size:19px}h3{margin:18px 0 4px;font-size:16px}
.meta{color:#666;font-size:13px}.positioning{font-size:18px;border-left:3px solid #b8673c;padding-left:12px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #ddd;padding:6px;text-align:left;vertical-align:top}.none{color:#888}</style></head><body>
<h1>${esc(speakerName)}</h1><p class="meta">Personal Blueprint · version ${version} · approved ${esc(approvedAt.slice(0, 10))}</p>
<h2>Positioning</h2><p class="positioning">${esc(bp.positioning)}</p>
<h2>Your three talks</h2>${angles}
<h2>How you sound</h2><p><b>Traits:</b> ${esc(bp.voice.traits.join(", "))}</p><p><b>Keep doing:</b></p>${list(bp.voice.do)}<p><b>Never:</b></p>${list(bp.voice.dont)}<p><b>In your words:</b></p>${list(bp.voice.sample_sentences)}
<h2>Boundaries</h2><p><b>Topics we stay away from:</b></p>${list(bp.boundaries.avoid_topics)}<p><b>Never named:</b></p>${list(bp.boundaries.do_not_name)}${bp.boundaries.notes.length ? `<p><b>Also:</b></p>${list(bp.boundaries.notes)}` : ""}
<h2>Bios</h2><h3>Short (50 words)</h3><p>${esc(bp.bio.short_50w)}</p><h3>Medium (150 words)</h3><p>${esc(bp.bio.medium_150w)}</p><h3>Long (300 words)</h3><p>${esc(bp.bio.long_300w)}</p>
<h2>Claims ledger</h2><table><thead><tr><th>ID</th><th>Claim</th><th>Type</th><th>Status</th><th>Said at</th></tr></thead><tbody>${ledger}</tbody></table>
${bp.open_questions.length ? `<h2>Still to decide</h2>${list(bp.open_questions)}` : ""}
</body></html>`;
}
