#!/usr/bin/env python3
"""Install collected Claude Code subagents into the global agents directory.

Agents live under ``agents/<owner>_<repo>/<division>/.../<agent>.md``. An agent
file is a Markdown file whose YAML front-matter has a ``name:`` key; other
Markdown (READMEs, playbooks) is ignored. Each agent is copied flat into
``~/.claude/agents/<file>.md`` so Claude Code discovers it in every project.

Behaviour:
  * Agents already in the target directory are preserved (never clobbered).
    Claude Code identifies an agent by its front-matter ``name``, so an agent
    whose file name or ``name`` is already taken by something this installer
    didn't write is skipped rather than renamed.
  * The install is idempotent: a sidecar manifest records what this script
    wrote, and re-running removes the previous install first, then rebuilds.

Narrow what gets installed with ``--source <owner>_<repo>`` and/or
``--division <name>`` (both repeatable), e.g.:

    python3 install_global_agents.py --division engineering --division testing

Every agent's description is loaded into each Claude Code session, so
installing only the divisions you use keeps sessions lean.

Override the destination with the ``CLAUDE_AGENTS_DIR`` environment variable
(useful for testing).
"""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "agents"
DEST_ROOT = Path(
    os.environ.get("CLAUDE_AGENTS_DIR", str(Path.home() / ".claude" / "agents"))
)
# Sidecar manifest tracking the agents THIS installer created (for idempotency).
INSTALL_MANIFEST = DEST_ROOT / ".collection-install.json"

FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)


def agent_name(path: Path) -> Optional[str]:
    """The front-matter ``name:``, or None if the file isn't an agent."""
    try:
        head = path.read_text(errors="ignore")[:4000]
    except OSError:
        return None
    m = FRONT_MATTER.match(head)
    if not m:
        return None
    n = re.search(r"^name:\s*['\"]?([^'\"\n]+)", m.group(1), re.M)
    return n.group(1).strip() if n else None


def owner_repo(path: Path) -> str:
    return path.relative_to(SRC_ROOT).parts[0]


def division(path: Path) -> str:
    parts = path.relative_to(SRC_ROOT).parts
    return parts[1] if len(parts) > 2 else ""


def find_agents(src_root: Path) -> List[Path]:
    return sorted(p for p in src_root.rglob("*.md") if agent_name(p))


def load_previous_install() -> dict:
    """Returns ``{file_name: owner_repo}`` for everything a prior run wrote."""
    if INSTALL_MANIFEST.exists():
        try:
            return json.loads(INSTALL_MANIFEST.read_text()).get("installed", {})
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        metavar="OWNER_REPO",
        help="Only install agents from this collection (agents/<owner>_<repo>). Repeatable.",
    )
    parser.add_argument(
        "--division",
        action="append",
        default=None,
        metavar="NAME",
        help="Only install agents from this division, e.g. 'engineering'. Repeatable.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not SRC_ROOT.is_dir():
        print(f"error: source agents dir not found: {SRC_ROOT}", file=sys.stderr)
        return 1

    DEST_ROOT.mkdir(parents=True, exist_ok=True)

    sources = set(args.source) if args.source else None
    divisions = set(args.division) if args.division else None
    scoped = sources is not None or divisions is not None
    previous = load_previous_install()

    # Idempotency: remove what a previous run of THIS installer created. A
    # scoped run only removes entries from its own sources; an unscoped run
    # rebuilds everything. (Division isn't recorded, so a --division run
    # clears and rebuilds that whole source.)
    kept: dict = {}
    for name, src in previous.items():
        if sources is not None and src not in sources:
            kept[name] = src
            continue
        (DEST_ROOT / name).unlink(missing_ok=True)

    agents = find_agents(SRC_ROOT)
    if sources is not None:
        agents = [a for a in agents if owner_repo(a) in sources]
        for name in sources - {owner_repo(a) for a in agents}:
            print(f"warning: no agents found for source '{name}'", file=sys.stderr)
    if divisions is not None:
        agents = [a for a in agents if division(a) in divisions]
        for name in divisions - {division(a) for a in agents}:
            print(f"warning: no agents found for division '{name}'", file=sys.stderr)

    # Files and agent names already present that this installer must not touch.
    existing = [p for p in DEST_ROOT.glob("*.md") if p.name not in kept]
    used_files = {p.name for p in DEST_ROOT.glob("*.md")}
    used_names = {n for n in (agent_name(p) for p in existing) if n}
    used_names |= {agent_name(DEST_ROOT / f) for f in kept if (DEST_ROOT / f).exists()}

    installed: dict = {}
    skipped: List[str] = []
    for path in agents:
        name = agent_name(path)
        if path.name in used_files or name in used_names:
            skipped.append(f"{path.name} ({name})")
            continue
        shutil.copy2(path, DEST_ROOT / path.name)
        used_files.add(path.name)
        used_names.add(name)
        installed[path.name] = owner_repo(path)

    manifest_installed = {**kept, **installed}
    INSTALL_MANIFEST.write_text(
        json.dumps(
            {
                "source": str(SRC_ROOT),
                "count": len(manifest_installed),
                "installed": dict(sorted(manifest_installed.items())),
            },
            indent=2,
        )
    )

    print(f"Installed {len(installed)} agents into {DEST_ROOT}")
    if skipped:
        print(f"  {len(skipped)} skipped: file or agent name already taken")
        for s in skipped:
            print(f"    - {s}")
    if scoped:
        scope = sorted(sources or []) + sorted(divisions or [])
        print(f"  scope: {', '.join(scope)}")
    print(f"  manifest: {INSTALL_MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
