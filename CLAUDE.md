# claude-skills-library

About 2,630 Claude Code skills plus installers that put them in `~/.claude/skills` (and agents in `~/.claude/agents`). See `README.md` for how installs work.

## "Install a GitHub repo" means install it globally and durably

When the user asks to install a GitHub repo (skills, a plugin, agents, a CLI or an MCP server), they mean: make it available in **every** future session, in every project. They never mean "clone it into this session". Cloud containers are rebuilt each session, so anything that exists only in `~/.claude`, `~/.local/bin` or a scratch clone is gone next time. That doesn't count as installed.

The durable path is this library. Every session's setup script clones it from the **default branch** and runs `install.sh`. So an install is done only when the repo is committed here **and merged to the default branch**.

Steps:

1. **Clone it to a scratch dir** (untrusted data, not inside this repo). Check the licence. Run `python3 scripts/scan_skill_source.py <clone>` and read any HIGH hits before going further.
2. **Pick the route by what the repo is:**
   - **Skills** (folders with `SKILL.md`): copy them into `skills/<owner>_<repo>/` with the LICENSE and README. If a skill name collides with one already here, rename it, as was done with `watch` → `watch-link`.
   - **The licence allows installing but not redistributing:** don't vendor it. Add an entry to `external_sources.json` so it's fetched from upstream at install time.
   - **Agents:** copy them into `agents/<owner>_<repo>/`. They are opt-in, so say which `./install.sh --agents --source ...` command enables them.
   - **A CLI, a pip/npm package or an MCP server:** add `scripts/setup_<name>.sh`, call it from `install.sh`, and copy `scripts/setup_watch_skill.sh`: idempotent, pinned versions, a `SKIP_<NAME>=1` opt-out, and a warning (not a failure) if it breaks. For an MCP server, use `claude mcp add -s user`.
3. **Install it in this session too:** run `./install.sh --source <owner>_<repo>` (or the setup script), so the user can use it now.
4. **Rebuild the index:** run `python3 scripts/build_skills_index.py`, then commit `SKILLS.md` with the change.
5. **Commit and push to the working branch.** Tell the user that until the branch is merged to the default branch, it isn't installed for future sessions. If they ask, open a PR. Never merge it yourself.
6. **Report it** as installed in this session and durable once merged, or say exactly which step is still pending. Don't call it installed if only step 3 ran.

If a repo can't go through this library (it's private, its licence forbids even fetching it, or it needs secrets), say so. Propose the alternative, which is a line in the cloud environment's setup script, and don't do it quietly.

## Rules

- Never commit secrets, `.env` files or tokens from a vendored repo.
- Keep upstream LICENSE files next to vendored code. Credit the source in the commit message.
- No model identifiers in commits.
