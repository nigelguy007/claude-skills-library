// A minimal durable runner with the semantics R9 asks of the real engine: completed steps
// are memoised (a restart replays without re-running them), a run can pause for days on a
// named event without holding a process, and a resumed run continues where it stopped.
// In deployment each `step` maps to an Inngest step.run and each `waitFor` to
// step.waitForEvent (or the Temporal/n8n equivalents). Step state lives in the brain, so
// "restart" here means a new Conductor over the same store.
import type { Brain } from "../brain/store.js";

export class Paused extends Error {
  constructor(readonly waiting_for: string) {
    super(`paused: waiting for ${waiting_for}`);
  }
}

interface RunRecord {
  steps: Map<string, unknown>;
  events: Map<string, unknown>;
  status: "running" | "paused" | "done" | "failed";
  waiting_for?: string;
  error?: string;
}

export class Run {
  constructor(
    private rec: RunRecord,
    readonly id: string,
  ) {}

  async step<T>(name: string, fn: () => Promise<T> | T): Promise<T> {
    if (this.rec.steps.has(name)) return this.rec.steps.get(name) as T;
    const value = await fn();
    this.rec.steps.set(name, value);
    return value;
  }

  waitFor<T>(event: string): T {
    if (this.rec.events.has(event)) return this.rec.events.get(event) as T;
    throw new Paused(event);
  }
}

export type RunOutcome<T> = { status: "done"; value: T } | { status: "paused"; waiting_for: string } | { status: "failed"; error: string };

function record(brain: Brain, runId: string): RunRecord {
  const key = `run:${runId}`;
  if (!brain.kv.has(key)) brain.kv.set(key, { steps: new Map(), events: new Map(), status: "running" } satisfies RunRecord);
  return brain.kv.get(key) as RunRecord;
}

export async function runWorkflow<T>(brain: Brain, runId: string, wf: (run: Run) => Promise<T>): Promise<RunOutcome<T>> {
  const rec = record(brain, runId);
  if (rec.status === "done") return { status: "done", value: rec.steps.get("__result") as T };
  rec.status = "running";
  try {
    const value = await wf(new Run(rec, runId));
    rec.steps.set("__result", value);
    rec.status = "done";
    return { status: "done", value };
  } catch (e) {
    if (e instanceof Paused) {
      rec.status = "paused";
      rec.waiting_for = e.waiting_for;
      return { status: "paused", waiting_for: e.waiting_for };
    }
    // Leave status "running" for crashes so a retry resumes; failures are rethrown.
    rec.error = (e as Error).message;
    throw e;
  }
}

export function deliver(brain: Brain, runId: string, event: string, payload: unknown): void {
  record(brain, runId).events.set(event, payload);
}

export function runStatus(brain: Brain, runId: string): Pick<RunRecord, "status" | "waiting_for" | "error"> | undefined {
  const rec = brain.kv.get(`run:${runId}`) as RunRecord | undefined;
  return rec && { status: rec.status, waiting_for: rec.waiting_for, error: rec.error };
}
