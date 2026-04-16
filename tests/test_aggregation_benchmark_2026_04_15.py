"""Test module for the aggregation benchmark 2026 04 15 behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from scripts.run_aggregation_benchmark_2026_04_15 import (  # noqa: E402
    DEFAULT_MANIFEST,
    load_answers,
    load_manifest,
    run_benchmark,
    score_answer,
)


def test_manifest_loads_and_has_expected_seed_set() -> None:
    """Verify that manifest loads and has expected seed set behaves the way the team expects."""
    manifest = load_manifest(DEFAULT_MANIFEST)
    assert manifest["benchmark_id"] == "aggregation_benchmark_2026-04-15"
    assert len(manifest["items"]) == 12

    families = {}
    ids = set()
    for item in manifest["items"]:
        ids.add(item["id"])
        families[item["family"]] = families.get(item["family"], 0) + 1

    assert ids == {f"AGG-{index:03d}" for index in range(1, 13)}
    assert families == {
        "confabulation": 4,
        "cross_slice_rollup": 1,
        "query_pack": 5,
        "hardtail": 2,
    }


@pytest.mark.parametrize(
    ("expected", "actual", "passed"),
    [
        (76, 76, True),
        (1367, "1,367 provider entities", True),
        (624, "There are 624 total response files", True),
        (39, "39 provider folders with 16 files each", True),
        (10, "9", False),
    ],
)
def test_score_answer_handles_numeric_variants(expected: int, actual: object, passed: bool) -> None:
    """Verify that score answer handles numeric variants behaves the way the team expects."""
    result, detail = score_answer(expected, actual)
    assert result is passed
    assert detail


def test_load_answers_accepts_object_and_array_shapes(tmp_path: Path) -> None:
    """Verify that load answers accepts object and array shapes behaves the way the team expects."""
    object_path = tmp_path / "answers_object.json"
    object_path.write_text(json.dumps({"AGG-001": 76, "AGG-002": {"answer": 39}}), encoding="utf-8")
    assert load_answers(object_path) == {"AGG-001": 76, "AGG-002": 39}

    array_path = tmp_path / "answers_array.json"
    array_path.write_text(
        json.dumps(
            [
                {"id": "AGG-001", "answer": 76},
                {"id": "AGG-002", "answer": "39"},
            ]
        ),
        encoding="utf-8",
    )
    assert load_answers(array_path) == {"AGG-001": 76, "AGG-002": "39"}


def test_self_check_passes_every_item() -> None:
    """Verify that self check passes every item behaves the way the team expects."""
    manifest = load_manifest(DEFAULT_MANIFEST)
    summary = run_benchmark(manifest, answers=None, self_check=True, manifest_path=DEFAULT_MANIFEST)

    assert summary.total_items == 12
    assert summary.pass_count == 12
    assert summary.fail_count == 0
    assert summary.gate_pass is True
    assert summary.mode == "self-check"


def test_scoring_against_candidate_answers(tmp_path: Path) -> None:
    """Verify that scoring against candidate answers behaves the way the team expects."""
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(
        json.dumps(
            {
                "AGG-001": "76",
                "AGG-002": 624,
                "AGG-003": 16,
                "AGG-004": 2197,
                "AGG-005": 1367,
                "AGG-006": 397,
                "AGG-007": 134,
                "AGG-008": 148,
                "AGG-009": 55,
                "AGG-010": 60,
                "AGG-011": 10,
                "AGG-012": 1,
            }
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(DEFAULT_MANIFEST)
    answers = load_answers(answers_path)
    summary = run_benchmark(manifest, answers=answers, manifest_path=DEFAULT_MANIFEST)

    assert summary.pass_count == 12
    assert summary.gate_pass is True
