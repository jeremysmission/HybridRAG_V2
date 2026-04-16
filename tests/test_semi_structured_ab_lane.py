"""Test module for the semi structured ab lane behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.extraction.entity_extractor import (
    EntityExtractor,
    TABLE_PROMPT_MODE_BASELINE,
    TABLE_PROMPT_MODE_SYNOPSIS_ROW_PROVENANCE,
)
from src.extraction.tabular_substrate import build_table_prompt_context


FIXTURE_PACK_PATH = (
    V2_ROOT / "tests" / "tabular_eval" / "semi_structured_ab_subset_12_2026-04-15.json"
)


def _load_fixture_pack() -> list[dict]:
    """Load the fixture data used by the test."""
    return json.loads(FIXTURE_PACK_PATH.read_text(encoding="utf-8"))


class _FakeLLMResponse:
    """Small helper object used to keep test setup or expected results organized."""
    def __init__(self, text: str, input_tokens: int = 11, output_tokens: int = 7):
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _RecordingLLM:
    """Small helper object used to keep test setup or expected results organized."""
    available = True
    max_tokens = 4096

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, *, prompt: str, system_prompt: str, temperature: float, max_tokens: int, response_format: dict):
        self.prompts.append(prompt)
        return _FakeLLMResponse('{"entities": [], "relationships": [], "table_rows": []}')


class TestSemiStructuredABFixturePack:
    """Small helper object used to keep test setup or expected results organized."""
    def test_fixture_pack_has_expected_split(self):
        pack = _load_fixture_pack()
        assert len(pack) == 12
        buckets = {}
        for fixture in pack:
            buckets[fixture["bucket"]] = buckets.get(fixture["bucket"], 0) + 1
        assert buckets == {
            "clean_labeled": 4,
            "dense_semi_structured": 4,
            "ocr_damaged": 4,
        }

    @pytest.mark.parametrize("fixture", _load_fixture_pack(), ids=lambda item: item["fixture_id"])
    def test_prompt_context_builds_expected_shape(self, fixture: dict):
        context = build_table_prompt_context(
            text=fixture["text"],
            chunk_id=fixture["chunk_id"],
            source_path=fixture["source_path"],
        )
        assert context is not None
        assert context.table_mode == fixture["expected_table_mode"]
        assert context.detected_row_count >= fixture["min_rows"]
        assert context.row_provenance_lines
        if fixture.get("expected_family"):
            assert context.table_family == fixture["expected_family"]
        rendered = context.render()
        assert "[TABLE SYNOPSIS]" in rendered
        assert "row_provenance:" in rendered

    @pytest.mark.parametrize("fixture", _load_fixture_pack(), ids=lambda item: item["fixture_id"])
    def test_entity_extractor_selection_is_distinguishable_and_reproducible(self, fixture: dict):
        llm = _RecordingLLM()
        extractor = EntityExtractor(llm)

        default_result = extractor.extract_from_chunk(
            text=fixture["text"],
            chunk_id=fixture["chunk_id"],
            source_path=fixture["source_path"],
        )
        baseline_result = extractor.extract_from_chunk(
            text=fixture["text"],
            chunk_id=fixture["chunk_id"],
            source_path=fixture["source_path"],
            table_prompt_mode=TABLE_PROMPT_MODE_BASELINE,
        )
        treatment_result = extractor.extract_from_chunk(
            text=fixture["text"],
            chunk_id=fixture["chunk_id"],
            source_path=fixture["source_path"],
            table_prompt_mode=TABLE_PROMPT_MODE_SYNOPSIS_ROW_PROVENANCE,
        )
        repeat_treatment_result = extractor.extract_from_chunk(
            text=fixture["text"],
            chunk_id=fixture["chunk_id"],
            source_path=fixture["source_path"],
            table_prompt_mode=TABLE_PROMPT_MODE_SYNOPSIS_ROW_PROVENANCE,
        )

        default_prompt, baseline_prompt, treatment_prompt, repeat_treatment_prompt = llm.prompts
        assert default_prompt == baseline_prompt
        assert "[TABLE SYNOPSIS]" not in baseline_prompt
        assert "[TABLE SYNOPSIS]" in treatment_prompt
        assert treatment_prompt == repeat_treatment_prompt

        assert len(default_result.table_rows) >= fixture["min_rows"]
        assert len(baseline_result.table_rows) == len(treatment_result.table_rows)
        assert len(repeat_treatment_result.table_rows) == len(treatment_result.table_rows)
