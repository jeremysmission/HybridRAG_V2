from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.extraction.installed_base_extractor import (
    extract_installed_base_records_from_text,
    extract_path_derived_installed_base,
    extract_quantity_at_site,
    extract_serial_numbers,
    extract_snapshot_date,
    is_installed_base_candidate_path,
)


@pytest.mark.parametrize("path,expected", [
    (r"E:\CorpusTransfr\Site Inventory\Site Inventory Report_Guam.xlsx", True),
    (r"E:\CorpusTransfr\Site Inventory\Site Inventory Report_Guam.pdf", True),
    (r"E:\CorpusTransfr\Installation Summary Documents\Guam_As-Built_2024.xlsx", True),
    (r"E:\CorpusTransfr\Installation Summary Documents\Guam_As-Built_2024.pdf", True),
    (r"E:\CorpusTransfr\Logistics\Spares Inventory (Guam)_(2024-01-01).pdf", True),
    (r"E:\CorpusTransfr\Install\Acceptance Test\ATP_Guam.docx", True),
    (r"E:\CorpusTransfr\Misc\notes.txt", False),
])
def test_is_installed_base_candidate_path(path, expected):
    assert is_installed_base_candidate_path(path) is expected


def test_extract_snapshot_date_from_path():
    text = r"E:\CorpusTransfr\Guam\2021-06-02 thru 06-08\Site Inventory\Report.xlsx"
    assert extract_snapshot_date(text) == "2021-06-02"


def test_extract_snapshot_date_missing_returns_empty():
    assert extract_snapshot_date("no date token here") == ""


def test_extract_serial_numbers_primary_pattern():
    text = "Part ARC-4471 Serial Number SN-778899 Qty 2"
    serials = extract_serial_numbers(text)
    assert "SN-778899" in serials


def test_extract_serial_numbers_secondary_pattern():
    text = "ARC-4471 S/N ABCD-1234"
    serials = extract_serial_numbers(text)
    assert "ABCD-1234" in serials


@pytest.mark.parametrize("text,expected", [
    ("qty installed 12", 12),
    ("on hand: 7", 7),
    ("spares 3", 3),
    ("quantity at site 21", 21),
    ("5 units", 5),
    ("no quantity here", None),
])
def test_extract_quantity_at_site(text, expected):
    assert extract_quantity_at_site(text) == expected


def test_extract_records_from_text_with_quantities():
    rows = extract_installed_base_records_from_text(
        "ARC-4471 qty 12 installed\nWR-200 qty 4 installed",
        source_path="p1",
        chunk_id="c1",
        system="NEXION",
        site_token="guam",
        snapshot_date="2024-03-01",
        snapshot_year=2024,
    )
    assert len(rows) == 2
    assert rows[0].part_number == "ARC-4471"
    assert rows[0].quantity_at_site == 12
    assert rows[1].part_number == "WR-200"
    assert rows[1].quantity_at_site == 4


def test_extract_records_from_text_serial_implies_quantity_one():
    rows = extract_installed_base_records_from_text(
        "ARC-4471 serial number SN-445566",
        source_path="p1",
        chunk_id="c1",
        system="NEXION",
        site_token="guam",
        snapshot_date="2024-03-01",
        snapshot_year=2024,
    )
    assert len(rows) == 1
    assert rows[0].serial_number == "SN-445566"
    assert rows[0].quantity_at_site == 1


def test_extract_records_from_text_ignores_lines_without_qty_or_serial():
    rows = extract_installed_base_records_from_text(
        "ARC-4471 observed in report header only",
        source_path="p1",
        chunk_id="c1",
        system="NEXION",
        site_token="guam",
        snapshot_date="2024-03-01",
        snapshot_year=2024,
    )
    assert rows == []


def test_extract_path_derived_installed_base(tmp_path):
    db = tmp_path / "retrieval_metadata.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE source_metadata (
            source_path TEXT,
            site_token TEXT,
            source_doc_hash TEXT
        );
        INSERT INTO source_metadata VALUES
            ('E:/CorpusTransfr/NEXION/Guam/2024-03-01/Site Inventory Report_Guam.xlsx', 'guam', 'h1'),
            ('E:/CorpusTransfr/random/notes.txt', 'guam', 'h2'),
            ('E:/CorpusTransfr/ISTO/Djibouti/2025-01-10/As-Built_Djibouti.xlsx', 'djibouti', 'h3');
        """
    )
    conn.commit()
    conn.close()
    rows = list(extract_path_derived_installed_base(db))
    assert len(rows) == 2
    assert rows[0].system == "NEXION"
    assert rows[0].site_token == "guam"
    assert rows[1].system == "ISTO"
    assert rows[1].site_token == "djibouti"
