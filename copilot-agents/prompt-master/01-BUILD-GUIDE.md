# Prompt Master for Microsoft 365 Copilot: build guide

A Copilot agent version of the open-source Claude skill **prompt-master** (MIT licence, by Nidhin Joseph Nelson). You give it a rough idea or a weak prompt. It gives back one ready-to-paste prompt tuned for the tool you'll use it in.

## What it does, in short

The original skill boils down to five things. All five are rebuilt here.

1. **Find the target tool first.** A prompt for Excel Copilot, ChatGPT and Midjourney each needs a different shape. It asks if the tool isn't clear.
2. **Pull out what's actually wanted** across 9 points: task, tool, format, constraints, input, context, audience, success criteria and examples. It asks at most 3 questions.
3. **Apply that tool's rules** (knowledge file K1).
4. **Fill the right template** (K2) and fix known failure patterns (K3).
5. **Return one copy-ready block** plus a one-line note on what it optimised. No lectures.

**What changed for Copilot:** the original is about 59,000 characters across three files. Copilot agent instructions are capped at **8,000 characters**. So:
- The core behaviour goes in the Instructions field (about 5,400 characters, leaving room for your additions).
- The reference material goes into three uploaded knowledge files.
- New material: Microsoft 365 Copilot targets (Chat, Word, Excel, PowerPoint, Outlook, Teams), Template P (grounded M365 request), Template Q (agent instructions), and patterns 38 to 41.
- Removed: model names that go out of date quickly. It uses model-family guidance instead.

## Files in this folder

| File | Where it goes |
|---|---|
| `02-INSTRUCTIONS.txt` | Paste into the **Instructions** field |
| `PM-K1 Tool Routing.txt` | Upload as knowledge |
| `PM-K2 Templates.txt` | Upload as knowledge |
| `PM-K3 Failure Patterns.txt` | Upload as knowledge |
| `LICENSE-prompt-master.txt` | Keep with the files. The MIT licence requires the copyright notice to travel with the material. |
| `03-TEST-SCRIPT.md` | Run these tests after building |

Don't rename the knowledge files. The instructions refer to them by name (`PM-K1`, `PM-K2`, `PM-K3`).

## Build it (Agent Builder in Microsoft 365 Copilot)

1. Open Microsoft 365 Copilot (m365copilot.com, or Copilot in Teams). In the left pane choose **Create agent** (it may be under *Agents → New agent*).
2. Switch to the **Configure** tab. Don't use Describe, because it would rewrite the instructions.
3. Fill in the fields:

| Field | Value |
|---|---|
| **Name** (30 characters max) | `Prompt Master` |
| **Description** | `Turns a rough idea or a weak prompt into one ready-to-paste prompt optimised for the tool you'll use it in: Microsoft 365 Copilot (Chat, Word, Excel, PowerPoint, Outlook, Teams), Copilot agents, ChatGPT, Claude, Gemini, GitHub Copilot, image and video tools. Fixes, adapts and splits existing prompts.` |
| **Instructions** | Paste the entire contents of `02-INSTRUCTIONS.txt` |

4. **Knowledge:** upload the three `PM-K…` files.
   - Leave **"Only use specified sources"** OFF. The agent also needs general knowledge to write prompts on any topic. The files tell it *how*, not *what*.
5. **Capabilities:**
   - **Web search: OFF** (recommended). Prompt writing doesn't need it. Leaving it off means none of the work details people paste in get sent out as web queries. Switch it on only if you want it to check new model names.
   - **Code interpreter: OFF.** **Image generator: OFF.** The agent writes prompts and never runs them.
6. **Starter prompts:**

| Title | Prompt |
|---|---|
| Build a prompt | `Write me a prompt for Copilot in Excel to flag overdue invoices in my sheet` |
| Fix my prompt | `Fix this prompt: [paste your prompt]` |
| Adapt for another tool | `Adapt this ChatGPT prompt for Microsoft 365 Copilot: [paste]` |
| Meeting / email prompt | `I need a prompt to get Copilot to summarise last week's project meetings into actions and owners` |
| Build an agent | `Write the instructions for a Copilot agent that answers our team's onboarding questions` |
| Break it down | `Explain what each part of this prompt does and what's missing: [paste]` |

7. Select **Create**. Test it using `03-TEST-SCRIPT.md` before sharing.
8. **Share:** *Share → Anyone in your organisation*, or specific people. Anyone you share with can read the knowledge files. These contain nothing confidential.

**Run it every time:** in Copilot Chat, type `@Prompt Master` followed by your idea, or pin the agent in the left pane.

## If Agent Builder isn't available, or you hit limits

- **No Agent Builder?** It needs Microsoft 365 Copilot access, and your IT admin may have disabled agent creation. Ask IT, or use **Copilot Studio** (which has the same instructions field and knowledge upload, plus topics and actions).
- **Want it to follow the templates more strictly?** Knowledge files are searched and retrieved in chunks; Copilot doesn't read them in full every time. If a template isn't being used, either (a) paste the 2 to 3 templates you use most directly into the instructions (you have about 2,500 characters spare), or (b) name the template in your request: "use Template P".
- **Copilot Studio upgrade path:** put each mode (Build / Fix / Adapt / Agent instructions) in its own topic for more reliable routing, and publish to Teams.

## Check with your company first

- Most organisations allow internal agents, but some require approval before sharing them widely. Check your AI policy.
- The agent writes prompts and stores nothing extra. However, whatever people paste in stays in their Copilot chat history under your tenant's normal retention rules.
- Keep `LICENSE-prompt-master.txt` with the files. The MIT licence allows commercial and internal use as long as the notice is kept.

## Keeping it up to date

The upstream skill changes often (it went from v1.6 to v1.8 in a month). It's in the shared skills library at `skills/nidhinjs_prompt-master/` (github.com/nigelguy007/claude-skills-library). To pull in changes later, ask Claude to "diff prompt-master upstream against the Copilot build and update the knowledge files". Then re-upload the changed files in Agent Builder (*Edit → Knowledge*).
