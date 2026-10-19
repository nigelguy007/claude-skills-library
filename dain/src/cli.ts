// dain CLI.
//   npm run demo               offline run of the whole company with a scripted model
//   npm run demo -- --live     same flow with real Claude (needs ANTHROPIC_API_KEY)
//   npm run dain -- map        print the org chart from the register
import { RUBRIC_V0 } from "./agents/b2.js";
import { onboardingCap } from "./agents/groundskeeper.js";
import { Brain } from "./brain/store.js";
import { Conductor } from "./conductor/conductor.js";
import { dashboard, EventLog } from "./events.js";
import type { ActionAdapter } from "./gate.js";
import { AnthropicLLM, type LLM } from "./llm.js";
import { REGISTER, type Department } from "./register.js";
import { HELEN_ID, helenDecisions, helenProfile, helenScreener, helenTranscript, helenWorld, leedsEnquiry } from "./fixtures/helen.js";

const say = (...parts: string[]) => console.log(parts.join(" "));

function printMap() {
  const depts: Record<Department, string> = { "agentic-os": "Agentic OS", content: "Content", bookability: "Bookability", pipeline: "Pipeline (sales)" };
  say("YOU");
  say(" └─ C0 Conductor (code, fixed routes)");
  for (const [d, label] of Object.entries(depts)) {
    say(`     ├─ ${label}`);
    for (const c of REGISTER.filter((x) => x.department === d && x.id !== "C0"))
      say(`     │   ├─ ${c.id.padEnd(3)} ${c.name} · ${c.archetype} · ${c.type}${c.llm ? " (LLM)" : ""} · ${c.phase} · owner ${c.owner}`);
  }
  say("\nEvery box reads the Canon and writes the Chronicle (src/brain/store.ts).");
}

function stubAdapter(action: "publish" | "send"): ActionAdapter {
  const done = new Map<string, string>();
  return {
    action,
    execute: async ({ idempotency_key }) => {
      const id = `${action}-${done.size + 1}`;
      done.set(idempotency_key, id);
      return id;
    },
    findExisting: async (k) => done.get(k) ?? null,
  };
}

async function demo(live: boolean) {
  const llm: LLM = live ? new AnthropicLLM() : helenWorld();
  const brain = new Brain();
  const log = new EventLog();
  const c = new Conductor({ brain, log, llm, adapters: { linkedin: stubAdapter("publish"), email: stubAdapter("send") } });
  const PL = { approver: "Product lead", role: "product_lead" as const };
  const BS = { approver: "Booking specialist", role: "specialist" as const };
  const HELEN = { approver: "Helen Marsh", role: "speaker" as const };

  say(`Dain demo (${live ? "live Claude" : "scripted model, no API calls"}). Speaker: Helen Marsh (fictional).\n`);
  brain.promote("rubric", "current", RUBRIC_V0, PL);
  brain.promote("bureau", "bureau-north", { id: "bureau-north", name: "North Speakers", contact: "Priya Shah", channel: "email", bio_lengths: ["short", "medium"], wants_one_sheet: true, photo_spec: "2000px", cadence_days: 90 }, BS);

  say("1. Onboard → interview → Blueprint");
  say("   ", JSON.stringify(await c.dispatch("speaker.onboard", { speaker_id: HELEN_ID, profile: helenProfile, screener: helenScreener })));
  say("   ", JSON.stringify(await c.dispatch("interview.transcript", { speaker_id: HELEN_ID, transcript: helenTranscript })));
  say("   ", JSON.stringify(await c.dispatch("blueprint.confirm", { speaker_id: HELEN_ID, decisions: helenDecisions, approval: HELEN })));

  say("\n2. Weekly content (A2 ↔ B2, fanned out)");
  await c.dispatch("content.weekly", { speaker_id: HELEN_ID, week: "2026-W45" });
  const queue = c.review.queue("specialist").filter((i) => i.entity === "ContentItem");
  for (const i of queue) say(`   ${i.id}  [${i.state}] ${i.content.split("\n")[0]}`);

  const first = queue[0];
  if (first) {
    say("\n3. Specialist approves, Helen approves, Action Gate publishes");
    await c.dispatch("review.open", { item_id: first.id, role: "specialist", at_ms: 0 });
    for (let t = 60000; t <= 180000; t += 60000) c.review.activity(first.id, t);
    await c.dispatch("review.approve", { item_id: first.id, approval: BS, at_ms: 240000 });
    await c.dispatch("review.open", { item_id: first.id, role: "speaker", at_ms: 0 });
    for (let t = 60000; t <= 420000; t += 60000) c.review.activity(first.id, t);
    say("   ", JSON.stringify(await c.dispatch("review.approve", { item_id: first.id, approval: HELEN, at_ms: 480000 })));
  }

  say("\n4. Enquiry from email (Leeds summit)");
  await c.dispatch("enquiry.capture", { speaker_id: HELEN_ID, enquiry_id: "enq-1", raw: { channel: "email", raw_text: leedsEnquiry, completeness: "full", received_at: new Date(Date.now() - 20 * 60000).toISOString() } });
  const enq = c.review.item("enq-1");
  say(`   reply draft:\n${enq.content.replace(/^/gm, "     ")}`);
  say(`   guard: ${enq.blocked.length ? `BLOCKED ${JSON.stringify(enq.blocked)}` : "clean"}`);

  say("\n5. Nightly groundskeeper");
  const r = (await c.dispatch("nightly", {})) as Record<string, unknown>;
  say("   ", JSON.stringify({ unconfirmed_claims: r.unconfirmed_claims, stale_angle_evidence: (r.stale_angle_evidence as unknown[]).length, rubric_provisional: r.rubric_provisional }));

  say("\n6. Pilot dashboard (R5)");
  for (const [k, v] of Object.entries(dashboard(log))) say(`   ${k.padEnd(28)} ${v === null ? "—" : typeof v === "number" ? Math.round(v * 1000) / 1000 : v}`);
  say(`   onboarding cap @ 30 h/wk, 22 min/speaker   ${onboardingCap(1800, 22)}`);
}

const [cmd = "demo", ...rest] = process.argv.slice(2);
if (cmd === "map") printMap();
else if (cmd === "demo") await demo(rest.includes("--live"));
else {
  console.error(`unknown command ${cmd}; use demo [--live] | map`);
  process.exit(1);
}
