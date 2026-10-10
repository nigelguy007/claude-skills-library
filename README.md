# claude-skills-library

About 2,630 [Claude Code](https://claude.com/claude-code) skills collected from open-source repositories, plus a one-command installer that puts them all in `~/.claude/skills` so every project can use them.

- Skills live under [`skills/`](skills/), namespaced by origin as `skills/<owner>_<repo>/...`.
- [`SKILLS.md`](SKILLS.md) lists every skill, its source repository and what triggers it.

## Install

On any machine with `git` and `python3`:

```bash
curl -fsSL https://raw.githubusercontent.com/nigelguy007/claude-skills-library/HEAD/bootstrap.sh | bash
```

Or clone first:

```bash
git clone https://github.com/nigelguy007/claude-skills-library.git
cd claude-skills-library && ./bootstrap.sh
```

Restart Claude Code afterwards. Run the same command again to update.

- Skills already in `~/.claude/skills` are never overwritten. Name collisions are installed as `<owner>_<repo>_<name>`.
- To install a single collection: `./install.sh --source <owner>_<repo>`.
- To search what's installed: `./find-skill.sh <keyword>`.
- Collections with a router `SKILL.md` at their root (gstack, avoid-ai-writing, linkedin-skills) also get the skills nested under it installed. If a skill with that name is already there from another install, such as gstack's own setup, that copy is kept.
- After adding or removing skills, run `python3 scripts/build_skills_index.py` to rebuild `SKILLS.md` from what's on disk.

## Claude Code on the web (cloud sessions)

Add this to your cloud environment's **Setup script** (environment menu in the session title bar → Edit), so every new session in every repo gets the skills:

```bash
# --- claude-skills-library: install all skills into ~/.claude/skills ---
git clone --depth 1 https://github.com/nigelguy007/claude-skills-library.git ~/claude-skills-library \
  && bash ~/claude-skills-library/install.sh || true
(pip install --quiet scrapling scrapegraphai agent-reach geo-optimizer-skill >/tmp/skill-tools-install.log 2>&1 &) || true
```

The `pip` line installs the command-line tools that some skills (Scrapling, Agent-Reach, GEO Optimizer) call. It runs in the background.

## Subagents

[`agents/`](agents/) holds Claude Code subagents, namespaced the same way as `agents/<owner>_<repo>/<division>/<agent>.md`. Currently that's the 282 agents from [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) (MIT), in 18 divisions: engineering, design, marketing, sales, testing and so on.

They are **not** installed by default. Every installed agent's description goes into every Claude Code session, so 282 of them cost context and make Claude pick the wrong one more often. Install only the divisions you use:

```bash
./install.sh --agents --division engineering --division testing   # into ~/.claude/agents
./install.sh --agents                                              # all of them
```

- Agents already in `~/.claude/agents` are never overwritten. An agent whose file name or `name:` is already taken is skipped and listed.
- Re-running replaces the previous agent install. A `--division` run replaces it with just those divisions.
- For cloud sessions, add `bash ~/claude-skills-library/install.sh --agents --division <name> || true` to the setup script after the skills line. Agents load when a session starts.

## claude.ai chat and the Desktop chat app

Chat can't read `~/.claude/skills`. Skills there are uploaded as zips in claude.ai → Settings → Capabilities → Skills. Build upload-ready zips with:

```bash
python3 scripts/package_for_claude_ai.py make-plan geo-optimizer free-llm-apis
```

Pick the few you actually use in chat. Uploading thousands isn't practical, and overlapping skills make Claude pick the wrong one more often.

## Licensing

Every skill belongs to its original authors and keeps their licence. Each collection's source is linked in [`SKILLS.md`](SKILLS.md), and newer collections record the exact upstream commit in `.vendor-info.json`. Check a collection's upstream licence before reusing it. If you're an author and want your work removed, open an issue.

## Security

Skills run as code, since Claude loads `SKILL.md` and may execute the scripts beside it. New sources are scanned with `scripts/scan_skill_source.py` before they're added, but review anything you plan to rely on.
