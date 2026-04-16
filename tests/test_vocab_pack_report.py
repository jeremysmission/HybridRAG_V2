"""Tests for the read-only vocabulary pack report / lookup/scan helper."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vocab.pack_reports import (  # noqa: E402
    build_cross_pack_alias_collisions,
    build_vocab_report,
    find_scan_hits,
    format_vocab_report,
)
from src.vocab.pack_loader import load_all_packs  # noqa: E402

SEED_DIR = ROOT / "config" / "vocab_packs"


def test_vocab_report_summarizes_seed_packs() -> None:
    """Verify that vocab report summarizes seed packs behaves the way the team expects."""
    report = build_vocab_report(SEED_DIR)
    assert report["pack_count"] == 4
    assert report["entry_count"] > 0
    assert report["validation"]
    assert all(not errors for errors in report["validation"].values())

    text = format_vocab_report(report)
    assert "Vocabulary Pack Report" in text
    assert "program_management_terms" in text
    assert "government_forms" in text


def test_vocab_report_lookup_hits_real_seed_terms() -> None:
    """Verify that vocab report lookup hits real seed terms behaves the way the team expects."""
    report = build_vocab_report(SEED_DIR, lookups=["DD1149", "CPI", "Patrick AFB"])

    dd_hits = report["lookup_hits"]["DD1149"]
    cpi_hits = report["lookup_hits"]["CPI"]
    patrick_hits = report["lookup_hits"]["Patrick AFB"]

    assert dd_hits and dd_hits[0]["pack_id"] == "government_forms"
    assert dd_hits[0]["canonical"] == "DD Form 1149"
    assert cpi_hits and cpi_hits[0]["pack_id"] == "program_management_terms"
    assert cpi_hits[0]["canonical"] == "CPI"
    assert patrick_hits and patrick_hits[0]["pack_id"] == "locations_bases"
    assert patrick_hits[0]["canonical"] == "Patrick Space Force Base"

    text = format_vocab_report(report)
    assert "Lookups:" in text
    assert "DD1149" in text
    assert "Patrick AFB" in text


def test_vocab_report_json_roundtrip() -> None:
    """Verify that vocab report json roundtrip behaves the way the team expects."""
    report = build_vocab_report(SEED_DIR, lookups=["CPI"])
    payload = json.dumps(report, sort_keys=True)
    decoded = json.loads(payload)
    assert decoded["lookup_summary"]["CPI"]["hit_count"] >= 1


def test_vocab_report_surfaces_cross_pack_alias_collisions() -> None:
    """Verify that vocab report surfaces cross pack alias collisions behaves the way the team expects."""
    packs = load_all_packs(SEED_DIR)
    collisions = build_cross_pack_alias_collisions(packs)
    assert "poam" in collisions
    targets = {(item["pack_id"], item["term_id"]) for item in collisions["poam"]}
    assert ("cyber_terms", "cyber.rmf.poam") in targets
    assert ("program_management_terms", "pmi.risk.poam") in targets


def test_find_scan_hits_finds_real_seed_terms_in_text() -> None:
    """Verify that find scan hits finds real seed terms in text behaves the way the team expects."""
    packs = load_all_packs(SEED_DIR)
    hits = find_scan_hits(
        packs,
        "Patrick AFB uses DD1149 and CPI tracking.",
    )
    keys = {(hit.pack_id, hit.term_id) for hit in hits}
    assert ("locations_bases", "locations.spaceforce.patrick_sfb") in keys
    assert ("government_forms", "forms.dd.1149") in keys
    assert ("program_management_terms", "pmi.evm.cpi") in keys


def test_find_scan_hits_marks_ambiguous_aliases() -> None:
    """Verify that find scan hits marks ambiguous aliases behaves the way the team expects."""
    packs = load_all_packs(SEED_DIR)
    hits = find_scan_hits(packs, "POAM review remains open.")
    assert len(hits) == 2
    assert all(hit.ambiguous for hit in hits)
    assert {hit.pack_id for hit in hits} == {
        "cyber_terms",
        "program_management_terms",
    }


def test_find_scan_hits_respects_boundaries() -> None:
    """Verify that find scan hits respects boundaries behaves the way the team expects."""
    packs = load_all_packs(SEED_DIR)
    hits = find_scan_hits(packs, "The CPIX token should not trigger CPI.")
    assert len(hits) == 1
    assert hits[0].canonical == "CPI"
    assert hits[0].matched_text == "CPI"


def test_vocab_report_includes_text_scan_summary() -> None:
    """Verify that vocab report includes text scan summary behaves the way the team expects."""
    report = build_vocab_report(SEED_DIR, scan_text="Patrick AFB filed DD1149.")
    assert report["text_scan_summary"]["hit_count"] == 2
    assert report["text_scan_hits"]
    text = format_vocab_report(report)
    assert "Text scan:" in text
    assert "Patrick AFB" in text
