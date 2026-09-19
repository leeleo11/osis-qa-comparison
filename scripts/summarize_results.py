"""Create ignored JSON/CSV summaries from local QA run artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.reporting import collect_records, write_reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    records = collect_records(args.runs_dir)
    outputs = write_reports(args.output, records)
    print(f"summarized {len(records)} runs -> {outputs['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
