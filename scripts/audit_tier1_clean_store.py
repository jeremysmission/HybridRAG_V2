#!/usr/bin/env python3
"""
Post-rerun clean-store audit for Tier 1.

This is a read-only acceptance harness for a finished clean Tier 1 rerun.
It inspects the entity and relationship stores, reports the current counts
and top values, and flags the namespace collisions that must not survive the
clean rerun.

The harness is intentionally conservative:
- It requires a readable entity store.
- It infers the sibling relationship store when not given explicitly.
- It reports PO/PART top values and checks them against the known blocked
  namespaces from the Tier 1 regex work.
- It checks for a preserve set of real business identifiers that must still
  survive a clean rerun.
- It can emit JSON and Markdown artifacts for the clean-rerun results doc.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENTITY_DB = REPO_ROOT / "data" / "index" / "clean" / "tier1_clean_20260413" / "entities.sqlite3"
KNOWN_ENTITY_TYPES = ("PERSON", "PART", "SITE", "DATE", "PO", "ORG", "CONTACT")

PO_BLOCKED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "control_family",
        re.compile(
            r"^(?:AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)"
            r"-\d{1,2}(?:\(\d+\))?$"
        ),
    ),
    ("ir_lookalike", re.compile(r"^IR-[A-Z0-9_-]+$")),
    ("report_id_noise", re.compile(r"^(?:FSR|UMR|ASV|RTS)-[A-Z0-9_-]+$")),
)

PART_BLOCKED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("stig_platform", re.compile(r"^(?:AS|OS|GPOS|HS)-\d{3,5}$")),
    ("cci", re.compile(r"^CCI-\d+$")),
    ("sv", re.compile(r"^SV-\d+$")),
    ("cce", re.compile(r"^CCE-\d+$")),
    ("cve", re.compile(r"^CVE-\d{4}")),
    ("rhsa", re.compile(r"^RHSA-\d{4}")),
    ("stig_filename", re.compile(r"^STIG-\d{4}")),
    ("lower_underscore", re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")),
    ("service_status", re.compile(r"^SERVICE_(?:START|STOP)$")),
    ("generic_debris", re.compile(r"^(?:mode|NORMAL|failure)$")),
    ("app_requirement", re.compile(r"^APP-\d{4}$")),
)

PO_SENTINELS: tuple[str, ...] = (
    "7000372377",
    "7200751620",
    "268235",
    "250802",
    "5000696458",
    "5300168230",
)

PART_SENTINELS: tuple[str, ...] = (
    "RG-213",
    "LMR-400",
    "FGD-0800",
    "POL-2100",
    "PCE-4129",
    "PT-2700",
    "TK-423",
    "PS-110",
    "MRF-141",
    "DBZH-101",
)


@dataclass(frozen=True)
class StorePaths:
    """Structured helper object used by the audit tier1 clean store workflow."""
    entity_db: str
    relationship_db: str


@dataclass(frozen=True)
class EntityTypeCount:
    """Structured record used to hold a computed statistic for reporting."""
    entity_type: str
    count: int


@dataclass(frozen=True)
class RelationshipPredicateCount:
    """Structured record used to hold a computed statistic for reporting."""
    predicate: str
    count: int
    distinct_sources: int
    sample_source: str


@dataclass(frozen=True)
class TopValue:
    """Structured helper object used by the audit tier1 clean store workflow."""
    entity_type: str
    text: str
    rows: int
    distinct_sources: int
    sample_source: str


@dataclass(frozen=True)
class BlockedHit:
    """Structured helper object used by the audit tier1 clean store workflow."""
    entity_type: str
    namespace: str
    text: str
    rows: int
    distinct_sources: int
    sample_source: str


@dataclass(frozen=True)
class SentinelResult:
    """Small structured record used to keep related results together as the workflow runs."""
    entity_type: str
    text: str
    present: bool
    rows: int
    distinct_sources: int
    sample_source: str


@dataclass
class CleanStoreAudit:
    """Structured helper object used by the audit tier1 clean store workflow."""
    entity_db: str
    relationship_db: str
    entity_total: int
    extracted_table_rows: int
    relationship_total: int
    entity_type_counts: list[EntityTypeCount]
    relationship_predicates: list[RelationshipPredicateCount]
    top_po: list[TopValue]
    top_part: list[TopValue]
    blocked_hits: list[BlockedHit]
    po_sentinels: list[SentinelResult]
    part_sentinels: list[SentinelResult]
    warnings: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _default_entity_db() -> Path:
    """Support the audit tier1 clean store workflow by handling the default entity db step."""
    if DEFAULT_ENTITY_DB.exists():
        return DEFAULT_ENTITY_DB
    return REPO_ROOT / "data" / "index" / "entities.sqlite3"


def resolve_store_paths(
    entity_db: str | Path | None,
    relationship_db: str | Path | None = None,
) -> StorePaths:
    """Resolve the final path or setting value that downstream code should use."""
    entity_path = Path(entity_db) if entity_db else _default_entity_db()
    rel_path = Path(relationship_db) if relationship_db else entity_path.with_name("relationships.sqlite3")
    return StorePaths(entity_db=str(entity_path), relationship_db=str(rel_path))


def _open_ro_sqlite(db_path: str | Path) -> sqlite3.Connection:
    """Support the audit tier1 clean store workflow by handling the open ro sqlite step."""
    path = Path(db_path)
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _count_scalar(conn: sqlite3.Connection, sql: str) -> int:
    """Support the audit tier1 clean store workflow by handling the count scalar step."""
    row = conn.execute(sql).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def load_entity_type_counts(conn: sqlite3.Connection) -> list[EntityTypeCount]:
    """Load the data needed for the audit tier1 clean store workflow."""
    rows = conn.execute(
        "SELECT entity_type, COUNT(*) AS n FROM entities GROUP BY entity_type"
    ).fetchall()
    counts = {row["entity_type"]: int(row["n"]) for row in rows}
    return [EntityTypeCount(entity_type=etype, count=counts.get(etype, 0)) for etype in KNOWN_ENTITY_TYPES]


def load_top_values(
    conn: sqlite3.Connection,
    entity_type: str,
    limit: int,
) -> list[TopValue]:
    """Load the data needed for the audit tier1 clean store workflow."""
    rows = conn.execute(
        """
        SELECT
            text,
            COUNT(*) AS rows,
            COUNT(DISTINCT source_path) AS distinct_sources,
            COALESCE(MIN(source_path), '') AS sample_source
        FROM entities
        WHERE entity_type = ?
        GROUP BY text
        ORDER BY rows DESC, text ASC
        LIMIT ?
        """,
        (entity_type, limit),
    ).fetchall()
    return [
        TopValue(
            entity_type=entity_type,
            text=row["text"],
            rows=int(row["rows"]),
            distinct_sources=int(row["distinct_sources"]),
            sample_source=row["sample_source"],
        )
        for row in rows
    ]


def load_relationship_predicates(
    conn: sqlite3.Connection,
    limit: int,
) -> list[RelationshipPredicateCount]:
    """Load the data needed for the audit tier1 clean store workflow."""
    rows = conn.execute(
        """
        SELECT
            predicate,
            COUNT(*) AS rows,
            COUNT(DISTINCT source_path) AS distinct_sources,
            COALESCE(MIN(source_path), '') AS sample_source
        FROM relationships
        GROUP BY predicate
        ORDER BY rows DESC, predicate ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        RelationshipPredicateCount(
            predicate=row["predicate"],
            count=int(row["rows"]),
            distinct_sources=int(row["distinct_sources"]),
            sample_source=row["sample_source"],
        )
        for row in rows
    ]


def _classify_blocked(entity_type: str, text: str) -> str | None:
    """Support the audit tier1 clean store workflow by handling the classify blocked step."""
    patterns = PO_BLOCKED_PATTERNS if entity_type == "PO" else PART_BLOCKED_PATTERNS
    for namespace, pattern in patterns:
        if pattern.match(text):
            return namespace
    return None


def _load_sentinel_results(
    conn: sqlite3.Connection,
    entity_type: str,
    sentinels: Iterable[str],
) -> list[SentinelResult]:
    """Load the data needed for the audit tier1 clean store workflow."""
    results: list[SentinelResult] = []
    for sentinel in sentinels:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS rows,
                COUNT(DISTINCT source_path) AS distinct_sources,
                COALESCE(MIN(source_path), '') AS sample_source
            FROM entities
            WHERE entity_type = ? AND text = ?
            """,
            (entity_type, sentinel),
        ).fetchone()
        rows = int(row["rows"]) if row else 0
        results.append(
            SentinelResult(
                entity_type=entity_type,
                text=sentinel,
                present=rows > 0,
                rows=rows,
                distinct_sources=int(row["distinct_sources"]) if row else 0,
                sample_source=row["sample_source"] if row else "",
            )
        )
    return results


def _blocked_hits_from_top_values(top_values: Iterable[TopValue]) -> list[BlockedHit]:
    """Support the audit tier1 clean store workflow by handling the blocked hits from top values step."""
    hits: list[BlockedHit] = []
    for item in top_values:
        namespace = _classify_blocked(item.entity_type, item.text)
        if namespace:
            hits.append(
                BlockedHit(
                    entity_type=item.entity_type,
                    namespace=namespace,
                    text=item.text,
                    rows=item.rows,
                    distinct_sources=item.distinct_sources,
                    sample_source=item.sample_source,
                )
            )
    return hits


def audit_clean_store(
    entity_db: str | Path | None = None,
    relationship_db: str | Path | None = None,
    top_po_limit: int = 20,
    top_part_limit: int = 30,
    relationship_predicate_limit: int = 10,
) -> CleanStoreAudit:
    """Support the audit tier1 clean store workflow by handling the audit clean store step."""
    paths = resolve_store_paths(entity_db, relationship_db)
    entity_path = Path(paths.entity_db)
    rel_path = Path(paths.relationship_db)

    warnings: list[str] = []
    issues: list[str] = []

    entity_total = 0
    extracted_table_rows = 0
    entity_type_counts: list[EntityTypeCount] = [EntityTypeCount(etype, 0) for etype in KNOWN_ENTITY_TYPES]
    top_po: list[TopValue] = []
    top_part: list[TopValue] = []
    po_sentinels: list[SentinelResult] = [SentinelResult("PO", sentinel, False, 0, 0, "") for sentinel in PO_SENTINELS]
    part_sentinels: list[SentinelResult] = [
        SentinelResult("PART", sentinel, False, 0, 0, "") for sentinel in PART_SENTINELS
    ]
    blocked_hits: list[BlockedHit] = []

    try:
        with _open_ro_sqlite(entity_path) as entity_conn:
            entity_total = _count_scalar(entity_conn, "SELECT COUNT(*) FROM entities")
            extracted_table_rows = _count_scalar(
                entity_conn, "SELECT COUNT(*) FROM extracted_tables"
            )
            entity_type_counts = load_entity_type_counts(entity_conn)
            top_po = load_top_values(entity_conn, "PO", top_po_limit)
            top_part = load_top_values(entity_conn, "PART", top_part_limit)
            po_sentinels = _load_sentinel_results(entity_conn, "PO", PO_SENTINELS)
            part_sentinels = _load_sentinel_results(entity_conn, "PART", PART_SENTINELS)

            if entity_total <= 0:
                issues.append("entity store is empty")
            if not top_po:
                issues.append("no PO values found")
            if not top_part:
                issues.append("no PART values found")

            missing_po = [item.text for item in po_sentinels if not item.present]
            missing_part = [item.text for item in part_sentinels if not item.present]
            if missing_po:
                issues.append("missing PO sentinels: " + ", ".join(missing_po))
            if missing_part:
                issues.append("missing PART sentinels: " + ", ".join(missing_part))

            blocked_hits = _blocked_hits_from_top_values(top_po + top_part)
            if blocked_hits:
                hit_text = "; ".join(
                    f"{hit.entity_type}:{hit.namespace}:{hit.text}" for hit in blocked_hits
                )
                issues.append("blocked namespaces remain in top values: " + hit_text)
    except Exception as exc:
        issues.append(f"entity store error: {exc}")

    if not rel_path.exists():
        issues.append(f"relationship store missing: {rel_path}")
        relationship_total = 0
        relationship_predicates: list[RelationshipPredicateCount] = []
    else:
        try:
            with _open_ro_sqlite(rel_path) as rel_conn:
                relationship_total = _count_scalar(rel_conn, "SELECT COUNT(*) FROM relationships")
                relationship_predicates = load_relationship_predicates(
                    rel_conn, relationship_predicate_limit
                )
                if relationship_total <= 0:
                    issues.append("relationship store is empty")
                if not relationship_predicates:
                    warnings.append("relationship store returned no predicate summary rows")
        except Exception as exc:
            issues.append(f"relationship store error: {exc}")
            relationship_total = 0
            relationship_predicates = []

    return CleanStoreAudit(
        entity_db=str(entity_path),
        relationship_db=str(rel_path),
        entity_total=entity_total,
        extracted_table_rows=extracted_table_rows,
        relationship_total=relationship_total,
        entity_type_counts=entity_type_counts,
        relationship_predicates=relationship_predicates,
        top_po=top_po,
        top_part=top_part,
        blocked_hits=blocked_hits,
        po_sentinels=po_sentinels,
        part_sentinels=part_sentinels,
        warnings=warnings,
        issues=issues,
    )


def render_markdown(report: CleanStoreAudit) -> str:
    """Render the collected results into a report-friendly format."""
    lines: list[str] = []
    lines.append("# Tier 1 Clean Rerun Store Audit")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"- **Verdict:** {'PASS' if report.ok else 'FAIL'}")
    lines.append(f"- Entity DB: `{report.entity_db}`")
    lines.append(f"- Relationship DB: `{report.relationship_db}`")
    lines.append("")
    lines.append("## Store Counts")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Entities | {report.entity_total:,} |")
    lines.append(f"| Extracted tables | {report.extracted_table_rows:,} |")
    lines.append(f"| Relationships | {report.relationship_total:,} |")
    lines.append("")
    lines.append("### Entity Types")
    lines.append("")
    lines.append("| Entity Type | Count |")
    lines.append("|---|---:|")
    for item in report.entity_type_counts:
        lines.append(f"| {item.entity_type} | {item.count:,} |")
    lines.append("")
    lines.append("## Top PO Values")
    lines.append("")
    lines.append("| Text | Rows | Distinct Sources | Sample Source |")
    lines.append("|---|---:|---:|---|")
    for item in report.top_po:
        lines.append(
            f"| `{item.text}` | {item.rows:,} | {item.distinct_sources:,} | `{item.sample_source}` |"
        )
    if not report.top_po:
        lines.append("| _none_ | 0 | 0 | _n/a_ |")
    lines.append("")
    lines.append("## Top PART Values")
    lines.append("")
    lines.append("| Text | Rows | Distinct Sources | Sample Source |")
    lines.append("|---|---:|---:|---|")
    for item in report.top_part:
        lines.append(
            f"| `{item.text}` | {item.rows:,} | {item.distinct_sources:,} | `{item.sample_source}` |"
        )
    if not report.top_part:
        lines.append("| _none_ | 0 | 0 | _n/a_ |")
    lines.append("")
    lines.append("## Blocked Namespace Hits")
    lines.append("")
    if report.blocked_hits:
        lines.append("| Entity | Namespace | Text | Rows | Distinct Sources | Sample Source |")
        lines.append("|---|---|---|---:|---:|---|")
        for hit in report.blocked_hits:
            lines.append(
                f"| {hit.entity_type} | `{hit.namespace}` | `{hit.text}` | {hit.rows:,} | "
                f"{hit.distinct_sources:,} | `{hit.sample_source}` |"
            )
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Preserve Sentinels")
    lines.append("")
    lines.append("### PO")
    lines.append("")
    lines.append("| Text | Present | Rows | Distinct Sources |")
    lines.append("|---|---|---:|---:|")
    for item in report.po_sentinels:
        lines.append(
            f"| `{item.text}` | {'yes' if item.present else 'no'} | {item.rows:,} | {item.distinct_sources:,} |"
        )
    lines.append("")
    lines.append("### PART")
    lines.append("")
    lines.append("| Text | Present | Rows | Distinct Sources |")
    lines.append("|---|---|---:|---:|")
    for item in report.part_sentinels:
        lines.append(
            f"| `{item.text}` | {'yes' if item.present else 'no'} | {item.rows:,} | {item.distinct_sources:,} |"
        )
    lines.append("")
    if report.relationship_predicates:
        lines.append("## Relationship Summary")
        lines.append("")
        lines.append("| Predicate | Count | Distinct Sources | Sample Source |")
        lines.append("|---|---:|---:|---|")
        for item in report.relationship_predicates:
            lines.append(
                f"| `{item.predicate}` | {item.count:,} | {item.distinct_sources:,} | `{item.sample_source}` |"
            )
        lines.append("")
    if report.warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    if report.issues:
        lines.append("## Issues")
        lines.append("")
        for issue in report.issues:
            lines.append(f"- {issue}")
        lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "This report is a post-rerun store audit. PASS means the finished clean Tier 1 store still preserves the expected procurement / hardware sentinels and does not surface the blocked namespaces in the highest-ranked PO/PART values."
    )
    return "\n".join(lines)


def _print_text(report: CleanStoreAudit) -> None:
    """Render a readable summary for the person running the tool."""
    print("=" * 72)
    print("TIER 1 CLEAN RERUN STORE AUDIT")
    print("=" * 72)
    print(f"Entity DB:       {report.entity_db}")
    print(f"Relationship DB: {report.relationship_db}")
    print(f"Entities:        {report.entity_total:,}")
    print(f"Extracted tables: {report.extracted_table_rows:,}")
    print(f"Relationships:   {report.relationship_total:,}")
    print()
    print("Entity type counts:")
    for item in report.entity_type_counts:
        print(f"  - {item.entity_type}: {item.count:,}")
    print()
    print("Top PO values:")
    if report.top_po:
        for item in report.top_po:
            print(
                f"  - {item.text} [{item.rows:,} rows, {item.distinct_sources:,} sources] "
                f"({item.sample_source})"
            )
    else:
        print("  - none")
    print()
    print("Top PART values:")
    if report.top_part:
        for item in report.top_part:
            print(
                f"  - {item.text} [{item.rows:,} rows, {item.distinct_sources:,} sources] "
                f"({item.sample_source})"
            )
    else:
        print("  - none")
    print()
    if report.blocked_hits:
        print("Blocked namespace hits:")
        for hit in report.blocked_hits:
            print(
                f"  - {hit.entity_type}:{hit.namespace}:{hit.text} "
                f"[{hit.rows:,} rows, {hit.distinct_sources:,} sources]"
            )
    else:
        print("Blocked namespace hits: none")
    print()
    print("Preserve sentinels:")
    for label, items in (("PO", report.po_sentinels), ("PART", report.part_sentinels)):
        missing = [item.text for item in items if not item.present]
        print(f"  - {label}: {'ok' if not missing else 'missing ' + ', '.join(missing)}")
    print()
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"  - {warning}")
        print()
    if report.issues:
        print("Issues:")
        for issue in report.issues:
            print(f"  - {issue}")
    else:
        print("Issues: none")
    print()
    print("Verdict:", "PASS" if report.ok else "FAIL")


def main(argv: list[str] | None = None) -> int:
    """Parse command-line inputs and run the main audit tier1 clean store workflow."""
    parser = argparse.ArgumentParser(description="Post-rerun clean-store audit for Tier 1.")
    parser.add_argument("--entity-db", help="Path to the entities.sqlite3 file to audit.")
    parser.add_argument(
        "--relationship-db",
        help="Optional path to the relationships.sqlite3 sibling store.",
    )
    parser.add_argument(
        "--top-po",
        type=int,
        default=20,
        help="Number of PO values to inspect for blocked namespaces.",
    )
    parser.add_argument(
        "--top-part",
        type=int,
        default=30,
        help="Number of PART values to inspect for blocked namespaces.",
    )
    parser.add_argument(
        "--relationship-predicate-limit",
        type=int,
        default=10,
        help="Number of relationship predicates to include in the summary.",
    )
    parser.add_argument(
        "--markdown",
        help="Optional output path for a Markdown report artifact.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the JSON report after the text summary.",
    )
    args = parser.parse_args(argv)

    report = audit_clean_store(
        entity_db=args.entity_db,
        relationship_db=args.relationship_db,
        top_po_limit=args.top_po,
        top_part_limit=args.top_part,
        relationship_predicate_limit=args.relationship_predicate_limit,
    )
    _print_text(report)

    if args.markdown:
        out_path = Path(args.markdown)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"\nMarkdown report written to: {out_path}")

    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
