#!/usr/bin/env python3
"""Pre-vendor security scan for a third-party skill source.

Run this against a freshly cloned skill/plugin repo BEFORE copying it into
skills/ and committing — especially when the source arrived via an
unsolicited link (a cold DM, a random "install this" ask, a repo you've
never heard of). It does not replace reading the diff yourself; it just
flags the patterns worth reading first.

Two severities:
  HIGH   - code-execution / exfiltration primitives that have no business
           being in a skill's supporting scripts: eval/exec, shell=True,
           os.system, pickle/marshal deserialization, `curl|sh`-style
           remote-script execution, JS `new Function`/`child_process.exec`.
           A HIGH hit is not proof of malice, but it means "read this file
           before vendoring", so the scanner exits non-zero.
  INFO   - env-var access alongside a network call in the same file. Very
           common and usually fine (an API client reading its own key from
           .env and calling its own service) — this repo's own
           lib/*_client.py files trip it. Still worth a glance to confirm
           the destination is the service the skill claims to talk to, not
           something else. Never fails the scan by itself.

Usage:
    python3 scripts/scan_skill_source.py <path-to-cloned-repo> [more-paths...]

Exit status: 0 if no HIGH findings, 1 if any HIGH finding was reported.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterator, NamedTuple

SCAN_EXTENSIONS = {
    ".py", ".sh", ".bash", ".js", ".ts", ".mjs", ".cjs", ".rb", ".pl", ".ps1",
}

# Directories never worth descending into.
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}

HIGH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("eval(", re.compile(r"\beval\s*\(")),
    # Negative lookbehind excludes JS/Python `.exec(` (RegExp/subprocess-result
    # method calls) — extremely common and benign — while still catching the
    # bare Python builtin `exec(...)`.
    ("exec(", re.compile(r"(?<!\.)\bexec\s*\(")),
    ("os.system(", re.compile(r"\bos\.system\s*\(")),
    ("subprocess shell=True", re.compile(r"shell\s*=\s*True")),
    ("pickle.loads(", re.compile(r"\bpickle\.loads?\s*\(")),
    ("marshal.loads(", re.compile(r"\bmarshal\.loads?\s*\(")),
    ("__import__(", re.compile(r"__import__\s*\(")),
    ("remote-script pipe (curl|sh)", re.compile(r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(sh|bash|zsh)\b")),
    ("PowerShell download-and-invoke", re.compile(r"Invoke-Expression|IEX\s*\(|iwr\s")),
    ("JS new Function(", re.compile(r"new\s+Function\s*\(")),
    ("JS child_process.exec(", re.compile(r"child_process\.\s*exec(File)?\s*\(")),
]

ENV_ACCESS = re.compile(r"os\.environ|os\.getenv|process\.env|ENV\[")
NETWORK_CALL = re.compile(
    r"\brequests\.(get|post|put|patch|delete)\s*\("
    r"|[_.]session\.(get|post|put|patch|delete)\s*\("
    r"|urlopen\s*\(|fetch\s*\(|axios\.|httpx\.|urllib\.request"
)


class Finding(NamedTuple):
    severity: str
    file: Path
    line: int
    label: str
    text: str


def iter_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in SCAN_EXTENSIONS:
            yield path


def scan_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: list[Finding] = []
    lines = text.splitlines()

    for label, pattern in HIGH_PATTERNS:
        for i, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(Finding("HIGH", path, i, label, line.strip()))

    if ENV_ACCESS.search(text) and NETWORK_CALL.search(text):
        # File-level, not line-level: report once against the first env-access line.
        for i, line in enumerate(lines, start=1):
            if ENV_ACCESS.search(line):
                findings.append(
                    Finding("INFO", path, i, "env var read + network call in same file", line.strip())
                )
                break

    return findings


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    all_findings: list[Finding] = []
    for arg in argv:
        root = Path(arg)
        if not root.exists():
            print(f"error: no such path: {root}", file=sys.stderr)
            return 2
        for f in iter_files(root):
            all_findings.extend(scan_file(f))

    high = [f for f in all_findings if f.severity == "HIGH"]
    info = [f for f in all_findings if f.severity == "INFO"]

    if not all_findings:
        print("clean: no HIGH or INFO patterns found.")
        return 0

    if high:
        print(f"=== {len(high)} HIGH finding(s) — read these before vendoring ===")
        for f in high:
            print(f"  [{f.label}] {f.file}:{f.line}: {f.text}")
        print()

    if info:
        print(f"=== {len(info)} INFO finding(s) — likely-fine API-client pattern, spot-check the destination ===")
        for f in info:
            print(f"  [{f.label}] {f.file}:{f.line}: {f.text}")
        print()

    return 1 if high else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
