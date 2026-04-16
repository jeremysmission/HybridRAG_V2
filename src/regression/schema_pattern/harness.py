"""Regression harness for schema-pattern checks. It runs saved cases, scores the outcome, and produces a readable report."""
# ============================================================================
# HybridRAG V2 -- Schema Pattern Regression Harness
# (src/regression/schema_pattern/harness.py)
# ============================================================================
# Read-only classifier that decides keep / drop / normalize for an
# (entity_type, text) pair, based on the full-index pattern mining done
# on 2026-04-15. Frozen fixture lives at:
#   tests/regression/schema_pattern/fixture_2026_04_15.json
#
# Use as a library (GUI panel, pytest), or as a CLI:
#   python -m src.regression.schema_pattern.harness
#   python -m src.regression.schema_pattern.harness --fixture <path> --json
# ============================================================================

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Fixture location
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE_PATH = (
    _REPO_ROOT / "tests" / "regression" / "schema_pattern"
    / "fixture_2026_04_15.json"
)

# ---------------------------------------------------------------------------
# Rules (from FULL_INDEX_SCHEMA_PATTERN_MINING_2026-04-15.md regex/tag table)
# ---------------------------------------------------------------------------

_SITE_DROP_PATTERNS = [
    re.compile(r"^(?:WEBSITE|OBSOLESCENCE WEBSITE|SITE|LOCATION|FACILITY|WH|CABINET \d+)$", re.IGNORECASE),
    re.compile(r"^(?:alternate (?:processing|work) site(?:s)?|server rooms?|organizational facilities)$", re.IGNORECASE),
]

_PERSON_DROP_PATTERNS = [
    re.compile(r"^(?:CFO|root|users?|attacker|individuals?|personnel)$", re.IGNORECASE),
    re.compile(r"^organizational personnel(?: with information security responsibilities)?$", re.IGNORECASE),
    re.compile(r"^system(?:/network)? administrators?$", re.IGNORECASE),
    re.compile(r"^system developers?$", re.IGNORECASE),
]

_CONTACT_DROP_NUMERIC = re.compile(r"^\d{8,10}$")
_CONTACT_KEEP_EMAIL = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\.?$", re.IGNORECASE)
_CONTACT_KEEP_PHONE = re.compile(r"^(?:\(\d{3}\)\s*|\d{3}[-\s])\d{3}[-\s]\d{4}$")

_DATE_DROP_HEADER = re.compile(r"^[A-Z][A-Z /_-]+ DATE$")
_DATE_KEEP_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_KEEP_SLASH = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
_DATE_KEEP_DASH_MONTH = re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$")

_ORG_DROP_PATTERNS = [
    re.compile(r"^(?:the )?organizations?$", re.IGNORECASE),
]

# Normalization clusters: (entity_type, lowercased_variant) -> canonical
_NORMALIZE_MAP: dict[tuple[str, str], str] = {
    ("SITE", "onsite"):    "Onsite",
    ("SITE", "on-site"):   "Onsite",
    ("ORG",  "mcmaster-carr"): "McMaster-Carr",
    ("PO",   "ir-4a"):     "IR-4A",
}

# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class Case:
    """Structured input record that keeps one unit of work easy to pass around and inspect."""
    id: str
    family: str
    text: str
    entity_type: str
    expected: str            # "keep" | "drop" | "normalize"
    why: str = ""
    canonical: str | None = None
    hits: int = 0
    docs: int = 0


@dataclass
class Verdict:
    """Structured helper object used by the harness workflow."""
    case_id: str
    family: str
    text: str
    entity_type: str
    expected: str
    actual: str
    canonical_expected: str | None
    canonical_actual: str | None
    passed: bool
    rule: str = ""


@dataclass
class FamilyStat:
    """Structured record used to hold a computed statistic for reporting."""
    family: str
    total: int = 0
    passed: int = 0
    failed_cases: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total) if self.total else 0.0


@dataclass
class Report:
    """Small structured record used to keep related results together as the workflow runs."""
    fixture_id: str
    total: int
    passed: int
    failed: int
    families: list[FamilyStat]
    verdicts: list[Verdict]

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total) if self.total else 0.0

    def as_dict(self) -> dict:
        return {
            "fixture_id": self.fixture_id,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "families": [
                {
                    "family": f.family,
                    "total": f.total,
                    "passed": f.passed,
                    "pass_rate": f.pass_rate,
                    "failed_cases": list(f.failed_cases),
                }
                for f in self.families
            ],
            "verdicts": [asdict(v) for v in self.verdicts],
        }


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify(entity_type: str, text: str) -> tuple[str, str | None, str]:
    """Classify (entity_type, text).

    Returns (action, canonical_or_none, rule_name).
    action is one of: "keep", "drop", "normalize".
    """
    et = (entity_type or "").upper().strip()
    raw = text or ""
    s = raw.strip()

    # Normalization clusters first (so "McMaster-Carr" is normalize, not keep).
    canon = _NORMALIZE_MAP.get((et, s.lower()))
    if canon is not None:
        return "normalize", canon, "normalize_cluster"

    if et == "SITE":
        for rx in _SITE_DROP_PATTERNS:
            if rx.match(s):
                return "drop", None, "site_drop_pattern"
        return "keep", None, "site_default_keep"

    if et == "PERSON":
        for rx in _PERSON_DROP_PATTERNS:
            if rx.match(s):
                return "drop", None, "person_drop_pattern"
        return "keep", None, "person_default_keep"

    if et == "CONTACT":
        if _CONTACT_KEEP_EMAIL.match(s):
            return "keep", None, "contact_email"
        if _CONTACT_KEEP_PHONE.match(s):
            return "keep", None, "contact_phone"
        if _CONTACT_DROP_NUMERIC.match(s):
            return "drop", None, "contact_numeric_junk"
        return "keep", None, "contact_default_keep"

    if et == "DATE":
        if _DATE_KEEP_ISO.match(s) or _DATE_KEEP_SLASH.match(s) or _DATE_KEEP_DASH_MONTH.match(s):
            return "keep", None, "date_calendar_value"
        if _DATE_DROP_HEADER.match(s):
            return "drop", None, "date_header_label"
        return "keep", None, "date_default_keep"

    if et == "ORG":
        for rx in _ORG_DROP_PATTERNS:
            if rx.match(s):
                return "drop", None, "org_generic_bucket"
        return "keep", None, "org_default_keep"

    # PART, PO, and any unhandled type default to keep.
    return "keep", None, "default_keep"


# ---------------------------------------------------------------------------
# Fixture I/O + runner
# ---------------------------------------------------------------------------

def load_fixture(path: str | Path | None = None) -> dict:
    """Load the data needed for the harness workflow."""
    p = Path(path) if path else DEFAULT_FIXTURE_PATH
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _iter_cases(fixture: dict) -> Iterable[Case]:
    """Support the harness workflow by handling the iter cases step."""
    for raw in fixture.get("cases", []):
        yield Case(
            id=raw["id"],
            family=raw["family"],
            text=raw["text"],
            entity_type=raw["entity_type"],
            expected=raw["expected"],
            why=raw.get("why", ""),
            canonical=raw.get("canonical"),
            hits=int(raw.get("hits", 0) or 0),
            docs=int(raw.get("docs", 0) or 0),
        )


def run_fixture(fixture: dict | None = None, fixture_path: str | Path | None = None) -> Report:
    """Execute one complete stage of the workflow and return its results."""
    if fixture is None:
        fixture = load_fixture(fixture_path)

    fam_stats: dict[str, FamilyStat] = {}
    verdicts: list[Verdict] = []
    passed_total = 0

    for case in _iter_cases(fixture):
        action, canonical, rule = classify(case.entity_type, case.text)
        # For normalize cases, also require canonical match.
        passed = (action == case.expected)
        if passed and case.expected == "normalize":
            passed = (canonical == case.canonical)

        v = Verdict(
            case_id=case.id,
            family=case.family,
            text=case.text,
            entity_type=case.entity_type,
            expected=case.expected,
            actual=action,
            canonical_expected=case.canonical,
            canonical_actual=canonical,
            passed=passed,
            rule=rule,
        )
        verdicts.append(v)

        fs = fam_stats.setdefault(case.family, FamilyStat(family=case.family))
        fs.total += 1
        if passed:
            fs.passed += 1
            passed_total += 1
        else:
            fs.failed_cases.append(case.id)

    total = len(verdicts)
    return Report(
        fixture_id=fixture.get("fixture_id", "unknown"),
        total=total,
        passed=passed_total,
        failed=total - passed_total,
        families=sorted(fam_stats.values(), key=lambda f: f.family),
        verdicts=verdicts,
    )


# ---------------------------------------------------------------------------
# Fixture validator (forward-compat preflight surface)
# ---------------------------------------------------------------------------

_VALID_ACTIONS_SET = {"keep", "drop", "normalize"}


def validate_fixture(fixture: object) -> list[str]:
    """Return a list of validation error strings for `fixture`. Empty list
    means the fixture is structurally valid for this harness.

    Pure function: never raises, never reads disk, never logs. Suitable for
    preflight gates, CLI checks, and test assertions on user-supplied
    fixture files.
    """
    errors: list[str] = []

    if not isinstance(fixture, dict):
        return ["fixture must be a JSON object at the top level"]

    if "fixture_id" not in fixture:
        errors.append("missing required key: fixture_id")
    elif not isinstance(fixture["fixture_id"], str) or not fixture["fixture_id"]:
        errors.append("fixture_id must be a non-empty string")

    if "cases" not in fixture:
        errors.append("missing required key: cases")
        return errors

    cases = fixture["cases"]
    if not isinstance(cases, list):
        errors.append("cases must be a list")
        return errors

    if not cases:
        errors.append("cases list is empty")

    seen_ids: set[str] = set()
    for i, case in enumerate(cases):
        prefix = "cases[{}]".format(i)
        if not isinstance(case, dict):
            errors.append("{}: must be a JSON object".format(prefix))
            continue
        for key in ("id", "text", "entity_type", "expected"):
            if key not in case:
                errors.append("{}: missing required key: {}".format(prefix, key))

        cid = case.get("id")
        if cid is not None:
            if not isinstance(cid, str) or not cid:
                errors.append("{}: id must be a non-empty string".format(prefix))
            elif cid in seen_ids:
                errors.append("{}: duplicate id: {}".format(prefix, cid))
            else:
                seen_ids.add(cid)

        exp = case.get("expected")
        if exp is not None and exp not in _VALID_ACTIONS_SET:
            errors.append(
                "{}: expected must be one of {} (got {!r})".format(
                    prefix, sorted(_VALID_ACTIONS_SET), exp
                )
            )

        if exp == "normalize" and not case.get("canonical"):
            errors.append(
                "{}: normalize case missing canonical".format(prefix)
            )

        et = case.get("entity_type")
        if et is not None and (not isinstance(et, str) or not et):
            errors.append("{}: entity_type must be a non-empty string".format(prefix))

    return errors


# ---------------------------------------------------------------------------
# Multi-fixture runner (CI smoke surface)
# ---------------------------------------------------------------------------

def discover_fixtures(directory: str | Path | None = None) -> list[Path]:
    """Return every `fixture_*.json` file in `directory` (default: same dir
    as the frozen tier1 fixture). Sorted by name for stable ordering."""
    base = Path(directory) if directory else DEFAULT_FIXTURE_PATH.parent
    return sorted(base.glob("fixture_*.json"))


def run_all_fixtures(directory: str | Path | None = None) -> list[Report]:
    """Run every discovered fixture and return their reports in order."""
    return [run_fixture(fixture_path=p) for p in discover_fixtures(directory)]


def format_oneline_summary(reports: list[Report]) -> str:
    """One-line CI/launcher-friendly summary across all reports."""
    if not reports:
        return "schema_pattern_regression: no fixtures discovered"
    total = sum(r.total for r in reports)
    passed = sum(r.passed for r in reports)
    failed = sum(r.failed for r in reports)
    verdict = "PASS" if failed == 0 else "FAIL"
    return (
        "schema_pattern_regression: {verdict} "
        "fixtures={n} cases={p}/{t} ({rate:.1%}) failed={f}"
    ).format(
        verdict=verdict, n=len(reports), p=passed, t=total,
        rate=(passed / total) if total else 0.0, f=failed,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _format_text_report(r: Report) -> str:
    """Turn internal values into human-readable text for the operator."""
    lines: list[str] = []
    lines.append("Schema Pattern Regression Report")
    lines.append("=" * 60)
    lines.append("Fixture: {}".format(r.fixture_id))
    lines.append("Overall: {}/{} passed ({:.1%})".format(r.passed, r.total, r.pass_rate))
    lines.append("")
    lines.append("-- By family --")
    for f in r.families:
        lines.append("  {:<40s} {:>3d}/{:<3d}  {:>6.1%}".format(
            f.family, f.passed, f.total, f.pass_rate
        ))
        for cid in f.failed_cases:
            lines.append("      FAIL  {}".format(cid))
    lines.append("")
    lines.append("-- Failures --")
    fails = [v for v in r.verdicts if not v.passed]
    if not fails:
        lines.append("  (none)")
    else:
        for v in fails:
            lines.append(
                "  {:<35s} {} {:<8s} expected={} actual={} canon_exp={} canon_act={}".format(
                    v.case_id, v.entity_type, repr(v.text)[:24],
                    v.expected, v.actual,
                    v.canonical_expected, v.canonical_actual,
                )
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Parse command-line inputs and run the main harness workflow."""
    ap = argparse.ArgumentParser(
        description="Run the schema pattern regression fixture(s)."
    )
    ap.add_argument("--fixture", default=None,
                    help="Path to a single fixture JSON (default: frozen 2026-04-15 fixture).")
    ap.add_argument("--all", action="store_true",
                    help="Run every fixture_*.json discovered in --directory.")
    ap.add_argument("--directory", default=None,
                    help="Directory to scan for fixtures when --all is set.")
    ap.add_argument("--json", action="store_true",
                    help="Emit JSON instead of text.")
    ap.add_argument("--oneline", action="store_true",
                    help="Emit only the one-line CI summary (use with --all or alone).")
    ap.add_argument("--validate", default=None, metavar="PATH",
                    help="Validate a fixture file; exit 0 if clean, 1 if errors.")
    args = ap.parse_args(argv)

    if args.validate is not None:
        try:
            fixture = load_fixture(args.validate)
        except Exception as exc:
            print("validate: failed to load fixture: {}".format(exc))
            return 1
        errors = validate_fixture(fixture)
        if not errors:
            print("validate: OK ({} cases)".format(len(fixture.get("cases", []))))
            return 0
        print("validate: {} error(s)".format(len(errors)))
        for e in errors:
            print("  - {}".format(e))
        return 1

    if args.all:
        reports = run_all_fixtures(directory=args.directory)
        if args.oneline:
            print(format_oneline_summary(reports))
        elif args.json:
            print(json.dumps(
                {
                    "summary": format_oneline_summary(reports),
                    "reports": [r.as_dict() for r in reports],
                },
                indent=2,
            ))
        else:
            for r in reports:
                print(_format_text_report(r))
                print("")
            print(format_oneline_summary(reports))
        return 0 if all(r.failed == 0 for r in reports) else 1

    report = run_fixture(fixture_path=args.fixture)

    if args.oneline:
        print(format_oneline_summary([report]))
    elif args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(_format_text_report(report))

    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
