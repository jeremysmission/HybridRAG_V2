"""Read-only validation/report CLI for controlled vocabulary packs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vocab.pack_loader import VocabPackError  # noqa: E402
from src.vocab.pack_reports import build_vocab_report, format_vocab_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Collect command-line options so the script can decide what work to run."""
    parser = argparse.ArgumentParser(
        description="Validate and summarize controlled vocabulary packs."
    )
    parser.add_argument(
        "--pack-dir",
        default=str(ROOT / "config" / "vocab_packs"),
        help="Directory containing sanitized vocab pack YAML files.",
    )
    parser.add_argument(
        "--lookup",
        action="append",
        default=[],
        help="Exact alias/canonical lookup term. May be repeated.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    return parser.parse_args()


def main() -> int:
    """Parse command-line inputs and run the main vocab pack report 2026-04-15 workflow."""
    args = parse_args()
    try:
        report = build_vocab_report(args.pack_dir, lookups=args.lookup)
    except VocabPackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_vocab_report(report))
        if args.lookup:
            print()
            print("Run note:")
            print(
                f"  .\\.venv\\Scripts\\python.exe scripts\\vocab_pack_report_2026-04-15.py "
                f"--lookup {args.lookup[0]!r}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
