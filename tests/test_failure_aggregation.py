"""
Unit tests for the failure-aggregation deterministic backend.

Covers:
  - Year canonicalization (FY24, CY2024, 2024, "past 7 years", ranges)
  - System alias resolution (NEXION, ISTO)
  - Site alias resolution (Djibouti, Lemonnier, etc.)
  - Intent detection (top-N / failing / rank triggers)
  - SQL adapter: top_n_parts, top_n_parts_per_year
  - Evidence linker: evidence_for_part
  - AggregationExecutor end-to-end on a seeded in-memory substrate
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.extraction.failure_event_extractor import (
    detect_system,
    extract_part_numbers,
    extract_year,
    has_failure_signal,
)
from src.query.aggregation_executor import (
    AggregationExecutor,
    AliasTables,
    detect_aggregation_intent,
    parse_top_n,
    parse_year_range,
)
from src.store.failure_events_store import (
    FailureEvent,
    FailureEventsStore,
)


# ---------------------------------------------------------------------------
# Year canonicalization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("report filed in 2024", 2024),
    ("2023-05-10 maintenance log", 2023),
    ("FY24 actuals", 2024),
    ("CY2024 summary", 2024),
    ("FY2025 planning", 2025),
    ("no year here", None),
    ("2024_03 filename", 2024),
    ("Q1 FY26 forecast", 2026),
])
def test_extract_year(text, expected):
    assert extract_year(text) == expected


@pytest.mark.parametrize("q,expected", [
    ("top failing parts in NEXION in 2024",            (2024, 2024)),
    ("top parts from 2022-2025",                       (2022, 2025)),
    ("between 2020 and 2023",                          (2020, 2023)),
    ("top 5 failing parts each year for the past 7 years", (2019, 2025)),
    ("ranked each year",                               (None, None)),
    ("FY24 top parts",                                 (2024, 2024)),
])
def test_parse_year_range(q, expected):
    assert parse_year_range(q, anchor_year=2025) == expected


# ---------------------------------------------------------------------------
# Top-N
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("q,expected", [
    ("top 5 failing parts",    5),
    ("top 10 failing parts",   10),
    ("top five failing parts", 5),
    ("top ten failing parts",  10),
    ("highest failing parts",  5),   # default
    ("top 99 failing parts",   50),  # capped
])
def test_parse_top_n(q, expected):
    assert parse_top_n(q) == expected


# ---------------------------------------------------------------------------
# System detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("NEXION report Q1",                 "NEXION"),
    ("E:\\CorpusTransfr\\nexion\\foo",   "NEXION"),
    ("ISTO calibration",                 "ISTO"),
    ("random file",                      ""),
])
def test_detect_system(text, expected):
    assert detect_system(text) == expected


# ---------------------------------------------------------------------------
# Part numbers
# ---------------------------------------------------------------------------

def test_extract_part_numbers_basic():
    text = "The ARC-4471 failed. Also TC 16-06-23-003 and SEMS3D-5501 observed."
    parts = extract_part_numbers(text)
    assert "ARC-4471" in parts
    assert "SEMS3D-5501" in parts


def test_extract_part_numbers_filters_false_positives():
    text = "FY24 budget CY2024 Q1-2024 A027 deliverable"
    parts = extract_part_numbers(text)
    for fp in ("FY24", "CY24", "Q1-2024", "A027"):
        assert fp not in parts


def test_failure_signal_detection():
    assert has_failure_signal("The amplifier failed during calibration")
    assert has_failure_signal("Replaced due to fault")
    assert not has_failure_signal("Quarterly status update with no issues")


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("q,expected", [
    ("What were the highest failing part numbers in the NEXION system in 2024?",   True),
    ("Top 5 failing parts in ISTO in Djibouti from 2022-2025",                     True),
    ("Top 5 failure rate parts ranked each year for the past 7 years",             True),
    ("How many times has ARC-4471 failed?",                                        False),   # not a top-N
    ("Who is the POC for Thule?",                                                  False),
    ("Which part numbers are the most failing?",                                   True),
])
def test_detect_aggregation_intent(q, expected):
    assert detect_aggregation_intent(q) == expected


# ---------------------------------------------------------------------------
# Alias resolution
# ---------------------------------------------------------------------------

def test_alias_tables_load(tmp_path):
    yaml_path = V2_ROOT / "config" / "canonical_aliases.yaml"
    tables = AliasTables.load(yaml_path)
    assert tables.resolve_system("top failing parts in NEXION in 2024") == "NEXION"
    assert tables.resolve_system("ISTO calibration")                    == "ISTO"
    assert tables.resolve_site("failing parts in Djibouti")             == "djibouti"
    assert tables.resolve_site("Camp Lemonnier outage")                 == "djibouti"
    assert tables.resolve_site("guam maintenance")                      == "guam"


# ---------------------------------------------------------------------------
# Store + executor end-to-end with in-memory seeded substrate
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_store(tmp_path):
    db = tmp_path / "failure_events.sqlite3"
    store = FailureEventsStore(db)
    # Seed 15 failure events across NEXION / ISTO, 3 sites, years 2022-2025
    events = [
        # NEXION 2024 Djibouti
        FailureEvent(source_path="p1", chunk_id="c1", part_number="ARC-4471", system="NEXION", site_token="djibouti", event_year=2024, incident_id="IGSI-100"),
        FailureEvent(source_path="p2", chunk_id="c2", part_number="ARC-4471", system="NEXION", site_token="djibouti", event_year=2024, incident_id="IGSI-101"),
        FailureEvent(source_path="p3", chunk_id="c3", part_number="ARC-4471", system="NEXION", site_token="djibouti", event_year=2024, incident_id="IGSI-102"),
        FailureEvent(source_path="p4", chunk_id="c4", part_number="WR-200",  system="NEXION", site_token="djibouti", event_year=2024, incident_id="IGSI-103"),
        FailureEvent(source_path="p5", chunk_id="c5", part_number="WR-200",  system="NEXION", site_token="djibouti", event_year=2024, incident_id="IGSI-104"),
        FailureEvent(source_path="p6", chunk_id="c6", part_number="AB-115",  system="NEXION", site_token="djibouti", event_year=2024, incident_id="IGSI-105"),
        # NEXION 2023 Guam
        FailureEvent(source_path="p7", chunk_id="c7", part_number="ARC-4471", system="NEXION", site_token="guam", event_year=2023, incident_id="IGSI-200"),
        FailureEvent(source_path="p8", chunk_id="c8", part_number="FM-440",  system="NEXION", site_token="guam", event_year=2023, incident_id="IGSI-201"),
        # ISTO 2024 Djibouti
        FailureEvent(source_path="p9",  chunk_id="c9",  part_number="SEMS3D-5501", system="ISTO", site_token="djibouti", event_year=2024, incident_id="IGSI-300"),
        FailureEvent(source_path="p10", chunk_id="c10", part_number="SEMS3D-5501", system="ISTO", site_token="djibouti", event_year=2024, incident_id="IGSI-301"),
        FailureEvent(source_path="p11", chunk_id="c11", part_number="PS-909",      system="ISTO", site_token="djibouti", event_year=2023, incident_id="IGSI-302"),
        # ISTO 2025 Djibouti
        FailureEvent(source_path="p12", chunk_id="c12", part_number="SEMS3D-5501", system="ISTO", site_token="djibouti", event_year=2025, incident_id="IGSI-400"),
        # ISTO 2022 Djibouti
        FailureEvent(source_path="p13", chunk_id="c13", part_number="PS-909",      system="ISTO", site_token="djibouti", event_year=2022, incident_id="IGSI-500"),
        # Unrelated
        FailureEvent(source_path="p14", chunk_id="c14", part_number="AH-777", system="NEXION", site_token="thule",    event_year=2019, incident_id="IGSI-600"),
        FailureEvent(source_path="p15", chunk_id="c15", part_number="AH-777", system="NEXION", site_token="thule",    event_year=2020, incident_id="IGSI-601"),
    ]
    store.insert_many(events)
    yield store
    store.close()


def test_store_coverage_summary(seeded_store):
    cov = seeded_store.coverage_summary()
    assert cov["total_events"] == 15
    # ARC-4471, WR-200, AB-115, FM-440, SEMS3D-5501, PS-909, AH-777 = 7 distinct parts
    assert cov["distinct_parts"] == 7
    assert cov["distinct_systems"] == 2     # NEXION, ISTO


def test_top_n_parts_nexion_2024(seeded_store):
    rows = seeded_store.top_n_parts(system="NEXION", year_from=2024, year_to=2024, limit=5)
    # Expected: ARC-4471(3), WR-200(2), AB-115(1)
    assert rows[0]["part_number"] == "ARC-4471"
    assert rows[0]["failure_count"] == 3
    assert rows[1]["part_number"] == "WR-200"
    assert rows[1]["failure_count"] == 2
    assert rows[2]["part_number"] == "AB-115"
    assert rows[2]["failure_count"] == 1


def test_top_n_parts_isto_djibouti_2022_2025(seeded_store):
    rows = seeded_store.top_n_parts(
        system="ISTO", site_token="djibouti",
        year_from=2022, year_to=2025, limit=5,
    )
    # Expected: SEMS3D-5501(3), PS-909(2)
    assert len(rows) == 2
    assert rows[0]["part_number"] == "SEMS3D-5501"
    assert rows[0]["failure_count"] == 3
    assert rows[1]["part_number"] == "PS-909"
    assert rows[1]["failure_count"] == 2


def test_top_n_parts_per_year_nexion(seeded_store):
    per_year = seeded_store.top_n_parts_per_year(
        system="NEXION", year_from=2019, year_to=2025, limit_per_year=3,
    )
    assert 2024 in per_year
    assert per_year[2024][0]["part_number"] == "ARC-4471"
    assert 2023 in per_year
    assert per_year[2023][0]["part_number"] in ("ARC-4471", "FM-440")


def test_evidence_for_part(seeded_store):
    ev = seeded_store.evidence_for_part(
        "ARC-4471", system="NEXION", year_from=2024, year_to=2024, limit=5,
    )
    assert len(ev) == 3
    assert all(e["event_year"] == 2024 for e in ev)


# ---------------------------------------------------------------------------
# AggregationExecutor end-to-end
# ---------------------------------------------------------------------------

def test_executor_question_1_nexion_2024(seeded_store):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    exec_ = AggregationExecutor(seeded_store, aliases)
    result = exec_.try_execute(
        "What were the highest failing part numbers in the NEXION system in 2024?"
    )
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["system"] == "NEXION"
    assert result.parsed_params["year_from"] == 2024
    assert result.parsed_params["year_to"] == 2024
    assert result.ranked_rows[0]["part_number"] == "ARC-4471"
    assert "Deterministic Failure Aggregation" in result.context_text


def test_executor_question_2_isto_djibouti_range(seeded_store):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    exec_ = AggregationExecutor(seeded_store, aliases)
    result = exec_.try_execute(
        "What were the highest failing part numbers in the ISTO system in Djibouti from 2022-2025?"
    )
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["system"] == "ISTO"
    assert result.parsed_params["site_token"] == "djibouti"
    assert result.parsed_params["year_from"] == 2022
    assert result.parsed_params["year_to"] == 2025
    assert result.ranked_rows[0]["part_number"] == "SEMS3D-5501"


def test_executor_question_3_per_year_rate(seeded_store):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    exec_ = AggregationExecutor(seeded_store, aliases)
    result = exec_.try_execute(
        "What are the top 5 failure rate parts ranked each year for the past 7 years?"
    )
    assert result is not None
    # Rate without installed-base denominator → YELLOW
    assert result.tier == "YELLOW"
    assert result.parsed_params["per_year"] is True
    assert result.parsed_params["is_rate"] is True
    assert 2024 in result.per_year_rows
    assert "rate" in result.message.lower()


def test_executor_returns_none_for_non_aggregation_query(seeded_store):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    exec_ = AggregationExecutor(seeded_store, aliases)
    result = exec_.try_execute("Who is the POC for Thule?")
    assert result is None


def test_executor_unsupported_returns_red(tmp_path):
    empty_store = FailureEventsStore(tmp_path / "empty.sqlite3")
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    exec_ = AggregationExecutor(empty_store, aliases)
    # With empty substrate, try_execute returns None (pre-RED) OR a RED result
    result = exec_.try_execute("top 5 failing parts in NEXION in 2024")
    # When result is RED or None, pipeline falls through to RAG path — both are acceptable
    assert result is None or result.tier == "RED"
    empty_store.close()
