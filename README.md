# claude-skills-library

About 2,630 [Claude Code](https://claude.com/claude-code) skills collected from open-source repositories, plus a one-command installer that puts them all in `~/.claude/skills` so every project can use them.licensed and copyrighted  by Juliemango.ai

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
- Sources listed in [`external_sources.json`](external_sources.json) (currently [transitions.dev](https://github.com/Jakubantalik/transitions.dev)) are cloned from upstream each time you install. Their licences don't allow redistributing them, so they aren't committed here.
- The official design sources (impeccable, make-interfaces-feel-better, GSAP, transitions.dev) are installed first and keep the bare skill names. Third-party copies of the same skills are namespaced.
- After adding or removing skills, run `python3 scripts/build_skills_index.py` to rebuild `SKILLS.md` from what's on disk.

## Claude Code on the web (cloud sessions)

Add this to your cloud environment's **Setup script** (environment menu in the session title bar → Edit), so every new session in every repo gets the skills:

```bash
# --- claude-skills-library: install all skills into ~/.claude/skills ---
git clone --depth 1 https://github.com/nigelguy007/claude-skills-library.git ~/claude-skills-library \
  && bash ~/claude-skills-library/install.sh || true
(pip install --quiet scrapling scrapegraphai geo-optimizer-skill >/tmp/skill-tools-install.log 2>&1 &) || true
```

The `pip` line installs the command-line tools that some skills (Scrapling, GEO Optimizer) call. It runs in the background.

`install.sh` also runs [`scripts/setup_agent_reach.sh`](scripts/setup_agent_reach.sh), which installs the [Agent Reach](https://github.com/Panniantong/Agent-Reach) CLI (pinned to v1.6.0) from its GitHub release with `uv` and runs `agent-reach setup`. **Do not `pip install agent-reach`**: the PyPI package with that name is a different project, and the script removes it if it finds it. Set `SKIP_AGENT_REACH=1` to opt out, or `AGENT_REACH_VERSION` to pin another release.

YouTube blocks cloud IPs unless you're signed in. To read YouTube from cloud sessions, export a `cookies.txt` from a browser signed in to a throwaway YouTube account, base64-encode it (`base64 -w0 cookies.txt`), and save it as the environment variable `AGENT_REACH_YT_COOKIES_B64` in your cloud environment. The script passes it to yt-dlp. Never commit the cookies file: it's a login.

`install.sh` also runs [`scripts/setup_claude_flow.sh`](scripts/setup_claude_flow.sh), which does `npm install -g claude-flow@3.38.20` and `claude mcp add -s user claude-flow -- npx claude-flow@3.38.20 mcp start`. Any setup script that runs `install.sh` therefore gets claude-flow too, so you don't need to add those lines yourself. Cloud containers are rebuilt for every session and the setup script runs each time, so the install happens again in each new session. The first install takes about a minute. Re-runs skip the npm step. Set `SKIP_CLAUDE_FLOW=1` to opt out, or `CLAUDE_FLOW_VERSION` to pin a different version.

## Subagents

[`agents/`](agents/) holds Claude Code subagents, namespaced the same way as `agents/<owner>_<repo>/<division>/<agent>.md`. Currently that's the 282 agents from [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) (MIT), in 18 divisions: engineering, design, marketing, sales, testing and so on.

[`agents/nigelguy007_book-studio/`](agents/nigelguy007_book-studio/) adds 8 book-writing agents (idea → outline → chapters → edits → KDP launch), run by the `/write-book` skill. Install them with `./install.sh --agents --source nigelguy007_book-studio`.

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
