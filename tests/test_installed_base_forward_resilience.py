from __future__ import annotations

import sqlite3
from pathlib import Path

from openpyxl import Workbook

from scripts.populate_installed_base import run_xlsx_pass


def _write_inventory_workbook(path: Path, rows: list[list[object]], *, sheet_name: str = "Sheet1") -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    wb.save(path)
    wb.close()
    return path


def _seed_metadata_db(db_path: Path, rows: list[tuple[str, str, str]]) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE source_metadata (
            source_path TEXT,
            site_token TEXT,
            source_doc_hash TEXT
        );
        """
    )
    conn.executemany("INSERT INTO source_metadata VALUES (?, ?, ?)", rows)
    conn.commit()
    conn.close()


def test_populate_twice_keeps_count_stable(tmp_path: Path):
    data_index = tmp_path / "data" / "index"
    data_index.mkdir(parents=True)
    lance_db = data_index / "lancedb"
    lance_db.mkdir()
    wb_path = _write_inventory_workbook(
        tmp_path / "NEXION Site Inventory Report_Guam.xlsx",
        [
            ["PART NUMBER", "QTY", "SERIAL NUMBER"],
            ["ARC-4471", 2, "SN1"],
            ["WR-200", 1, ""],
        ],
    )
    metadata_db = data_index / "retrieval_metadata.sqlite3"
    _seed_metadata_db(
        metadata_db,
        [(str(wb_path), "guam", "h1")],
    )
    output_db = tmp_path / "installed_base.sqlite3"
    stats1 = run_xlsx_pass(lance_db, output_db=output_db)
    stats2 = run_xlsx_pass(lance_db, output_db=output_db)
    assert stats1["coverage"]["total_rows"] == 2
    assert stats2["coverage"]["total_rows"] == 2


def test_fake_site_folder_adds_rows_without_mutating_existing(tmp_path: Path):
    data_index = tmp_path / "data" / "index"
    data_index.mkdir(parents=True)
    lance_db = data_index / "lancedb"
    lance_db.mkdir()

    wb_existing = _write_inventory_workbook(
        tmp_path / "NEXION Site Inventory Report_Guam.xlsx",
        [
            ["PART NUMBER", "QTY", "SERIAL NUMBER"],
            ["ARC-4471", 2, "SN1"],
        ],
    )
    metadata_db = data_index / "retrieval_metadata.sqlite3"
    _seed_metadata_db(metadata_db, [(str(wb_existing), "guam", "h1")])
    output_db = tmp_path / "installed_base.sqlite3"
    run_xlsx_pass(lance_db, output_db=output_db)

    conn = sqlite3.connect(metadata_db)
    wb_new = _write_inventory_workbook(
        tmp_path / "NEXION Site Inventory Report_NewSite.xlsx",
        [
            ["PART NUMBER", "QTY", "SERIAL NUMBER"],
            ["SEMS3D-40536", 3, "SN2"],
        ],
    )
    conn.execute(
        "INSERT INTO source_metadata VALUES (?, ?, ?)",
        (str(wb_new), "newsite", "h2"),
    )
    conn.commit()
    conn.close()

    stats = run_xlsx_pass(lance_db, output_db=output_db)
    assert stats["coverage"]["total_rows"] == 2

    check = sqlite3.connect(output_db)
    rows = check.execute(
        "SELECT part_number, site_token, quantity_at_site FROM installed_base ORDER BY part_number"
    ).fetchall()
    check.close()
    assert rows == [
        ("ARC-4471", "guam", 2),
        ("SEMS3D-40536", "newsite", 3),
    ]


def test_existing_site_rows_unchanged_after_additive_ingestion(tmp_path: Path):
    data_index = tmp_path / "data" / "index"
    data_index.mkdir(parents=True)
    lance_db = data_index / "lancedb"
    lance_db.mkdir()

    wb_existing = _write_inventory_workbook(
        tmp_path / "NEXION Site Inventory Report_Guam.xlsx",
        [
            ["PART NUMBER", "QTY", "SERIAL NUMBER"],
            ["ARC-4471", 2, "SN1"],
        ],
    )
    metadata_db = data_index / "retrieval_metadata.sqlite3"
    _seed_metadata_db(metadata_db, [(str(wb_existing), "guam", "h1")])
    output_db = tmp_path / "installed_base.sqlite3"
    run_xlsx_pass(lance_db, output_db=output_db)

    check = sqlite3.connect(output_db)
    before = check.execute(
        "SELECT part_number, site_token, quantity_at_site FROM installed_base WHERE site_token='guam'"
    ).fetchall()
    check.close()

    conn = sqlite3.connect(metadata_db)
    wb_new = _write_inventory_workbook(
        tmp_path / "NEXION Site Inventory Report_Wake.xlsx",
        [
            ["PART NUMBER", "QTY", "SERIAL NUMBER"],
            ["WR-200", 4, "SN9"],
        ],
    )
    conn.execute(
        "INSERT INTO source_metadata VALUES (?, ?, ?)",
        (str(wb_new), "wake", "h2"),
    )
    conn.commit()
    conn.close()

    run_xlsx_pass(lance_db, output_db=output_db)

    check = sqlite3.connect(output_db)
    after = check.execute(
        "SELECT part_number, site_token, quantity_at_site FROM installed_base WHERE site_token='guam'"
    ).fetchall()
    all_rows = check.execute(
        "SELECT part_number, site_token, quantity_at_site FROM installed_base ORDER BY site_token, part_number"
    ).fetchall()
    check.close()
    assert before == after
    assert ("WR-200", "wake", 4) in all_rows
