"""Entry point: orchestrate run --requirements path/to/req.md"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .backends import BackendError, build_backend
from .logging_utils import RunLogger
from .loop import run_loop


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="orchestrate", description="Multi-agent orchestration tool")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run an Architect/Reviewer convergence loop")
    run_p.add_argument("--requirements", required=True, type=Path, help="Path to a requirements file")
    run_p.add_argument("--architect", default="claude", choices=["claude", "cursor"])
    run_p.add_argument("--reviewer", default="claude", choices=["claude", "cursor"])
    run_p.add_argument("--architect-model", default=None, help="Optional model override for the Architect backend")
    run_p.add_argument("--reviewer-model", default=None, help="Optional model override for the Reviewer backend")
    run_p.add_argument("--workspace", default=Path("."), type=Path, help="cwd for the CLI subprocesses")
    run_p.add_argument("--max-iterations", default=6, type=int, help="Max Reviewer/Architect round trips before forced resolution")
    run_p.add_argument("--runs-dir", default=Path("runs"), type=Path, help="Where per-run transcripts are written")

    args = parser.parse_args(argv)

    if args.command == "run":
        return _run(args)
    return 1


def _run(args: argparse.Namespace) -> int:
    if args.architect == args.reviewer and args.architect_model == args.reviewer_model:
        print(
            "Warning: Architect and Reviewer are the same backend+model. The loop still works "
            "(useful for testing the mechanics) but you get no real model diversity in the review.",
            file=sys.stderr,
        )

    if not args.requirements.exists():
        print(f"Requirements file not found: {args.requirements}", file=sys.stderr)
        return 1
    requirements = args.requirements.read_text()

    try:
        architect = build_backend(args.architect, args.architect_model)
        reviewer = build_backend(args.reviewer, args.reviewer_model)
    except BackendError as exc:
        print(f"Backend setup failed: {exc}", file=sys.stderr)
        return 1

    args.workspace.mkdir(parents=True, exist_ok=True)
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    logger = RunLogger(args.runs_dir)

    try:
        result = run_loop(
            requirements=requirements,
            architect=architect,
            reviewer=reviewer,
            workspace=args.workspace,
            max_iterations=args.max_iterations,
            logger=logger,
        )
    except BackendError as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1

    logger.finalize(result.outcome, result.plan, result.rounds_used, result.final_review)
    print(f"\nDone. Outcome: {result.outcome}. Transcript: {logger.run_dir}")
    return 0 if result.outcome == "AGREED" else 2


if __name__ == "__main__":
    sys.exit(main())
