// The speaker's desk by email (deck BE8: "Speaker receives email. Approve / Edit / Reject
// via simple form."). Parses a reply into one of three decisions. Anything ambiguous is
// refused, so a stray reply can never approve a post.
import { REASON_CODES, type ReasonCode } from "./review.js";

export type ReplyDecision =
  | { decision: "approve" }
  | { decision: "edit"; text: string }
  | { decision: "reject"; reason: ReasonCode; note: string };

/** Drop quoted history and signatures so only what the speaker typed is read. */
export function newText(body: string): string {
  const out: string[] = [];
  for (const line of body.replace(/\r\n/g, "\n").split("\n")) {
    if (/^\s*>/.test(line)) break;
    if (/^On .+wrote:\s*$/.test(line.trim())) break;
    if (/^-- ?$/.test(line)) break;
    if (/^-{2,}\s*Original Message/i.test(line.trim())) break;
    out.push(line);
  }
  return out.join("\n").trim();
}

export function parseReply(body: string): ReplyDecision | null {
  const text = newText(body);
  const [first = "", ...rest] = text.split("\n");
  const head = first.trim().toLowerCase().replace(/[.!:]+$/, "");
  const after = rest.join("\n").trim();

  if (/^(approve|approved|yes|ok|go)$/.test(head)) return { decision: "approve" };

  const edit = first.trim().match(/^(edit|change)\s*:?\s*(.*)$/i);
  if (edit) {
    const t = [edit[2] ?? "", after].filter(Boolean).join("\n").trim();
    return t ? { decision: "edit", text: t } : null; // "EDIT" with no new text is ambiguous
  }

  const rej = first.trim().match(/^(reject|rejected|no)\b\s*:?\s*(.*)$/i);
  if (rej) {
    const note = [rej[2] ?? "", after].filter(Boolean).join(" ").trim();
    const code = REASON_CODES.find((c) => note.toLowerCase().replace(/[\s-]+/g, "_").includes(c)) ?? "other";
    return { decision: "reject", reason: code, note };
  }
  return null;
}

/** The simple form posts structured fields; same three outcomes, same refusals. */
export function parseForm(form: { decision: "approve" | "edit" | "reject"; text?: string; reason?: string }): ReplyDecision | null {
  if (form.decision === "approve") return { decision: "approve" };
  if (form.decision === "edit") return form.text?.trim() ? { decision: "edit", text: form.text.trim() } : null;
  const reason = (REASON_CODES as readonly string[]).includes(form.reason ?? "") ? (form.reason as ReasonCode) : "other";
  return { decision: "reject", reason, note: form.reason ?? "" };
}
