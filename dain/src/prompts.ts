// Prompts live beside their SOP in departments/<dept>/<component>/*.prompt.md, so a
// prompt change is a reviewed, versioned file change, never an edit inside a workflow node.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const cache = new Map<string, string>();

export function loadPrompt(path: string): string {
  const hit = cache.get(path);
  if (hit) return hit;
  const text = readFileSync(join(ROOT, "departments", `${path}.prompt.md`), "utf8").trim();
  cache.set(path, text);
  return text;
}
