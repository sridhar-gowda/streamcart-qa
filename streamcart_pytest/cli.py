"""The ``streamcart`` command: what CI runs *between* pytest sessions.

streamcart merge-results shard-*/run-results.json -o run-results.json   # one run from many shards
streamcart publish run-results.json [--platform web --env staging ...] # run the channels (TMS, ...)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from streamcart.core.config import load_settings
from streamcart_pytest.channels import ResultChannel, TmsChannel, publish_all
from streamcart_pytest.results import RunResults, merge_files
from streamcart_pytest.tms import adapter_for


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="streamcart", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    merge = commands.add_parser("merge-results", help="merge shard runs of one run")
    merge.add_argument("runs", nargs="+", type=Path)
    merge.add_argument("-o", "--output", type=Path, required=True)

    publish = commands.add_parser("publish", help="publish a run-results file to the configured channels")
    publish.add_argument("run_results", type=Path)
    publish.add_argument("--platform")
    publish.add_argument("--env")
    publish.add_argument("--target")

    args = parser.parse_args(argv)
    if args.command == "merge-results":
        merged = merge_files(args.runs)
        merged.write(args.output)
        print(f"merged {len(args.runs)} run-results file(s), {len(merged.results)} result(s) -> {args.output}")
        return 0
    if args.command == "publish":
        settings = load_settings({"platform": args.platform, "env": args.env, "target": args.target})
        run_results = RunResults.read(args.run_results)
        channels: list[ResultChannel] = [TmsChannel(adapter_for(settings), settings)]
        receipts = publish_all(run_results, channels)
        run_results.write(args.run_results)
        for receipt in receipts:
            print(f"{'ok' if receipt.ok else 'FAILED'} {receipt.channel}: {receipt.detail}")
        return 0 if all(r.ok for r in receipts) else 1
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
