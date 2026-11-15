"""The command line: load the set, run, print, compare with the last report, save on request."""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from app.domain import Clock
from app.llm import Llm
from evaluation._data import InvalidSet, load_set
from evaluation._report import Report, render
from evaluation._run import run_evaluation

DATA = Path("evaluation/data")
LAST_REPORT = Path("evaluation/reports/last.json")
# Builds what a run needs: the Llm, a Clock and the names of the models for the report. Called after the
# set is checked, so a bad set costs nothing.
LlmFactory = Callable[[], tuple[Llm, Clock, str]]


def main(argv: Sequence[str], *, llm: LlmFactory) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation", description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA / "reviews.jsonl")
    parser.add_argument("--taxonomy", type=Path, default=DATA / "taxonomy.json")
    parser.add_argument("--last", type=Path, default=LAST_REPORT)
    parser.add_argument("--save", action="store_true", help="store this report as the new last one")
    args = parser.parse_args(argv)
    for path in (args.data, args.taxonomy):
        if not path.exists():
            print(
                f"{path} is missing. The hand-labelled, anonymized set is made by the owner: "
                "see evaluation/README.md (use --data/--taxonomy with the sample files to try the command).",
                file=sys.stderr,
            )
            return 2
    try:
        loaded = load_set(args.data, args.taxonomy)
    except InvalidSet as error:
        print(f"invalid set: {error}", file=sys.stderr)
        return 2
    last = Report.from_json(args.last.read_text(encoding="utf-8")) if args.last.exists() else None
    model, clock, models = llm()
    report = run_evaluation(model, loaded, clock, models=models)
    print(render(report, last))
    if args.save:
        args.last.parent.mkdir(parents=True, exist_ok=True)
        args.last.write_text(report.to_json(), encoding="utf-8")
        print(f"saved to {args.last}")
    return 0
