"""Offline checker, bounded source audit and module catalog CLI."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from itertools import islice
from pathlib import Path

from . import __version__
from .catalog import MODULES
from .data import DATASET, GRADING_VERSION, REVISION, examples
from .worker import Grader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("catalog")
    check = subcommands.add_parser("grade")
    check.add_argument("--module", required=True, choices=MODULES)
    check.add_argument("--question", required=True)
    check.add_argument("--reference", required=True)
    check.add_argument("--answer", required=True)
    check.add_argument("--timeout", type=float, default=3)
    audit = subcommands.add_parser("self-check")
    audit.add_argument("--source")
    audit.add_argument("--language", choices=("en", "ru"), default="ru")
    audit.add_argument(
        "--mode", choices=("train", "interpolate", "extrapolate", "all"), default="interpolate"
    )
    audit.add_argument("--module", action="append", dest="modules", choices=MODULES, default=[])
    audit.add_argument("--revision", default=REVISION)
    audit.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum checked rows; 0 explicitly means the entire selected source",
    )
    audit.add_argument("--require-all-modules", action="store_true")
    audit.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "catalog":
        print(
            json.dumps(
                {"version": __version__, "grading_version": GRADING_VERSION, "modules": MODULES},
                indent=2,
            )
        )
        return
    if args.command == "grade":
        with Grader(args.timeout) as grader:
            result = grader.grade(args.module, args.question, args.reference, args.answer)
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        if result.status == "invalid_reference":
            sys.exit(2)
        return
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    counts, kinds, statuses = Counter(), Counter(), Counter()
    errors = []
    modes = ("train", "interpolate", "extrapolate") if args.mode == "all" else (args.mode,)

    def selected():
        for mode in modes:
            yield from examples(
                source=args.source,
                language=args.language,
                mode=mode,
                modules=args.modules,
                revision=args.revision,
            )

    rows = islice(selected(), args.limit) if args.limit else selected()
    with Grader() as grader:
        for example in rows:
            result = grader.grade(example.module, example.question, example.answer, example.answer)
            counts[example.module] += 1
            kinds[result.kind] += 1
            statuses[result.status] += 1
            if result.reward != 1 and len(errors) < 100:
                errors.append(
                    {
                        "id": example.id,
                        "module": example.module,
                        "question": example.question,
                        "reference": example.answer,
                        "result": result.to_dict(),
                    }
                )
    missing = sorted(set(MODULES) - counts.keys())
    report = {
        "package_version": __version__,
        "grading_version": GRADING_VERSION,
        "dataset": DATASET if not args.source else "local",
        "dataset_revision": args.revision if not args.source else None,
        "language": args.language,
        "mode": args.mode,
        "source": args.source,
        "source_sha256": hashlib.sha256(Path(args.source).read_bytes()).hexdigest()
        if args.source
        else None,
        "checked": sum(counts.values()),
        "coverage": dict(sorted(counts.items())),
        "kinds": dict(kinds),
        "statuses": dict(statuses),
        "missing_modules": missing,
        "errors": errors,
        "evidence": (
            "reference acceptance only; not independent mathematical validation or RL training"
        ),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {k: report[k] for k in ("checked", "statuses", "kinds", "missing_modules")},
            ensure_ascii=False,
            indent=2,
        )
    )
    if (
        not counts
        or any(status != "correct" for status in statuses)
        or (args.require_all_modules and missing)
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
