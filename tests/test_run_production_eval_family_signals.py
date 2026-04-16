"""Test module for the run production eval family signals behavior. The checks here explain what the repository expects to keep working."""
from scripts.run_production_eval import _family_signals_for_query, _match_in_family


def test_family_signal_mapping_still_honors_legacy_25_query_overrides():
    """Verify that family signal mapping still honors legacy 25 query overrides behaves the way the team expects."""
    qdef = {
        "query_id": "PQ-001",
        "expected_document_family": "Program Management",
    }

    signals = _family_signals_for_query(qdef)

    assert "cdrl" in signals
    assert "monthly status" in signals


def test_family_signal_mapping_falls_back_to_expected_document_family():
    """Verify that family signal mapping falls back to expected document family behaves the way the team expects."""
    qdef = {
        "query_id": "PQ-101",
        "expected_document_family": "Program Management",
    }

    signals = _family_signals_for_query(qdef)

    assert "program management" in signals
    assert "program" in signals
    assert "management" in signals
    assert _match_in_family("1.0 enterprise program/Program Management/foo", "", signals)

