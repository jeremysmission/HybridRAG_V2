"""Tests for deterministic vocab tagging helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vocab.tagging import build_tagging_result, format_tagging_result  # noqa: E402

SEED_DIR = ROOT / "config" / "vocab_packs"


def test_build_tagging_result_extracts_expected_families() -> None:
    """Verify that build tagging result extracts expected families behaves the way the team expects."""
    result = build_tagging_result(
        SEED_DIR,
        "Patrick AFB uses DD1149 and EVM tracking.",
    )
    assert "government_form_document" in result["doc_family"]
    assert "site_document" in result["doc_family"]
    assert "program_management_document" in result["doc_family"]
    assert result["form_family"][0]["canonical"] == "DD Form 1149"
    assert result["site_family"][0]["canonical"] == "Patrick Space Force Base"
    assert result["vocab_domain_hits"]["government_forms"]["hit_count"] >= 1
    assert result["vocab_domain_hits"]["locations_bases"]["hit_count"] >= 1
    assert result["vocab_domain_hits"]["pmi_evm"]["hit_count"] >= 1


def test_build_tagging_result_surfaces_ambiguous_aliases() -> None:
    """Verify that build tagging result surfaces ambiguous aliases behaves the way the team expects."""
    result = build_tagging_result(SEED_DIR, "POAM review is still open.")
    assert len(result["ambiguous_alias_warnings"]) == 1
    warning = result["ambiguous_alias_warnings"][0]
    assert warning["alias"] == "poam"
    targets = {(item["pack_id"], item["term_id"]) for item in warning["candidates"]}
    assert ("cyber_terms", "cyber.rmf.poam") in targets
    assert ("program_management_terms", "pmi.risk.poam") in targets


def test_build_tagging_result_flags_cyber_document() -> None:
    """Verify that build tagging result flags cyber document behaves the way the team expects."""
    result = build_tagging_result(SEED_DIR, "ACAS and STIG checks remain active.")
    assert "cyber_document" in result["doc_family"]
    assert result["vocab_domain_hits"]["cyber"]["hit_count"] >= 2


def test_format_tagging_result_contains_core_sections() -> None:
    """Verify that format tagging result contains core sections behaves the way the team expects."""
    result = build_tagging_result(
        SEED_DIR,
        "Patrick AFB uses DD1149 and POAM tracking.",
    )
    text = format_tagging_result(result)
    assert "Deterministic Vocab Tags" in text
    assert "Doc family:" in text
    assert "Form family:" in text
    assert "Site family:" in text
    assert "Ambiguous alias warnings:" in text
