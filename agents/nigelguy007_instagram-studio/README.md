# instagram-studio

One subagent, `instagram-manager`, that runs an Instagram account using the 13
`ig-*` skills in `skills/nigelguy007_instagramskills` (mirror of
`Jakeschincariol/instagram-agent-skill`, MIT).

It routes each request to the right skill (`ig-viral`, `ig-plan`, `ig-reel`,
`ig-caption`, `ig-carousel`, `ig-story`, `ig-profile`, `ig-comment`,
`ig-reply`, `ig-dm`, `ig-repurpose`, `ig-audit`), chains them for multi-part
asks, and passes every draft through `ig-human` before showing it. State lives
in `~/.claude/instagram/` (`voice.md`, `plan.md`, `swipe.md`, `log.md`).

It never posts, schedules or sends anything.

Install (the skills must be installed too):

```bash
./install.sh --source nigelguy007_instagramskills
./install.sh --agents --source nigelguy007_instagram-studio
```

Then ask Claude Code to "use the instagram-manager agent to plan my week".
