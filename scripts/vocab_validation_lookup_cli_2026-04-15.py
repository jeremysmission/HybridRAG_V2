"""Controlled vocabulary validation, lookup, and text-scan CLI."""

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
        description=(
            "Validate controlled vocabulary packs, run exact alias lookups, "
            "and scan text for deterministic vocab hits."
        )
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
        "--text",
        help="Literal text to scan for deterministic vocab hits.",
    )
    parser.add_argument(
        "--text-file",
        help="Path to a UTF-8 text file to scan for deterministic vocab hits.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    return parser.parse_args()


def _resolve_scan_text(args: argparse.Namespace) -> str | None:
    """Resolve the final path or setting value that downstream code should use."""
    if args.text and args.text_file:
        raise ValueError("use only one of --text or --text-file")
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8")
    return args.text


def main() -> int:
    """Parse command-line inputs and run the main vocab validation lookup cli 2026-04-15 workflow."""
    args = parse_args()
    try:
        scan_text = _resolve_scan_text(args)
        report = build_vocab_report(
            args.pack_dir,
            lookups=args.lookup,
            scan_text=scan_text,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: unable to read text input: {exc}", file=sys.stderr)
        return 2
    except VocabPackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_vocab_report(report))
        print()
        print("Run note:")
        print(
            "  .\\.venv\\Scripts\\python.exe "
            "scripts\\vocab_validation_lookup_cli_2026-04-15.py "
            "--lookup DD1149 --lookup POAM "
            '--text "Patrick AFB uses DD1149 and POAM tracking."'
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
