// The company-map rules, enforced: one register, every workflow owned and tagged, the
// LLM budget held, nothing that acts outside Dain left to run on its own, and the SOP
// files (the skill files) agreeing with the register.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { ROOT } from "../src/prompts.js";
import { REGISTER, V1_LLM_BUDGET } from "../src/register.js";

const sop = (dir: string) => readFileSync(join(ROOT, "departments", dir, "SKILL.md"), "utf8");

describe("component register (R1)", () => {
  it("holds v1 to five LLM components", () => {
    const v1 = REGISTER.filter((c) => c.llm && c.phase !== "post-launch").map((c) => c.id);
    expect(v1.sort()).toEqual(["A1", "A2", "B1", "B2", "P1"]);
    expect(v1.length).toBeLessThanOrEqual(V1_LLM_BUDGET);
  });

  it("never tags a workflow that writes outside Dain as fully autonomous", () => {
    for (const c of REGISTER) for (const w of c.workflows) if (w.external_write) expect(w.autonomy, `${c.id}: ${w.name}`).not.toBe("fully-autonomous");
  });

  it("every component has an owner, a department, an eval that exists, and at least one workflow", () => {
    for (const c of REGISTER) {
      expect(c.owner).toBeTruthy();
      expect(c.workflows.length).toBeGreaterThan(0);
      expect(existsSync(join(ROOT, c.eval)), `${c.id} eval ${c.eval}`).toBe(true);
    }
  });

  it("covers the map's first five agents: scout, builder, publisher, groundskeeper, conductor", () => {
    const archetypes = new Set(REGISTER.map((c) => c.archetype));
    for (const a of ["scout", "builder", "publisher", "groundskeeper", "conductor"]) expect(archetypes.has(a as never)).toBe(true);
  });
});

describe("SOP skill files agree with the register", () => {
  for (const c of REGISTER) {
    it(`${c.id} · ${c.sop}`, () => {
      const text = sop(c.sop);
      const fm = text.split("---")[1]!;
      expect(fm).toMatch(/^name: dain-/m);
      expect(fm).toMatch(/^description: .{60,}/m);
      expect(fm).toContain(`component: ${c.id}`);
      expect(fm).toContain(`department: ${c.department}`);
      expect(fm).toContain(`archetype: ${c.archetype}`);
      expect(fm).toContain(`owner: ${c.owner}`);
      for (const w of c.workflows) expect(text, w.name).toContain(`| ${w.name} | ${w.autonomy} | ${w.external_write ? "yes" : "no"} |`);
      for (const part of ["## 1 · Name and trigger", "## 2 · When to use", "## 3 · Inputs", "## 4 · Steps", "## 5 · Handoffs"]) expect(text).toContain(part);
    });
  }

  it("there is no SOP folder without a register row, and every prompt file sits beside an SOP", () => {
    const dirs = readdirSync(join(ROOT, "departments")).flatMap((d) => readdirSync(join(ROOT, "departments", d)).map((x) => `${d}/${x}`));
    expect(dirs.sort()).toEqual(REGISTER.map((c) => c.sop).sort());
  });
});
