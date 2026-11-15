# nexu-io/open-design skills

The 169 functional skills from [nexu-io/open-design](https://github.com/nexu-io/open-design)
(`skills/` at commit `59e4f2ae85de7e7318a5e6bdcf3a34584c4b7582`, 2026-11-13). Apache-2.0
unless a skill carries its own `LICENSE`.

Only the skills are vendored. The OpenDesign app, its `od` daemon and MCP server,
`design-systems/` and `design-templates/` are not: `od` is not published to npm and
needs a from-source build (Node 24, pnpm) plus a running local daemon. Four skills
(the ones reading `OD_BIN` / `OD_PROJECT_ID`) only work inside that app.

Install just this collection: `./install.sh --source nexu-io_open-design`.
