"""Test module for the count benchmark behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.count_benchmark import (  # noqa: E402
    _count_entity_exact,
    _count_occurrences,
    _count_row_exact,
    compare_count_maps,
    load_predictions,
    load_target_set,
    parse_modes,
    select_targets,
    summarize_results,
)


def test_count_occurrences_is_case_insensitive() -> None:
    """Verify that count occurrences is case insensitive behaves the way the team expects."""
    assert _count_occurrences("Foo foo FOO", "foo") == 3


def test_parse_modes_all_and_subset() -> None:
    """Verify that parse modes all and subset behaves the way the team expects."""
    assert parse_modes("all") == (
        "raw_mentions",
        "unique_documents",
        "unique_chunks",
        "unique_rows",
    )
    assert parse_modes("raw_mentions,unique_chunks") == (
        "raw_mentions",
        "unique_chunks",
    )


def test_load_target_set_preserves_audited_targets() -> None:
    """Verify that load target set preserves audited targets behaves the way the team expects."""
    lane_name, lane_date, targets = load_target_set(
        REPO_ROOT / "tests" / "golden_eval" / "count_benchmark_targets_2026-04-15.json"
    )
    assert lane_name == "count_benchmark_tranche1_frozen"
    assert lane_date == "2026-04-15 MDT"
    selected = select_targets(targets, include_deferred=False)
    assert [t.target for t in selected] == [
        "Eareckson Air Station, Shemya, AK",
        "Pituffik Space Base",
        "IGSI-754",
        "IGSI-755",
        "IGSI-1803",
        "IGSI-1804",
        "IGSI-1805",
    ]


def test_load_predictions_accepts_results_shape(tmp_path: Path) -> None:
    """Verify that load predictions accepts results shape behaves the way the team expects."""
    path = tmp_path / "predictions.json"
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "target": "IGSI-754",
                        "counts": {
                            "raw_mentions": 28,
                            "unique_documents": 20,
                            "unique_chunks": 26,
                            "unique_rows": 0,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    loaded = load_predictions(path)
    assert loaded["IGSI-754"] == {
        "raw_mentions": 28,
        "unique_documents": 20,
        "unique_chunks": 26,
        "unique_rows": 0,
    }


def test_compare_count_maps_reports_exact_and_abs_error() -> None:
    """Verify that compare count maps reports exact and abs error behaves the way the team expects."""
    exact, max_abs_error, per_mode = compare_count_maps(
        {
            "raw_mentions": 28,
            "unique_documents": 20,
            "unique_chunks": 26,
            "unique_rows": 0,
        },
        {
            "raw_mentions": 28,
            "unique_documents": 19,
            "unique_chunks": 26,
            "unique_rows": 0,
        },
        ("raw_mentions", "unique_documents", "unique_chunks", "unique_rows"),
    )
    assert exact is False
    assert max_abs_error == 1
    assert per_mode["raw_mentions"]["exact_match"] is True
    assert per_mode["unique_documents"]["exact_match"] is False
    assert per_mode["unique_documents"]["abs_error"] == 1


def test_summarize_results_counts_prediction_hits() -> None:
    """Verify that summarize results counts prediction hits behaves the way the team expects."""
    _, _, targets = load_target_set(
        REPO_ROOT / "tests" / "golden_eval" / "count_benchmark_targets_2026-04-15.json"
    )
    audited = select_targets(targets, include_deferred=False)
    first = audited[0]
    second = audited[1]
    fake_results = [
        type(
            "R",
            (),
            {
                "expected": first.expected,
                "expected_exact_match": True,
                "predicted_counts": {"raw_mentions": 1, "unique_documents": 1, "unique_chunks": 1, "unique_rows": 0},
                "prediction_exact_match": True,
                "prediction_max_abs_error": 0,
                "prediction_per_mode": {
                    "raw_mentions": {"exact_match": True},
                    "unique_documents": {"exact_match": True},
                    "unique_chunks": {"exact_match": True},
                    "unique_rows": {"exact_match": True},
                },
            },
        )(),
        type(
            "R",
            (),
            {
                "expected": second.expected,
                "expected_exact_match": False,
                "predicted_counts": {"raw_mentions": 300, "unique_documents": 170, "unique_chunks": 358, "unique_rows": 0},
                "prediction_exact_match": False,
                "prediction_max_abs_error": 83,
                "prediction_per_mode": {
                    "raw_mentions": {"exact_match": False},
                    "unique_documents": {"exact_match": False},
                    "unique_chunks": {"exact_match": True},
                    "unique_rows": {"exact_match": True},
                },
            },
        )(),
    ]
    summary = summarize_results(fake_results, parse_modes("all"))
    assert summary["selected_targets"] == 2
    assert summary["expected_total"] == 2
    assert summary["expected_exact"] == 1
    assert summary["prediction_total"] == 2
    assert summary["prediction_exact"] == 1
    assert summary["prediction_max_abs_error"] == 83
    assert summary["per_mode_prediction_exact"]["raw_mentions"] == 1
    assert summary["per_mode_prediction_exact"]["unique_chunks"] == 2


def test_entity_exact_counts_use_exact_text_and_sources() -> None:
    """Verify that entity exact counts use exact text and sources behaves the way the team expects."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE entities (
            source_path TEXT,
            chunk_id TEXT,
            text TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO entities VALUES (?, ?, ?)",
        [
            ("doc1", "chunk1", "IGSI-1805"),
            ("doc1", "chunk2", "IGSI-1805"),
            ("doc2", "chunk3", "IGSI-1805"),
        ],
    )
    counts, sample_paths, sample_chunks = _count_entity_exact(conn, "IGSI-1805")
    assert counts == {
        "raw_mentions": 3,
        "unique_documents": 2,
        "unique_chunks": 3,
        "unique_rows": 0,
    }
    assert sample_paths[:2] == ["doc1", "doc1"]
    assert sample_chunks[:2] == ["chunk1", "chunk2"]


def test_row_exact_counts_headers_and_values() -> None:
    """Verify that row exact counts headers and values behaves the way the team expects."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE extracted_tables (
            source_path TEXT,
            table_id TEXT,
            row_index INTEGER,
            headers TEXT,
            values_json TEXT,
            chunk_id TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO extracted_tables VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("doc1", "t1", 1, "['DD Form 1149']", "['DD Form 1149']", "chunkA"),
            ("doc2", "t2", 2, "['Other']", "['DD Form 1149']", ""),
        ],
    )
    counts, sample_paths, sample_chunks = _count_row_exact(conn, "DD Form 1149")
    assert counts == {
        "raw_mentions": 3,
        "unique_documents": 2,
        "unique_chunks": 1,
        "unique_rows": 2,
    }
    assert sample_paths == ["doc1", "doc2"]
    assert sample_chunks == ["chunkA"]
