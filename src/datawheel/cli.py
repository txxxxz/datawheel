"""Command-line entry point; adapter failures remain visible to the caller."""

import argparse
from pathlib import Path

from .pipeline import DEFAULT_ADAPTER, run


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an inspectable local data feedback loop.")
    commands = parser.add_subparsers(dest="command", required=True)
    runner = commands.add_parser("run", help="Import, clean, synthesize, select, and feed back")
    runner.add_argument("--input", required=True, type=Path)
    runner.add_argument("--output", required=True, type=Path)
    runner.add_argument("--adapter", default=DEFAULT_ADAPTER)
    runner.add_argument("--rounds", type=int, default=2, help="Total desired rounds, including committed rounds")
    runner.add_argument("--budget", type=int, default=12)
    runner.add_argument("--keep", type=int, default=8)
    runner.add_argument("--seed", type=int, default=7)
    runner.add_argument("--min-score", type=float, default=1.0)
    runner.add_argument("--resume", action="store_true")
    reporter = commands.add_parser("report", help="Print the saved quality report")
    reporter.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "report":
        print((args.output / "report.md").read_text(encoding="utf-8"), end="")
        return
    summary = run(args.input, args.output, rounds=args.rounds, budget=args.budget, keep=args.keep,
                  seed=args.seed, min_score=args.min_score, adapter_spec=args.adapter, resume=args.resume)
    print(f"{summary['mode']}: exported {summary['exported_records']} records; report: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()
