"""
Generate and validate a workstation-safe derived eval profile.

This script reads the canonical production eval corpus, rewrites only the
workstation-facing narrative fields, and writes a derived profile plus a
validation report. It never overwrites the canonical corpus unless the caller
explicitly points an output path at it.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_EVAL = (
    REPO_ROOT / "tests" / "golden_eval" / "production_queries_400_2026-04-12.json"
)
PROFILE_ROOT = REPO_ROOT / "tests" / "golden_eval" / "profiles" / "workstation_safe"
PROFILE_NAME = "workstation_safe"

SANITIZED_FIELDS = (
    "user_input",
    "reference",
    "rationale",
    "corpus_grounding_evidence",
)

PRESERVED_FIELDS = (
    "query_id",
    "persona",
    "expected_query_type",
    "expected_document_family",
    "reference_contexts",
    "expected_source_patterns",
    "expected_anchor_entities",
    "difficulty",
    "has_ground_truth",
)


@dataclass(frozen=True)
class ReplacementRule:
    """Structured helper object used by the generate workstation safe eval workflow."""
    name: str
    pattern: re.Pattern[str]
    replacement: str


PROGRAM_REPLACEMENTS = (
    ReplacementRule(
        name="igs_nexion",
        pattern=re.compile(r"(?<![A-Za-z0-9])enterprise program[/ ]monitoring system(?![A-Za-z0-9])", re.IGNORECASE),
        replacement="enterprise program / monitoring system",
    ),
    ReplacementRule(
        name="isto_and_nexion",
        pattern=re.compile(
            r"(?<![A-Za-z0-9])legacy monitoring system\s+and\s+monitoring system\s+systems?(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
        replacement="legacy monitoring system and monitoring system",
    ),
    ReplacementRule(
        name="nexion_and_isto",
        pattern=re.compile(
            r"(?<![A-Za-z0-9])monitoring system\s+and\s+legacy monitoring system\s+systems?(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
        replacement="monitoring system and legacy monitoring system",
    ),
    ReplacementRule(
        name="isto_nexion",
        pattern=re.compile(
            r"(?<![A-Za-z0-9])legacy monitoring system / monitoring system(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
        replacement="legacy monitoring system / monitoring system",
    ),
    ReplacementRule(
        name="nexion_isto",
        pattern=re.compile(
            r"(?<![A-Za-z0-9])monitoring system / legacy monitoring system(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
        replacement="monitoring system / legacy monitoring system",
    ),
    ReplacementRule(
        name="igs_program",
        pattern=re.compile(r"(?<![A-Za-z0-9])IGS\s+program(?![A-Za-z0-9])", re.IGNORECASE),
        replacement="enterprise program",
    ),
    ReplacementRule(
        name="monitoring system",
        pattern=re.compile(r"(?<![A-Za-z0-9])monitoring system(?![A-Za-z0-9])", re.IGNORECASE),
        replacement="monitoring system",
    ),
    ReplacementRule(
        name="legacy monitoring system",
        pattern=re.compile(r"(?<![A-Za-z0-9])legacy monitoring system(?![A-Za-z0-9])", re.IGNORECASE),
        replacement="legacy monitoring system",
    ),
    ReplacementRule(
        name="enterprise program",
        pattern=re.compile(r"(?<![A-Za-z0-9])enterprise program(?![A-Za-z0-9])", re.IGNORECASE),
        replacement="enterprise program",
    ),
    ReplacementRule(
        name="rtx_3090",
        pattern=re.compile(
            r"(?<![A-Za-z0-9])(?:NVIDIA\s+GeForce\s+)?RTX\s*3090(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
        replacement="NVIDIA workstation GPU",
    ),
    ReplacementRule(
        name="geforce_rtx_3090",
        pattern=re.compile(
            r"(?<![A-Za-z0-9])NVIDIA\s+GeForce\s+RTX\s*3090(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
        replacement="NVIDIA workstation GPU",
    ),
    ReplacementRule(
        name="dual_3090",
        pattern=re.compile(r"(?<![A-Za-z0-9])dual[- ]3090s?(?![A-Za-z0-9])", re.IGNORECASE),
        replacement="NVIDIA workstation desktop GPUs",
    ),
    ReplacementRule(
        name="single_3090",
        pattern=re.compile(r"(?<![A-Za-z0-9])single\s+3090(?![A-Za-z0-9])", re.IGNORECASE),
        replacement="single NVIDIA workstation GPU",
    ),
    ReplacementRule(
        name="bare_3090",
        pattern=re.compile(r"(?<![A-Za-z0-9])3090(?![A-Za-z0-9])", re.IGNORECASE),
        replacement="NVIDIA workstation GPU",
    ),
)

CLEANUP_REPLACEMENTS = (
    (re.compile(r"\benterprise program program\b", re.IGNORECASE), "enterprise program"),
    (re.compile(r"\bmonitoring system systems?\b", re.IGNORECASE), "monitoring system"),
    (
        re.compile(r"\blegacy monitoring systems?\b", re.IGNORECASE),
        "legacy monitoring system",
    ),
)

DISALLOWED_TOKEN_PATTERNS = {
    "enterprise program": re.compile(r"(?<![A-Za-z0-9])enterprise program(?![A-Za-z0-9])", re.IGNORECASE),
    "legacy monitoring system": re.compile(r"(?<![A-Za-z0-9])legacy monitoring system(?![A-Za-z0-9])", re.IGNORECASE),
    "monitoring system": re.compile(r"(?<![A-Za-z0-9])monitoring system(?![A-Za-z0-9])", re.IGNORECASE),
    "3090": re.compile(r"(?<![A-Za-z0-9])(?:NVIDIA\s+GeForce\s+)?RTX\s*3090|(?<![A-Za-z0-9])3090(?![A-Za-z0-9])", re.IGNORECASE),
}


def _default_profile_paths(profile_date: str) -> tuple[Path, Path]:
    """Support the generate workstation safe eval workflow by handling the default profile paths step."""
    profile_dir = PROFILE_ROOT
    derived = (
        profile_dir
        / f"production_queries_400_workstation_safe_{profile_date}.json"
    )
    validation = profile_dir / f"workstation_safe_eval_validation_{profile_date}.json"
    return derived, validation


def _load_query_rows(path: Path) -> list[dict[str, Any]]:
    """Load the data needed for the generate workstation safe eval workflow."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict):
        if "queries" in payload:
            payload = payload["queries"]
        elif "samples" in payload:
            payload = payload["samples"]
        else:
            payload = list(payload.values())

    if not isinstance(payload, list):
        raise ValueError(f"Expected list-like payload, got {type(payload).__name__}")

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Row {index} is not an object: {type(item).__name__}")
        rows.append(item)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    """Write the generated output so the workflow leaves behind a reusable artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _sha256(path: Path) -> str:
    """Support the generate workstation safe eval workflow by handling the sha256 step."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _excerpt(text: str, start: int, end: int, width: int = 36) -> str:
    """Support the generate workstation safe eval workflow by handling the excerpt step."""
    left = max(0, start - width)
    right = min(len(text), end + width)
    return text[left:right].replace("\n", " ")


def _iter_string_fragments(value: Any, field: str) -> Iterable[tuple[str, str]]:
    """Support the generate workstation safe eval workflow by handling the iter string fragments step."""
    if isinstance(value, str):
        yield field, value
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_string_fragments(item, f"{field}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_string_fragments(item, f"{field}.{key}")


def _normalize_replacement_style(replacement: str, *, original: str, span: tuple[int, int]) -> str:
    """Support the generate workstation safe eval workflow by handling the normalize replacement style step."""
    start, end = span
    prev_char = original[start - 1] if start > 0 else ""
    next_char = original[end] if end < len(original) else ""
    if prev_char in "_-" or next_char in "_-":
        return replacement.replace(" ", "-")
    return replacement


def sanitize_program_text(text: str) -> tuple[str, Counter[str]]:
    """Support the generate workstation safe eval workflow by handling the sanitize program text step."""
    updated = text
    counts: Counter[str] = Counter()

    for rule in PROGRAM_REPLACEMENTS:
        original = updated

        def _repl(match: re.Match[str]) -> str:
            counts[rule.name] += 1
            return _normalize_replacement_style(
                rule.replacement,
                original=original,
                span=match.span(),
            )

        updated = rule.pattern.sub(_repl, updated)

    for pattern, replacement in CLEANUP_REPLACEMENTS:
        updated = pattern.sub(replacement, updated)

    return updated, counts


def build_workstation_safe_profile(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Assemble the structured object this workflow needs for its next step."""
    derived_rows = copy.deepcopy(rows)
    queries_changed = 0
    fields_changed = 0
    changed_query_ids: list[str] = []
    field_changes: Counter[str] = Counter()
    token_changes: Counter[str] = Counter()

    for row in derived_rows:
        query_id = str(row.get("query_id") or row.get("id") or "")
        row_changed = False

        for field in SANITIZED_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value:
                continue

            sanitized, counts = sanitize_program_text(value)
            if sanitized == value:
                continue

            row[field] = sanitized
            row_changed = True
            fields_changed += 1
            field_changes[field] += 1
            token_changes.update(counts)

        if row_changed:
            queries_changed += 1
            changed_query_ids.append(query_id)

    summary = {
        "queries_changed": queries_changed,
        "fields_changed": fields_changed,
        "field_changes": dict(sorted(field_changes.items())),
        "token_replacements": dict(sorted(token_changes.items())),
        "changed_query_ids": changed_query_ids,
    }
    return derived_rows, summary


def validate_workstation_safe_profile(
    rows: list[dict[str, Any]],
    *,
    canonical_path: Path,
    derived_path: Path,
    transform_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the generated data before later steps rely on it."""
    disallowed_hits: list[dict[str, Any]] = []
    allowed_residual_hits: list[dict[str, Any]] = []
    allowed_residual_by_field: Counter[str] = Counter()

    for row in rows:
        query_id = str(row.get("query_id") or row.get("id") or "")

        for field in SANITIZED_FIELDS:
            for fragment_path, text in _iter_string_fragments(row.get(field), field):
                for token, pattern in DISALLOWED_TOKEN_PATTERNS.items():
                    for match in pattern.finditer(text):
                        disallowed_hits.append(
                            {
                                "query_id": query_id,
                                "field": fragment_path,
                                "token": token,
                                "excerpt": _excerpt(text, match.start(), match.end()),
                            }
                        )

        for field in PRESERVED_FIELDS:
            for fragment_path, text in _iter_string_fragments(row.get(field), field):
                for token, pattern in DISALLOWED_TOKEN_PATTERNS.items():
                    for match in pattern.finditer(text):
                        allowed_residual_hits.append(
                            {
                                "query_id": query_id,
                                "field": fragment_path,
                                "token": token,
                                "excerpt": _excerpt(text, match.start(), match.end()),
                            }
                        )
                        allowed_residual_by_field[field] += 1

    report = {
        "profile_name": PROFILE_NAME,
        "workstation_only": True,
        "canonical_corpus": str(canonical_path),
        "derived_profile": str(derived_path),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sanitized_fields": list(SANITIZED_FIELDS),
        "preserved_machine_grounding_fields": list(PRESERVED_FIELDS),
        "banned_token_policy": {
            "rewritten_program_tokens": ["enterprise program", "legacy monitoring system", "monitoring system"],
            "preserved_identifiers": [
                "IGSI-*",
                "IGSCC-*",
            ],
            "preserved_field_rationale": (
                "reference_contexts and expected_source_patterns remain exact so "
                "workstation-safe profiles do not break path-grounded eval behavior."
            ),
        },
        "summary": {
            "total_queries": len(rows),
            "queries_changed": int(transform_summary.get("queries_changed", 0))
            if transform_summary
            else 0,
            "fields_changed": int(transform_summary.get("fields_changed", 0))
            if transform_summary
            else 0,
            "disallowed_hits_in_sanitized_fields": len(disallowed_hits),
            "allowed_residual_hits_in_preserved_fields": len(allowed_residual_hits),
            "ok": not disallowed_hits,
        },
        "transform_summary": transform_summary or {},
        "allowed_residual_hits_by_field": dict(sorted(allowed_residual_by_field.items())),
        "allowed_residual_examples": allowed_residual_hits[:25],
        "disallowed_hits": disallowed_hits,
    }

    if canonical_path.exists():
        report["canonical_sha256"] = _sha256(canonical_path)
    if derived_path.exists():
        report["derived_sha256"] = _sha256(derived_path)

    return report


def parse_args() -> argparse.Namespace:
    """Collect command-line options so the script can decide what work to run."""
    today = datetime.now().date().isoformat()

    parser = argparse.ArgumentParser(
        description="Generate a workstation-safe derived profile from the canonical 400-query eval corpus."
    )
    parser.add_argument(
        "--canonical",
        type=Path,
        default=CANONICAL_EVAL,
        help="Canonical eval corpus to derive from.",
    )
    parser.add_argument(
        "--profile-date",
        default=today,
        help="Date suffix (YYYY-MM-DD) used in default output filenames.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Path for the derived workstation-safe profile JSON.",
    )
    parser.add_argument(
        "--validation-json",
        type=Path,
        default=None,
        help="Path for the validation report JSON.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Skip generation and validate an existing derived profile.",
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=None,
        help="Derived profile to validate when using --validate-only.",
    )
    return parser.parse_args()


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve the final path or setting value that downstream code should use."""
    default_output, default_validation = _default_profile_paths(args.profile_date)
    output_path = (args.output_json or default_output).resolve()
    validation_path = (args.validation_json or default_validation).resolve()
    return output_path, validation_path


def main() -> int:
    """Parse command-line inputs and run the main generate workstation safe eval workflow."""
    args = parse_args()
    canonical_path = args.canonical.resolve()
    output_path, validation_path = _resolve_paths(args)

    if output_path == canonical_path:
        raise SystemExit("Refusing to overwrite the canonical corpus.")

    if args.validate_only:
        input_path = (args.input_json or output_path).resolve()
        rows = _load_query_rows(input_path)
        report = validate_workstation_safe_profile(
            rows,
            canonical_path=canonical_path,
            derived_path=input_path,
            transform_summary=None,
        )
        _write_json(validation_path, report)
        print(
            f"Validated {len(rows)} queries; disallowed hits={report['summary']['disallowed_hits_in_sanitized_fields']}; "
            f"allowed residual hits={report['summary']['allowed_residual_hits_in_preserved_fields']}"
        )
        return 1 if report["disallowed_hits"] else 0

    canonical_rows = _load_query_rows(canonical_path)
    derived_rows, transform_summary = build_workstation_safe_profile(canonical_rows)
    _write_json(output_path, derived_rows)

    report = validate_workstation_safe_profile(
        derived_rows,
        canonical_path=canonical_path,
        derived_path=output_path,
        transform_summary=transform_summary,
    )
    _write_json(validation_path, report)

    print(
        f"Generated {len(derived_rows)} workstation-safe queries; "
        f"changed {transform_summary['queries_changed']} queries / {transform_summary['fields_changed']} fields; "
        f"disallowed hits={report['summary']['disallowed_hits_in_sanitized_fields']}; "
        f"allowed residual hits={report['summary']['allowed_residual_hits_in_preserved_fields']}"
    )
    return 1 if report["disallowed_hits"] else 0


if __name__ == "__main__":
    sys.exit(main())
