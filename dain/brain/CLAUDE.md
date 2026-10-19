# Dain brain

Open this folder as an Obsidian vault. It is the human side of Dain's one shared brain: what Dain is, what lives where, and how the team works. The machine side (Canon and Chronicle records) lives in the database (`../db/schema.sql`). If it isn't in one of the two, it didn't happen.

## Who we are
Project Dain is a speaker growth platform built by Propela × The Disruptive AI Enabler for established, non-exclusive professional speakers (pilot segment: £5k–£15k keynote, 10+ paid talks a year, at least one bureau, wants more bookings). Three promises: speakers say clearly what makes them different, post without spending hours, and never lose an enquiry.

## What lives where
| Thing | Where | Who changes it |
|---|---|---|
| Org chart (departments, components, owners, autonomy tags) | `../src/register.ts`, explained in [[00-company-map]] | technical lead, by PR |
| SOP + skill file per component | `../departments/<dept>/<component>/SKILL.md` | component owner, by PR |
| Runtime prompts | `../departments/<dept>/<component>/*.prompt.md` | component owner, by PR, with tests |
| Approved facts (Blueprints, claims, rubric, evidence, bureau profiles, policies) | Canon table; seed copies in `canon/` | a named human only |
| Raw material (transcripts, drafts, signals, model outputs) | Chronicle table | agents (append-only) |
| Booker evidence programme (R2) | `evidence/` | product lead |
| Open client decisions | `decisions/open-decisions.md` | product lead |

## How we work
1. **One brain, everyone reads it.** Agents read facts from the Canon, never from their own recall.
2. **Every workflow has an owner and a tag.** Human-led, human-assisted or fully autonomous. Nothing that publishes, sends or shares in a speaker's name is ever fully autonomous.
3. **The system writes back.** Every job's output is the next job's input: published posts become voice samples, review edits become rubric evidence, enquiries become demand signal.
4. **Check before trust.** Every LLM output has a check that something other than its author runs, and a stop rule (3 tries, then a person).
5. **Five LLM components in v1** (A1, A2, B2, P1, B1). A new one needs to pass R1's three tests: judgement, a fallible check, a distinct output.

## The speakers in this vault
Worked examples use "Helen Marsh", a fictional former NHS operations director. She is not a real person.
