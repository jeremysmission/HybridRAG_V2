"""Test module for the tier1 clean store audit behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.audit_tier1_clean_store import (
    PART_SENTINELS,
    PO_SENTINELS,
    audit_clean_store,
    render_markdown,
    resolve_store_paths,
)


def _init_entity_db(db_path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    """Support this test module by handling the init entity db step."""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            text TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            confidence REAL NOT NULL,
            chunk_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            context TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE extracted_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            table_id TEXT NOT NULL,
            row_index INTEGER NOT NULL,
            headers TEXT NOT NULL,
            values_json TEXT NOT NULL,
            chunk_id TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO entities (
            entity_type, text, raw_text, confidence, chunk_id, source_path, context
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def _init_relationship_db(db_path: Path, rows: list[tuple[str, str, str, str, str, float, str, str, str]]) -> None:
    """Support this test module by handling the init relationship db step."""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,
            subject_text TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_text TEXT NOT NULL,
            confidence REAL NOT NULL,
            source_path TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            context TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO relationships (
            subject_type, subject_text, predicate, object_type, object_text,
            confidence, source_path, chunk_id, context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def test_resolve_store_paths_infers_relationship_sibling(tmp_path):
    """Verify that resolve store paths infers relationship sibling behaves the way the team expects."""
    entity_db = tmp_path / "entities.sqlite3"
    entity_db.touch()
    relationship_db = tmp_path / "relationships.sqlite3"
    relationship_db.touch()

    paths = resolve_store_paths(entity_db)

    assert paths.entity_db == str(entity_db)
    assert paths.relationship_db == str(relationship_db)


def test_clean_store_audit_passes_on_clean_fixture(tmp_path):
    """Verify that clean store audit passes on clean fixture behaves the way the team expects."""
    entity_db = tmp_path / "entities.sqlite3"
    rel_db = tmp_path / "relationships.sqlite3"
    rows = []
    for idx, sentinel in enumerate(PO_SENTINELS, start=1):
        rows.append(("PO", sentinel, sentinel, 1.0, f"po-{idx}", f"docs/po/{idx}.txt", "PO sentinel"))
    for idx, sentinel in enumerate(PART_SENTINELS, start=1):
        rows.append(("PART", sentinel, sentinel, 1.0, f"part-{idx}", f"docs/part/{idx}.txt", "PART sentinel"))
    rows.extend(
        [
            ("PERSON", "Alice Example", "Alice Example", 1.0, "p-1", "docs/p.txt", ""),
            ("SITE", "Thule Air Base", "Thule Air Base", 1.0, "s-1", "docs/s.txt", ""),
            ("DATE", "2025-04-01", "2025-04-01", 1.0, "d-1", "docs/d.txt", ""),
            ("ORG", "Example Org", "Example Org", 1.0, "o-1", "docs/o.txt", ""),
            ("CONTACT", "555-234-5678", "555-234-5678", 1.0, "c-1", "docs/c.txt", ""),
        ]
    )
    _init_entity_db(entity_db, rows)
    _init_relationship_db(
        rel_db,
        [
            ("SITE", "Thule Air Base", "LOCATED_AT", "PART", "RG-213", 1.0, "docs/r1.txt", "r-1", "site relation"),
            ("PERSON", "Alice Example", "WORKS_AT", "SITE", "Thule Air Base", 1.0, "docs/r2.txt", "r-2", "works at"),
        ],
    )

    report = audit_clean_store(entity_db=entity_db)

    assert report.ok
    assert report.entity_total == len(rows)
    assert report.relationship_total == 2
    assert report.blocked_hits == []
    assert all(item.present for item in report.po_sentinels)
    assert all(item.present for item in report.part_sentinels)
    markdown = render_markdown(report)
    assert "Verdict" in markdown
    assert "PASS" in markdown
    assert "Top PO Values" in markdown


def test_clean_store_audit_flags_blocked_top_values(tmp_path):
    """Verify that clean store audit flags blocked top values behaves the way the team expects."""
    entity_db = tmp_path / "entities.sqlite3"
    rel_db = tmp_path / "relationships.sqlite3"
    rows = [
        ("PO", "IR-4", "IR-4", 1.0, "po-1", "docs/bad_po.txt", ""),
        ("PO", "IR-4", "IR-4", 1.0, "po-2", "docs/bad_po.txt", ""),
        ("PO", "7000298452", "7000298452", 1.0, "po-3", "docs/good_po.txt", ""),
        ("PART", "AS-5021", "AS-5021", 1.0, "part-1", "docs/bad_part.txt", ""),
        ("PART", "AS-5021", "AS-5021", 1.0, "part-2", "docs/bad_part.txt", ""),
        ("PART", "RG-213", "RG-213", 1.0, "part-3", "docs/good_part.txt", ""),
    ]
    _init_entity_db(entity_db, rows)
    _init_relationship_db(
        rel_db,
        [("SITE", "Thule Air Base", "LOCATED_AT", "PART", "RG-213", 1.0, "docs/r.txt", "r-1", "")],
    )

    report = audit_clean_store(entity_db=entity_db, top_po_limit=3, top_part_limit=3)

    assert not report.ok
    assert any(hit.entity_type == "PO" and hit.text == "IR-4" for hit in report.blocked_hits)
    assert any(hit.entity_type == "PART" and hit.text == "AS-5021" for hit in report.blocked_hits)
    assert any("missing PO sentinels" in issue for issue in report.issues)
    assert any("missing PART sentinels" in issue for issue in report.issues)
