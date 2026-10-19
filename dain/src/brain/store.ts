// Layer 1 of the company map: one shared brain every component reads and writes.
//
// Chronicle  append-only raw material (transcripts, signals, drafts, model outputs).
//            Anything an agent writes lands here first. Never a source for publishable claims.
// Canon      versioned, human-approved facts (Blueprint, claims, rubric, angles, evidence).
//            Agents read it; only a human approval moves a record across the firewall.
//
// This in-memory implementation backs the tests and the demo. db/schema.sql is the
// Postgres shape of the same tables for deployment.
import { randomUUID } from "node:crypto";

export type HumanRole = "speaker" | "specialist" | "product_lead";
export interface Approval {
  approver: string;
  role: HumanRole;
}

export interface ChronicleEntry<T = unknown> {
  id: string;
  kind: string;
  speaker_id: string | null;
  payload: T;
  at: string;
}

export interface CanonRecord<T = unknown> {
  kind: string;
  key: string;
  version: number;
  value: T;
  approved_by: string;
  approved_role: HumanRole;
  approved_at: string;
  source_chronicle_id?: string;
}

const HUMAN_ROLES: ReadonlySet<string> = new Set(["speaker", "specialist", "product_lead"]);

export class FirewallError extends Error {}

export class Brain {
  private chronicle: ChronicleEntry[] = [];
  private canon = new Map<string, CanonRecord[]>();
  readonly kv = new Map<string, unknown>();

  constructor(private now: () => Date = () => new Date()) {}

  clock(): Date {
    return this.now();
  }

  // ---- Chronicle ----
  append<T>(kind: string, speakerId: string | null, payload: T): ChronicleEntry<T> {
    const entry: ChronicleEntry<T> = { id: randomUUID(), kind, speaker_id: speakerId, payload, at: this.now().toISOString() };
    this.chronicle.push(entry as ChronicleEntry);
    return entry;
  }

  read<T>(kind: string, speakerId?: string): ChronicleEntry<T>[] {
    return this.chronicle.filter(
      (e) => e.kind === kind && (speakerId === undefined || e.speaker_id === speakerId),
    ) as ChronicleEntry<T>[];
  }

  entry<T>(id: string): ChronicleEntry<T> | undefined {
    return this.chronicle.find((e) => e.id === id) as ChronicleEntry<T> | undefined;
  }

  // ---- Canon ----
  promote<T>(kind: string, key: string, value: T, approval: Approval, sourceChronicleId?: string): CanonRecord<T> {
    if (!approval?.approver || !HUMAN_ROLES.has(approval.role))
      throw new FirewallError(`Canon write to ${kind}/${key} needs a named human approver`);
    const id = `${kind}/${key}`;
    const history = this.canon.get(id) ?? [];
    const rec: CanonRecord<T> = {
      kind,
      key,
      version: history.length + 1,
      value: structuredClone(value),
      approved_by: approval.approver,
      approved_role: approval.role,
      approved_at: this.now().toISOString(),
      source_chronicle_id: sourceChronicleId,
    };
    history.push(rec as CanonRecord);
    this.canon.set(id, history);
    return rec;
  }

  get<T>(kind: string, key: string): CanonRecord<T> | undefined {
    const h = this.canon.get(`${kind}/${key}`);
    return h?.[h.length - 1] as CanonRecord<T> | undefined;
  }

  history<T>(kind: string, key: string): CanonRecord<T>[] {
    return (this.canon.get(`${kind}/${key}`) ?? []) as CanonRecord<T>[];
  }

  canonOf<T>(kind: string): CanonRecord<T>[] {
    const out: CanonRecord<T>[] = [];
    for (const h of this.canon.values()) {
      const last = h[h.length - 1];
      if (last && last.kind === kind) out.push(last as CanonRecord<T>);
    }
    return out;
  }

  /** A short fingerprint of everything an agent might read, logged with every node call. */
  canonVersion(speakerId: string): string {
    const bp = this.get("blueprint", speakerId);
    const rubric = this.get("rubric", "current");
    return `bp${bp?.version ?? 0}.rubric${rubric?.version ?? 0}`;
  }
}
