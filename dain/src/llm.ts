// Model access. Every agent is Claude through the API, called through `callNode`, which
// enforces the node contract (schema mismatch → reject, retry once), the per-call
// budget (breach → escalate, never a silent retry) and the trace (node.called event).
import Anthropic from "@anthropic-ai/sdk";
import type { z } from "zod";
import type { EventLog } from "./events.js";

export interface LLMRequest {
  node: string; // component ID, e.g. "A2"; also lets test fakes route
  system: string;
  user: string;
  model?: string;
  maxTokens?: number;
}
export interface LLMResponse {
  text: string;
  input_tokens: number;
  output_tokens: number;
  model: string;
}
export interface LLM {
  complete(req: LLMRequest): Promise<LLMResponse>;
}

export const DEFAULT_MODEL = process.env.DAIN_MODEL ?? "claude-sonnet-5-5";

// Placeholder prices, GBP per million tokens. Set real ones in the environment before
// reading cost-per-approved-post off the dashboard.
const PRICE_IN = Number(process.env.DAIN_GBP_PER_MTOK_IN ?? 2.4);
const PRICE_OUT = Number(process.env.DAIN_GBP_PER_MTOK_OUT ?? 12);

export class AnthropicLLM implements LLM {
  private client: Anthropic;
  constructor(apiKey = process.env.ANTHROPIC_API_KEY) {
    if (!apiKey) throw new Error("ANTHROPIC_API_KEY is not set");
    this.client = new Anthropic({ apiKey });
  }
  async complete(req: LLMRequest): Promise<LLMResponse> {
    const model = req.model ?? DEFAULT_MODEL;
    const res = await this.client.messages.create({
      model,
      max_tokens: req.maxTokens ?? 2000,
      system: req.system,
      messages: [{ role: "user", content: req.user }],
    });
    const text = res.content.map((b) => (b.type === "text" ? b.text : "")).join("");
    return { text, input_tokens: res.usage.input_tokens, output_tokens: res.usage.output_tokens, model };
  }
}

export interface Budget {
  max_tokens: number;
  max_gbp: number;
  max_ms: number;
}
export const DEFAULT_BUDGET: Budget = { max_tokens: 12000, max_gbp: 0.25, max_ms: 120000 };

export class BudgetExceeded extends Error {}
export class ContractError extends Error {
  constructor(
    message: string,
    readonly raw: string,
  ) {
    super(message);
  }
}

/** Pull the first JSON object out of a model reply (tolerates code fences and prose). */
export function extractJson(text: string): unknown {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  const body = fenced ? fenced[1]! : text;
  const start = body.indexOf("{");
  const end = body.lastIndexOf("}");
  if (start < 0 || end <= start) throw new Error("no JSON object in reply");
  return JSON.parse(body.slice(start, end + 1));
}

export interface NodeContext {
  llm: LLM;
  log: EventLog;
  speaker_id: string | null;
  canon_version: string;
  budget?: Budget;
}

/**
 * One bounded call with a fixed output schema. `extraCheck` lets a node add code-level
 * rules (e.g. B2's "every reason quotes the draft"); a failing check counts as a
 * contract mismatch and gets the same single retry.
 */
export async function callNode<S extends z.ZodTypeAny>(
  ctx: NodeContext,
  req: LLMRequest,
  schema: S,
  extraCheck?: (out: z.infer<S>) => string | null,
): Promise<z.infer<S>> {
  const budget = ctx.budget ?? DEFAULT_BUDGET;
  let user = req.user;
  let lastErr = "";
  let lastRaw = "";
  let spentTokens = 0;
  let spentGbp = 0;
  const started = Date.now();

  for (let attempt = 1; attempt <= 2; attempt++) {
    const res = await ctx.llm.complete({ ...req, user });
    const tokens = res.input_tokens + res.output_tokens;
    const cost = (res.input_tokens * PRICE_IN + res.output_tokens * PRICE_OUT) / 1e6;
    spentTokens += tokens;
    spentGbp += cost;
    const ms = Date.now() - started;
    lastRaw = res.text;

    let verdict = "ok";
    let parsed: z.infer<S> | undefined;
    try {
      const result = schema.safeParse(extractJson(res.text));
      if (!result.success) throw new Error(result.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "));
      const problem = extraCheck?.(result.data);
      if (problem) throw new Error(problem);
      parsed = result.data;
    } catch (e) {
      verdict = "contract_mismatch";
      lastErr = (e as Error).message;
    }
    ctx.log.emit({ type: "node.called", node: req.node, speaker_id: ctx.speaker_id, canon_version: ctx.canon_version, model: res.model, tokens, cost_gbp: cost, ms, verdict });

    if (spentTokens > budget.max_tokens || spentGbp > budget.max_gbp || ms > budget.max_ms)
      throw new BudgetExceeded(`${req.node} breached its budget (${spentTokens} tok, £${spentGbp.toFixed(3)}, ${ms} ms)`);
    if (parsed !== undefined) return parsed;
    user = `${req.user}\n\nYour previous reply was rejected: ${lastErr}\nReply again with JSON only, matching the schema exactly.`;
  }
  throw new ContractError(`${req.node} output failed its contract twice: ${lastErr}`, lastRaw);
}
