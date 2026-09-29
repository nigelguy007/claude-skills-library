#!/usr/bin/env python3
"""Install collected Claude skills into the global skills directory.

Each skill in this repo lives under ``skills/<owner>_<repo>/.../<skill>/SKILL.md``.
This script flattens every top-level skill (a directory whose ``SKILL.md`` has no
``SKILL.md`` ancestor) into ``~/.claude/skills/<name>/`` so Claude Code discovers
them globally, in every project.

Behaviour:
  * Existing skills already in the target directory are preserved (never clobbered).
  * When a skill name collides with something already present, or with another
    skill from the collection, it is namespaced as ``<owner>_<repo>_<name>``
    (with a numeric suffix as a last resort) so nothing is lost.
  * The install is idempotent: a sidecar manifest records what this script wrote,
    and re-running removes the previous install first, then rebuilds cleanly.

Pass ``--source <owner>_<repo>`` (repeatable) to install only the skills from
one or more source collections instead of the whole library, e.g.:

    python3 install_global_skills.py --source emilkowalski_skills

This installs just that collection's skills globally, so any project (this
repo or another one entirely) can use them without pulling in everything else.

Override the destination with the ``CLAUDE_SKILLS_DIR`` environment variable
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
SRC_ROOT = REPO_ROOT / "skills"
DEST_ROOT = Path(
    os.environ.get("CLAUDE_SKILLS_DIR", str(Path.home() / ".claude" / "skills"))
)
# Sidecar manifest tracking the skills THIS installer created (for idempotency).
INSTALL_MANIFEST = DEST_ROOT / ".collection-install.json"


def find_top_level_skills(src_root: Path) -> List[Path]:
    """Return skill directories: those containing SKILL.md with no SKILL.md ancestor."""
    skill_dirs = {p.parent for p in src_root.rglob("SKILL.md")}
    top: List[Path] = []
    for d in skill_dirs:
        anc = d.parent
        is_top = True
        while src_root in anc.parents or anc == src_root:
            if anc == src_root:
                break
            if anc in skill_dirs:
                is_top = False
                break
            anc = anc.parent
        if is_top:
            top.append(d)
    return sorted(top)


def find_router_children(src_root: Path, top: List[Path]) -> List[Path]:
    """Skills nested under a collection-root SKILL.md.

    Some sources (gstack, avoid-ai-writing, linkedin-skills) put a router
    SKILL.md at the repo root with the real skills below it. Only the root
    would be installed otherwise, so those nested skills (the top-most ones
    beneath the root, skipping plugin copies of the root skill itself) are
    installed too. Nesting deeper inside an ordinary skill (translations,
    per-platform variants, fixtures) is left alone.
    """
    roots = [d for d in top if d.parent == src_root]
    children: List[Path] = []
    for root in roots:
        nested = {p.parent for p in root.rglob("SKILL.md")} - {root}
        for d in nested:
            anc = d.parent
            while anc != root and anc not in nested:
                anc = anc.parent
            if anc == root and skill_name(d) != skill_name(root):
                children.append(d)
    return sorted(children)


def skill_name(skill_dir: Path) -> str:
    """The ``name:`` from SKILL.md front-matter, falling back to the dir name."""
    try:
        head = (skill_dir / "SKILL.md").read_text(errors="ignore")[:2000]
    except OSError:
        return skill_dir.name
    m = re.search(r"^name:\s*['\"]?([^'\"\n]+)", head, re.M)
    return m.group(1).strip() if m else skill_dir.name


def owner_repo(skill_dir: Path) -> str:
    """First path component under skills/, e.g. 'coreyhaines31_marketingskills'."""
    return skill_dir.relative_to(SRC_ROOT).parts[0]


def load_previous_install() -> dict:
    """Returns ``{name: owner_repo}`` for everything a prior run of this
    installer wrote. ``owner_repo`` is ``None`` for entries from an older
    manifest format (a flat name list) that predates per-source tracking —
    treated as unscoped so a scoped re-run never removes them by mistake.
    """
    if INSTALL_MANIFEST.exists():
        try:
            installed = json.loads(INSTALL_MANIFEST.read_text()).get("installed", [])
            if isinstance(installed, list):
                return {name: None for name in installed}
            return installed
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
        help=(
            "Only install skills from this source collection "
            "(the skills/<owner>_<repo> directory name, e.g. 'emilkowalski_skills'). "
            "Repeatable. Omit to install every collected skill."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not SRC_ROOT.is_dir():
        print(f"error: source skills dir not found: {SRC_ROOT}", file=sys.stderr)
        return 1

    DEST_ROOT.mkdir(parents=True, exist_ok=True)

    wanted = set(args.source) if args.source else None
    previous = load_previous_install()

    # Idempotency: remove skills a previous run of THIS installer created.
    # A scoped (--source) run only touches entries within its own scope, so
    # it never deletes skills a prior full (or differently-scoped) run put in
    # place; an unscoped run rebuilds everything, matching prior behaviour.
    kept: dict = {}
    for name, src in previous.items():
        if wanted is not None and src not in wanted:
            kept[name] = src
            continue
        target = DEST_ROOT / name
        if target.is_dir():
            shutil.rmtree(target)

    top = find_top_level_skills(SRC_ROOT)
    children = set(find_router_children(SRC_ROOT, top))
    top = sorted(set(top) | children)

    if wanted is not None:
        top = [d for d in top if owner_repo(d) in wanted]
        missing = wanted - {owner_repo(d) for d in top}
        for name in missing:
            print(f"warning: no skills found for source '{name}'", file=sys.stderr)

    # Names currently occupied by anything we must not touch (managed/other skills).
    used = {p.name for p in DEST_ROOT.iterdir() if p.is_dir()}

    installed: dict = {}
    namespaced = 0
    duplicates = 0
    for skill_dir in top:
        base = skill_dir.name
        name = base
        if skill_dir in children and name in used and name not in installed:
            # A router's sub-skill whose name is already taken by something this
            # installer didn't write is that same skill installed another way
            # (e.g. gstack's own setup, often a newer version). Keep that one.
            duplicates += 1
            continue
        if name in used:
            name = f"{owner_repo(skill_dir)}_{base}"
            namespaced += 1
            suffix = 2
            while name in used:
                name = f"{owner_repo(skill_dir)}_{base}_{suffix}"
                suffix += 1
        used.add(name)
        target = DEST_ROOT / name
        shutil.copytree(skill_dir, target)
        installed[name] = owner_repo(skill_dir)

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

    print(f"Installed {len(installed)} skills into {DEST_ROOT}")
    print(f"  {namespaced} namespaced by source repo to avoid name collisions")
    if duplicates:
        print(f"  {duplicates} skipped: already installed by other means")
    if wanted is not None:
        print(f"  scope: {', '.join(sorted(wanted))}")
    print(f"  manifest: {INSTALL_MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
