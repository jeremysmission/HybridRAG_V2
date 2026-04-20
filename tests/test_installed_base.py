from __future__ import annotations

import sys
import sqlite3
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
from src.query.aggregation_executor import AggregationExecutor, AliasTables
from src.store.failure_events_store import FailureEvent, FailureEventsStore
from src.store.installed_base_store import (
    InstalledBaseRecord,
    InstalledBaseStore,
    resolve_installed_base_db_path,
)


@pytest.mark.parametrize("path,expected", [
    (r"E:\CorpusTransfr\Site Inventory\Site Inventory Report_Guam.xlsx", True),
    (r"E:\CorpusTransfr\Installation Summary Documents\Guam_As-Built_2024.xlsx", True),
    (r"E:\CorpusTransfr\Misc\readme.txt", False),
])
def test_is_installed_base_candidate_path(path, expected):
    assert is_installed_base_candidate_path(path) is expected


def test_extract_snapshot_date():
    text = r"E:\CorpusTransfr\Guam\2021-06-02 thru 06-08\Site Inventory\Report.xlsx"
    assert extract_snapshot_date(text) == "2021-06-02"


def test_extract_serial_numbers():
    text = "Part ARC-4471 Serial Number SN-778899 Qty 2"
    serials = extract_serial_numbers(text)
    assert "SN-778899" in serials


@pytest.mark.parametrize("text,expected", [
    ("qty installed 12", 12),
    ("on hand: 7", 7),
    ("spares 3", 3),
    ("quantity at site 21", 21),
    ("no quantity here", None),
])
def test_extract_quantity_at_site(text, expected):
    assert extract_quantity_at_site(text) == expected


def test_extract_installed_base_records_from_text_quantity():
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


def test_extract_installed_base_records_from_text_serial_implies_quantity_one():
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


def test_resolve_installed_base_db_path():
    path = resolve_installed_base_db_path("data/index/lancedb")
    assert path.name == "installed_base.sqlite3"
    assert path.parent.name == "index"


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


@pytest.fixture
def installed_store(tmp_path):
    store = InstalledBaseStore(tmp_path / "installed_base.sqlite3")
    rows = [
        InstalledBaseRecord(source_path="ib1", part_number="ARC-4471", system="NEXION", site_token="guam", snapshot_date="2023-01-01", snapshot_year=2023, quantity_at_site=10, extraction_method="seed"),
        InstalledBaseRecord(source_path="ib2", part_number="ARC-4471", system="NEXION", site_token="guam", snapshot_date="2024-01-01", snapshot_year=2024, quantity_at_site=12, extraction_method="seed"),
        InstalledBaseRecord(source_path="ib3", part_number="WR-200", system="NEXION", site_token="guam", snapshot_date="2024-01-01", snapshot_year=2024, quantity_at_site=5, extraction_method="seed"),
        InstalledBaseRecord(source_path="ib4", part_number="SEMS3D-5501", system="ISTO", site_token="djibouti", snapshot_date="2024-01-01", snapshot_year=2024, quantity_at_site=2, extraction_method="seed"),
        InstalledBaseRecord(source_path="ib5", part_number="SEMS3D-5501", system="ISTO", site_token="djibouti", snapshot_date="2025-01-01", snapshot_year=2025, quantity_at_site=4, extraction_method="seed"),
        InstalledBaseRecord(source_path="ib6", part_number="PS-909", system="ISTO", site_token="djibouti", snapshot_date="2023-01-01", snapshot_year=2023, quantity_at_site=8, extraction_method="seed"),
        InstalledBaseRecord(source_path="ib7", part_number="ARC-4471", system="NEXION", site_token="thule", snapshot_date="2024-01-01", snapshot_year=2024, quantity_at_site=3, extraction_method="seed"),
    ]
    store.insert_many(rows)
    yield store
    store.close()


def test_installed_base_store_coverage_summary(installed_store):
    cov = installed_store.coverage_summary()
    assert cov["total_rows"] == 7
    assert cov["with_quantity"] == 7
    assert cov["distinct_parts"] == 4


def test_latest_quantity_for_part_picks_latest_year_same_site(installed_store):
    qty = installed_store.latest_quantity_for_part(
        "ARC-4471", system="NEXION", site_token="guam", year=2024
    )
    assert qty == 12


def test_latest_quantity_for_part_sums_across_sites(installed_store):
    qty = installed_store.latest_quantity_for_part("ARC-4471", system="NEXION", year=2024)
    assert qty == 15


def test_latest_quantity_for_part_uses_latest_not_future(installed_store):
    qty = installed_store.latest_quantity_for_part(
        "SEMS3D-5501", system="ISTO", site_token="djibouti", year=2024
    )
    assert qty == 2


@pytest.fixture
def failure_store(tmp_path):
    store = FailureEventsStore(tmp_path / "failure_events.sqlite3")
    rows = [
        FailureEvent(source_path="p1", chunk_id="c1", part_number="ARC-4471", system="NEXION", site_token="guam", event_year=2024),
        FailureEvent(source_path="p2", chunk_id="c2", part_number="ARC-4471", system="NEXION", site_token="guam", event_year=2024),
        FailureEvent(source_path="p3", chunk_id="c3", part_number="WR-200", system="NEXION", site_token="guam", event_year=2024),
        FailureEvent(source_path="p4", chunk_id="c4", part_number="SEMS3D-5501", system="ISTO", site_token="djibouti", event_year=2024),
        FailureEvent(source_path="p5", chunk_id="c5", part_number="SEMS3D-5501", system="ISTO", site_token="djibouti", event_year=2024),
        FailureEvent(source_path="p6", chunk_id="c6", part_number="SEMS3D-5501", system="ISTO", site_token="djibouti", event_year=2025),
        FailureEvent(source_path="p7", chunk_id="c7", part_number="PS-909", system="ISTO", site_token="djibouti", event_year=2023),
    ]
    store.insert_many(rows)
    yield store
    store.close()


def test_executor_rate_single_slice_green(failure_store, installed_store):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    exec_ = AggregationExecutor(failure_store, aliases, installed_store=installed_store)
    result = exec_.try_execute("top 5 failure rate parts in NEXION in 2024")
    assert result is not None
    assert result.tier == "GREEN"
    assert result.ranked_rows[0]["part_number"] == "WR-200"
    assert result.ranked_rows[0]["installed_qty"] == 5
    assert result.ranked_rows[0]["failure_rate"] == pytest.approx(1 / 5)


def test_executor_rate_per_year_green(failure_store, installed_store):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    exec_ = AggregationExecutor(failure_store, aliases, installed_store=installed_store)
    result = exec_.try_execute("top 5 failure rate parts ranked each year for the past 3 years")
    assert result is not None
    assert result.tier == "GREEN"
    assert 2023 in result.per_year_rows
    assert 2024 in result.per_year_rows
    assert result.per_year_rows[2024][0]["failure_rate"] > 0


def test_executor_rate_without_installed_store_stays_yellow(failure_store):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    exec_ = AggregationExecutor(failure_store, aliases)
    result = exec_.try_execute("top 5 failure rate parts in NEXION in 2024")
    assert result is not None
    assert result.tier == "YELLOW"
    assert "denominator" in result.message.lower()


def test_executor_rate_with_missing_denominator_falls_back_yellow(failure_store, tmp_path):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    sparse_store = InstalledBaseStore(tmp_path / "sparse.sqlite3")
    sparse_store.insert_many([
        InstalledBaseRecord(source_path="ib1", part_number="ARC-4471", system="NEXION", site_token="guam", snapshot_year=2024, quantity_at_site=12, extraction_method="seed")
    ])
    exec_ = AggregationExecutor(failure_store, aliases, installed_store=sparse_store)
    result = exec_.try_execute("top 5 failure rate parts ranked each year for the past 3 years")
    assert result is not None
    assert result.tier == "YELLOW"
    sparse_store.close()
