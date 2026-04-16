"""Deterministic tagging CLI for shipped controlled vocabulary packs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vocab.pack_loader import VocabPackError  # noqa: E402
from src.vocab.tagging import build_tagging_result, format_tagging_result  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Collect command-line options so the script can decide what work to run."""
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically tag text/doc snippets using shipped vocab packs "
            "and bounded alias matching."
        )
    )
    parser.add_argument(
        "--pack-dir",
        default=str(ROOT / "config" / "vocab_packs"),
        help="Directory containing sanitized vocab pack YAML files.",
    )
    parser.add_argument(
        "--text",
        help="Literal text to tag.",
    )
    parser.add_argument(
        "--text-file",
        help="Path to a UTF-8 text file to tag.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    return parser.parse_args()


def _resolve_text(args: argparse.Namespace) -> str:
    """Resolve the final path or setting value that downstream code should use."""
    if bool(args.text) == bool(args.text_file):
        raise ValueError("use exactly one of --text or --text-file")
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8")
    return args.text


def main() -> int:
    """Parse command-line inputs and run the main vocab deterministic tagging cli 2026-04-15 workflow."""
    args = parse_args()
    try:
        text = _resolve_text(args)
        result = build_tagging_result(args.pack_dir, text)
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
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(format_tagging_result(result))
        print()
        print("Run note:")
        print(
            "  .\\.venv\\Scripts\\python.exe "
            "scripts\\vocab_deterministic_tagging_cli_2026-04-15.py "
            '--text "Patrick AFB uses DD1149 and POAM tracking in the EVM package."'
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
