#!/usr/bin/env python3
"""
Tier 1 regex corpus audit helper.

Read-only helper for mining PO/PART confusion sets from the live store and
from procurement-heavy corpus paths. Designed to be rerun before and after a
Tier 1 rerun so the team can compare hard-reject families against real
business identifiers that must survive.

Usage:
    .venv\\Scripts\\python.exe scripts\\audit_tier1_regex_corpus.py
    .venv\\Scripts\\python.exe scripts\\audit_tier1_regex_corpus.py --json
    .venv\\Scripts\\python.exe scripts\\audit_tier1_regex_corpus.py --out audit.json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTITY_DB = REPO_ROOT / "data" / "index" / "entities.sqlite3"
LANCE_DB = REPO_ROOT / "data" / "index" / "lancedb"
PROCUREMENT_ROOTS = (
    Path(r"E:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement"),
    Path(r"E:\CorpusTransfr\verified\IGS\zzSEMS ARCHIVE\005_ILS\Purchases"),
)

PO_FAMILY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "control_family",
        re.compile(
            r"^(?:AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)"
            r"-\d{1,2}(?:\(\d+\))?$"
        ),
    ),
    ("ir_other", re.compile(r"^IR-[A-Z0-9_-]+$")),
    ("report_id", re.compile(r"^(?:FSR|UMR|ASV|RTS)-[A-Z0-9_-]+$")),
)

PART_FAMILY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("stig_platform", re.compile(r"^(?:AS|OS|GPOS|HS)-\d{3,5}$")),
    ("cci", re.compile(r"^CCI-\d+$")),
    ("sv", re.compile(r"^SV-\d+$")),
    ("cce", re.compile(r"^CCE-\d+$")),
    ("cve", re.compile(r"^CVE-\d{4}")),
    ("rhsa", re.compile(r"^RHSA-\d{4}")),
    ("stig_filename", re.compile(r"^STIG-\d{4}")),
    ("lower_underscore", re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")),
    ("service_status", re.compile(r"^SERVICE_(?:START|STOP)$")),
    ("generic_word", re.compile(r"^(?:mode|NORMAL|failure|SNMP)$")),
    ("audit_phrase", re.compile(r"^audit processing failure$")),
)

PO_FALSE_SENTINELS = (
    "IR-8",
    "IR-4",
    "FSR-L22",
    "FSR-461-M-USB",
    "ASV-VAFB",
    "RTS-DATA",
)
PO_TRUE_SENTINELS = (
    "7000372377",
    "7200751620",
    "268235",
    "250802",
    "5000696458",
    "5300168230",
)
PART_FALSE_SENTINELS = (
    "AS-5021",
    "OS-0004",
    "CCI-0003",
    "SV-2045",
    "pam_faillock",
    "unconfined_u",
    "SERVICE_STOP",
    "SNMP",
    "APP-0001",
    "RHSA-2018",
)
PART_TRUE_SENTINELS = (
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

PROCUREMENT_PO_RE = re.compile(
    r"(?i)\bPO[ _-]?([0-9]{6,10})\b|\bPurchase Order[ _-]?([0-9]{6,10})\b"
)


def open_entity_db() -> sqlite3.Connection:
    """Support the audit tier1 regex corpus workflow by handling the open entity db step."""
    return sqlite3.connect(f"file:{ENTITY_DB.as_posix()}?mode=ro", uri=True)


def short_path(path: str, keep: int = 3) -> str:
    """Support the audit tier1 regex corpus workflow by handling the short path step."""
    parts = (path or "").replace("\\", "/").split("/")
    if len(parts) <= keep:
        return path
    return "/".join(parts[-keep:])


def classify(text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> str:
    """Support the audit tier1 regex corpus workflow by handling the classify step."""
    for family, pattern in patterns:
        if pattern.match(text):
            return family
    return "other"


def summarize_families(
    conn: sqlite3.Connection,
    entity_type: str,
    patterns: tuple[tuple[str, re.Pattern[str]], ...],
) -> dict:
    """Condense detailed results into a shorter summary that is easier to review."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT text, COUNT(*) AS n
        FROM entities
        WHERE entity_type = ?
        GROUP BY text
        ORDER BY n DESC
        """,
        (entity_type,),
    )
    total = 0
    family_counts: Counter[str] = Counter()
    examples: dict[str, Counter[str]] = {name: Counter() for name, _ in patterns}
    examples["other"] = Counter()

    for text, count in cur.fetchall():
        total += count
        family = classify(text, patterns)
        family_counts[family] += count
        examples[family][text] += count

    return {
        "total_rows": total,
        "families": [
            {
                "family": family,
                "rows": rows,
                "share": round(rows / total, 6) if total else 0.0,
                "top_values": [
                    {"text": text, "rows": count}
                    for text, count in examples[family].most_common(8)
                ],
            }
            for family, rows in family_counts.most_common()
        ],
    }


def sample_entity_rows(
    conn: sqlite3.Connection,
    entity_type: str,
    text: str,
    limit: int = 3,
) -> list[dict]:
    """Support the audit tier1 regex corpus workflow by handling the sample entity rows step."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT source_path, context
        FROM entities
        WHERE entity_type = ?
          AND text = ?
        LIMIT ?
        """,
        (entity_type, text, limit),
    )
    rows = []
    for source_path, context in cur.fetchall():
        rows.append(
            {
                "source_path": source_path,
                "short_source": short_path(source_path),
                "context": (context or "").replace("\n", " ")[:280],
            }
        )
    return rows


def top_survivor_candidates(
    conn: sqlite3.Connection,
    entity_type: str,
    patterns: tuple[tuple[str, re.Pattern[str]], ...],
    limit: int = 25,
) -> list[dict]:
    """Support the audit tier1 regex corpus workflow by handling the top survivor candidates step."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT text, COUNT(*) AS n, COUNT(DISTINCT source_path) AS doc_count
        FROM entities
        WHERE entity_type = ?
        GROUP BY text
        ORDER BY n DESC
        """,
        (entity_type,),
    )
    out = []
    for text, rows, doc_count in cur.fetchall():
        if classify(text, patterns) != "other":
            continue
        out.append({"text": text, "rows": rows, "distinct_sources": doc_count})
        if len(out) >= limit:
            break
    return out


def scan_procurement_paths(limit: int = 30) -> dict:
    """Support the audit tier1 regex corpus workflow by handling the scan procurement paths step."""
    counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    length_counts: Counter[int] = Counter()

    for root in PROCUREMENT_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            match = PROCUREMENT_PO_RE.search(str(path))
            if not match:
                continue
            po_number = match.group(1) or match.group(2)
            counts[po_number] += 1
            length_counts[len(po_number)] += 1
            examples.setdefault(po_number, str(path))

    return {
        "roots_present": [str(root) for root in PROCUREMENT_ROOTS if root.exists()],
        "unique_po_numbers": len(counts),
        "length_distribution": {
            str(length): count for length, count in sorted(length_counts.items())
        },
        "top_examples": [
            {
                "po_number": po_number,
                "matches": matches,
                "example_path": examples[po_number],
            }
            for po_number, matches in counts.most_common(limit)
        ],
    }


def maybe_chunk_hits(queries: tuple[str, ...], limit: int = 2) -> dict[str, list[dict]]:
    """Support the audit tier1 regex corpus workflow by handling the maybe chunk hits step."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from src.store.lance_store import LanceStore
    except Exception:
        return {}

    store = LanceStore(str(LANCE_DB))
    if store._table is None:
        return {}

    out: dict[str, list[dict]] = {}
    for query in queries:
        try:
            rows = store._table.search(query, query_type="fts").limit(limit).to_list()
        except Exception:
            rows = []
        out[query] = [
            {
                "source_path": row.get("source_path") or "",
                "short_source": short_path(row.get("source_path") or ""),
                "text_preview": ((row.get("text") or "").replace("\n", " "))[:280],
            }
            for row in rows
        ]
    store.close()
    return out


def build_report() -> dict:
    """Assemble the structured object this workflow needs for its next step."""
    conn = open_entity_db()
    try:
        po_summary = summarize_families(conn, "PO", PO_FAMILY_PATTERNS)
        part_summary = summarize_families(conn, "PART", PART_FAMILY_PATTERNS)

        report = {
            "entity_db": str(ENTITY_DB),
            "po_summary": po_summary,
            "part_summary": part_summary,
            "po_false_sentinels": {
                text: sample_entity_rows(conn, "PO", text) for text in PO_FALSE_SENTINELS
            },
            "po_true_sentinels": {
                text: sample_entity_rows(conn, "PO", text) for text in PO_TRUE_SENTINELS
            },
            "part_false_sentinels": {
                text: sample_entity_rows(conn, "PART", text) for text in PART_FALSE_SENTINELS
            },
            "part_true_sentinels": {
                text: sample_entity_rows(conn, "PART", text) for text in PART_TRUE_SENTINELS
            },
            "po_survivor_candidates": top_survivor_candidates(
                conn, "PO", PO_FAMILY_PATTERNS, limit=20
            ),
            "part_survivor_candidates": top_survivor_candidates(
                conn, "PART", PART_FAMILY_PATTERNS, limit=30
            ),
            "procurement_path_scan": scan_procurement_paths(limit=25),
            "po_chunk_hits": maybe_chunk_hits(PO_TRUE_SENTINELS, limit=2),
            "part_chunk_hits": maybe_chunk_hits(PART_TRUE_SENTINELS, limit=2),
        }
    finally:
        conn.close()
    return report


def render_text(report: dict) -> str:
    """Render the collected results into a report-friendly format."""
    lines = []
    lines.append("Tier 1 Regex Corpus Audit")
    lines.append("=========================")
    lines.append("")
    lines.append(f"Entity DB: {report['entity_db']}")
    lines.append("")

    for label in ("po_summary", "part_summary"):
        summary = report[label]
        title = "PO" if label.startswith("po") else "PART"
        lines.append(f"{title} family summary ({summary['total_rows']:,} rows)")
        lines.append("-" * (len(lines[-1])))
        for family in summary["families"][:10]:
            lines.append(
                f"{family['family']}: {family['rows']:,} "
                f"({family['share'] * 100:.2f}%)"
            )
            if family["top_values"]:
                lines.append(
                    "  top: " + ", ".join(
                        f"{item['text']} ({item['rows']:,})"
                        for item in family["top_values"][:6]
                    )
                )
        lines.append("")

    scan = report["procurement_path_scan"]
    lines.append("Procurement path scan")
    lines.append("---------------------")
    lines.append(f"Roots present: {', '.join(scan['roots_present'])}")
    lines.append(f"Unique PO numbers in path names: {scan['unique_po_numbers']}")
    lines.append(f"Length distribution: {scan['length_distribution']}")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Parse command-line inputs and run the main audit tier1 regex corpus workflow."""
    parser = argparse.ArgumentParser(description="Mine Tier 1 PO/PART confusion sets.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--out", help="Optional file path for the JSON report.")
    args = parser.parse_args()

    report = build_report()

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json or args.out:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
