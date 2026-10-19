// R1 · Component register. One row per component: the org chart of the company map
// (department, archetype) and the build register of the spec (type, owner, eval) in one place.
// tests/register.test.ts enforces the rules: ≤ 5 LLM components in v1, every workflow has an
// owner and an autonomy tag, nothing that writes outside Dain is fully autonomous, every SOP
// file exists and agrees with this table.

export type Department = "content" | "bookability" | "pipeline" | "agentic-os";
// The map's six archetypes, plus "gate": the human review step, which the map has no word for.
export type Archetype = "scout" | "analyst" | "builder" | "publisher" | "groundskeeper" | "conductor" | "gate";
export type Autonomy = "human-led" | "human-assisted" | "fully-autonomous";

export interface Workflow {
  name: string;
  autonomy: Autonomy;
  external_write: boolean; // publishes, sends or shares outside Dain
}

export interface Component {
  id: string;
  name: string;
  department: Department;
  archetype: Archetype;
  type: "agent" | "loop" | "node" | "code" | "ui";
  llm: boolean;
  phase: "days-1-14" | "days-16-29" | "post-launch";
  owner: "TL" | "PL" | "BS" | "CL";
  sop: string; // departments/<dept>/<dir>/SKILL.md
  eval: string; // test or eval set that can fail it
  workflows: Workflow[];
}

export const REGISTER: Component[] = [
  {
    id: "C0", name: "Conductor (Dain Coordinator)", department: "agentic-os", archetype: "conductor", type: "code", llm: false, phase: "days-1-14", owner: "TL",
    sop: "agentic-os/c0-conductor", eval: "tests/conductor.test.ts",
    workflows: [{ name: "Route commands, run state machines, enforce budgets", autonomy: "fully-autonomous", external_write: false }],
  },
  {
    id: "AG", name: "Action Gate + publishers (LinkedIn, email)", department: "agentic-os", archetype: "publisher", type: "code", llm: false, phase: "days-1-14", owner: "TL",
    sop: "agentic-os/action-gate", eval: "tests/gate.test.ts",
    workflows: [
      { name: "Publish an approved post", autonomy: "human-assisted", external_write: true },
      { name: "Send an approved reply", autonomy: "human-assisted", external_write: true },
    ],
  },
  {
    id: "B3", name: "Review module", department: "agentic-os", archetype: "gate", type: "ui", llm: false, phase: "days-1-14", owner: "BS",
    sop: "agentic-os/b3-review", eval: "tests/review.test.ts",
    workflows: [{ name: "Specialist then speaker review, edit timer, token issue", autonomy: "human-led", external_write: false }],
  },
  {
    id: "GK", name: "Groundskeeper", department: "agentic-os", archetype: "groundskeeper", type: "code", llm: false, phase: "days-1-14", owner: "TL",
    sop: "agentic-os/groundskeeper", eval: "tests/groundskeeper.test.ts",
    workflows: [
      { name: "Nightly sweep: stuck items, stale facts, stale packs", autonomy: "fully-autonomous", external_write: false },
      { name: "Weekly onboarding cap (R8)", autonomy: "fully-autonomous", external_write: false },
    ],
  },
  {
    id: "A1", name: "Voice-Interview & Blueprint", department: "content", archetype: "analyst", type: "agent", llm: true, phase: "days-1-14", owner: "PL",
    sop: "content/a1-voice-interview", eval: "tests/a1.test.ts",
    workflows: [
      { name: "Interview → Blueprint draft → transcript check", autonomy: "fully-autonomous", external_write: false },
      { name: "Speaker confirms claims; Blueprint enters the Canon", autonomy: "human-led", external_write: false },
    ],
  },
  {
    id: "A2", name: "Content & Drafting", department: "content", archetype: "builder", type: "loop", llm: true, phase: "days-1-14", owner: "PL",
    sop: "content/a2-drafting", eval: "tests/content-loop.test.ts",
    workflows: [{ name: "Weekly plan and 3 drafts into review", autonomy: "human-assisted", external_write: false }],
  },
  {
    id: "B2", name: "Bookability Scoring", department: "bookability", archetype: "analyst", type: "node", llm: true, phase: "days-1-14", owner: "BS",
    sop: "bookability/b2-scoring", eval: "tests/b2.test.ts",
    workflows: [
      { name: "Score each draft in a fresh context", autonomy: "fully-autonomous", external_write: false },
      { name: "Change the rubric", autonomy: "human-led", external_write: false },
    ],
  },
  {
    id: "P1", name: "Lead Capture & Pipeline", department: "pipeline", archetype: "analyst", type: "node", llm: true, phase: "days-1-14", owner: "TL",
    sop: "pipeline/p1-capture", eval: "tests/p1.test.ts",
    workflows: [
      { name: "Capture and extract an enquiry onto the board", autonomy: "fully-autonomous", external_write: false },
      { name: "Draft the reply", autonomy: "human-assisted", external_write: false },
      { name: "Quote fees, hold dates, accept terms", autonomy: "human-led", external_write: true },
    ],
  },
  {
    id: "B1", name: "Relevance Radar (incl. inside-out mode, former A3)", department: "bookability", archetype: "scout", type: "agent", llm: true, phase: "days-16-29", owner: "BS",
    sop: "bookability/b1-radar", eval: "tests/b1.test.ts",
    workflows: [
      { name: "Weekly collection, verification and proposals into the Chronicle", autonomy: "fully-autonomous", external_write: false },
      { name: "Promote evidence to the Canon; change a speaker's angles", autonomy: "human-led", external_write: false },
    ],
  },
  {
    id: "P2", name: "Bureau & Bio Asset Pack", department: "pipeline", archetype: "builder", type: "code", llm: false, phase: "days-16-29", owner: "BS",
    sop: "pipeline/p2-asset-pack", eval: "tests/p2.test.ts",
    workflows: [
      { name: "Render pack and cover notes on Canon change", autonomy: "fully-autonomous", external_write: false },
      { name: "Send pack to a bureau", autonomy: "human-led", external_write: true },
    ],
  },
  {
    id: "P3", name: "Pass the Gig referral (manual v0)", department: "pipeline", archetype: "builder", type: "code", llm: false, phase: "post-launch", owner: "PL",
    sop: "pipeline/p3-referral", eval: "tests/p3.test.ts",
    workflows: [{ name: "Speaker names a peer; redacted intro drafted", autonomy: "human-led", external_write: true }],
  },
  {
    id: "L1", name: "Outcome & Learning", department: "agentic-os", archetype: "analyst", type: "node", llm: true, phase: "post-launch", owner: "PL",
    sop: "agentic-os/l1-learning", eval: "tests/calibration.test.ts",
    workflows: [{ name: "Monthly proposals for rubric and angle changes", autonomy: "human-led", external_write: false }],
  },
];

export const V1_LLM_BUDGET = 5;
