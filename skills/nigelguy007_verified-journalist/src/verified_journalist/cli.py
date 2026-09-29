"""Command-line entry point: `verified-journalist "topic" -o article.md --report report.json`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ARTICLE_STYLES, Settings
from .pipeline import InsufficientSourcesError, Journalist

EXIT_NEEDS_REVIEW = 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="verified-journalist",
        description="Research, write and fact-check an article on a topic.",
    )
    p.add_argument("topic", help="What the article should cover")
    p.add_argument("-o", "--out", type=Path, help="Write the Markdown article here")
    p.add_argument("--report", type=Path, help="Write the full JSON report here")
    p.add_argument("--style", choices=sorted(ARTICLE_STYLES), default="news")
    p.add_argument("--words", type=int, default=1200, help="Target length")
    p.add_argument("--max-sources", type=int, default=8)
    p.add_argument("--min-sources", type=int, default=3)
    p.add_argument("--recency-days", type=int, help="Prefer sources newer than this")
    p.add_argument("--revisions", type=int, default=2, help="Max fact-check/revise rounds")
    p.add_argument("--provider", choices=["anthropic", "openai"])
    p.add_argument("--no-cache", action="store_true")
    p.add_argument(
        "--strict",
        action="store_true",
        help=f"Exit {EXIT_NEEDS_REVIEW} if the article still needs human review",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = Settings(
            llm_provider=args.provider,
            style=args.style,
            target_words=args.words,
            max_sources=args.max_sources,
            min_sources=args.min_sources,
            recency_days=args.recency_days,
            max_revisions=args.revisions,
            use_cache=not args.no_cache,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if missing := settings.missing():
        print("error: missing " + " and ".join(missing), file=sys.stderr)
        return 2

    def progress(stage: str, detail: str) -> None:
        print(f"[{stage}] {detail}", file=sys.stderr)

    try:
        article = Journalist(settings).run(args.topic, on_progress=progress)
    except InsufficientSourcesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.out:
        args.out.write_text(article.markdown, "utf-8")
    else:
        print(article.markdown)
    if args.report:
        args.report.write_text(article.model_dump_json(indent=2), "utf-8")

    critical = [i for i in article.issues if i.severity == "critical"]
    warnings = [i for i in article.issues if i.severity == "warning"]
    print(
        f"\nstatus: {article.status} | {len(article.sources)} sources | "
        f"{len(critical)} critical, {len(warnings)} warnings | "
        f"{article.revisions} revision(s)",
        file=sys.stderr,
    )
    for issue in critical:
        print(f"  CRITICAL {issue.kind}: {issue.detail}", file=sys.stderr)
    print("usage: " + json.dumps(article.usage), file=sys.stderr)
    if args.strict and article.status != "ready":
        return EXIT_NEEDS_REVIEW
    return 0


if __name__ == "__main__":
    sys.exit(main())
