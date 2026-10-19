import { describe, expect, it } from "vitest";
import { applyConfirmation } from "../src/agents/a1.js";
import { confidenceFor, reduceSignals, runRadar, type Fetcher } from "../src/agents/b1.js";
import { Brain } from "../src/brain/store.js";
import { EventLog } from "../src/events.js";
import { FakeLLM, helenBlueprint, helenDecisions, PROMPT } from "../src/fixtures/helen.js";

const now = new Date("2026-11-01T00:00:00Z");
const sig = (theme: string, url: string, date: string, quote = `Session on ${theme}`) => ({ theme, quote, url, event: "Summit", date });

describe("radar reduce and confidence", () => {
  it("drops duplicates and anything older than 180 days, and clusters by theme", () => {
    const c = reduceSignals(
      [
        sig("Limits of AI in hiring", "https://a.org/agenda", "2026-10-01"),
        sig("limits of AI in hiring", "https://a.org/agenda", "2026-10-01"),
        sig("Limits of AI in hiring", "https://b.org/agenda", "2026-09-01"),
        sig("Ethical AI", "https://c.org/agenda", "2025-12-01"),
      ],
      now,
    );
    expect([...c.keys()]).toEqual(["limits of ai in hiring"]);
    expect(c.get("limits of ai in hiring")).toHaveLength(2);
  });

  it("high confidence needs 3 independent sites in 90 days", () => {
    const three = [sig("t", "https://a.org/x", "2026-10-01"), sig("t", "https://b.org/x", "2026-09-15"), sig("t", "https://www.c.org/x", "2026-08-20")];
    expect(confidenceFor(three, now)).toBe("high");
    expect(confidenceFor([...three.slice(0, 2), sig("t", "https://a.org/y", "2026-10-02")], now)).toBe("med");
    expect(confidenceFor([three[0]!], now)).toBe("low");
  });
});

describe("radar diamond", () => {
  it("keeps only signals that pass 2 of 3 checks, drops invented themes and unbacked concepts", async () => {
    const pages: Record<string, string> = {
      "https://nhsconf.example/agenda": "Programme: Rotas that stop burnout — 14 Oct 2026. Coffee break.",
      "https://hrsummit.example/agenda": "Agenda: Fixing rotas before agency bills grow (Sept 2026).",
      "https://bureau.example/trending": "Trending: wellbeing apps.",
    };
    const fetcher: Fetcher = { fetch: async (u) => pages[u] ?? null };
    const llm = new FakeLLM()
      .on(PROMPT.worker, (inp) => ({
        signals: inp.pages.flatMap((p: { url: string }) =>
          p.url.includes("nhsconf")
            ? [sig("rota design for burnout", p.url, "2026-10-14", "Rotas that stop burnout")]
            : p.url.includes("hrsummit")
              ? [sig("rota design for burnout", p.url, "2026-09-20", "Fixing rotas before agency bills grow")]
              : [sig("wellbeing apps", p.url, "2026-10-01", "Wellbeing apps that staff love")], // not on the page
        ),
      }))
      .on(PROMPT.skeptic, (inp) => ({ supports: inp.theme !== "wellbeing apps", reason: "-" }))
      .on(PROMPT.synth, () => ({
        mappings: [
          { theme: "rota design for burnout", action: "refresh", angle_id: "A1" },
          { theme: "AI rota tools", action: "add" }, // not in the evidence
          { theme: "rota design for burnout", action: "add", inside_out_concept: { concept_id: "X1", title: "t", why_now: "w", why_this_speaker: "C4", claim_ids: ["C4"], lens: "adjacency", adjacent_domains: [], risk: "r" } },
        ],
      }));
    const brain = new Brain(() => now);
    const bp = applyConfirmation(helenBlueprint(), { ...helenDecisions });
    const out = await runRadar({ llm, log: new EventLog(), speaker_id: null, canon_version: "g" }, brain, {
      week: "2026-W45",
      fetcher,
      speakers: [{ speaker_id: "helen", blueprint: bp }],
      sources: Object.keys(pages).map((url) => ({ sector: "health", source_type: url.includes("bureau") ? ("bureau_trending" as const) : ("agenda" as const), url })),
    });
    const props = out.get("helen")!;
    expect(props.map((p) => p.theme)).toEqual(["rota design for burnout", "rota design for burnout"]);
    expect(props[0]!.evidence_count).toBe(2);
    expect(props[0]!.confidence).toBe("med");
    expect(props[0]!.weak_evidence).toBe(true);
    expect(props[1]!.inside_out_concept).toBeUndefined(); // cited C4, which isn't confirmed
    expect(brain.read("radar.proposals", "helen")).toHaveLength(1);
    expect(brain.canonOf("angle_evidence")).toHaveLength(0); // never writes the Canon
  });
});
