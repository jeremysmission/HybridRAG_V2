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


def test_family_signal_mapping_expands_cdrl_family_codes_for_fallback_queries():
    qdef = {
        "query_id": "PQ-336",
        "expected_document_family": "CDRLs",
    }

    signals = _family_signals_for_query(qdef)

    assert "a009" in signals
    assert "monthly status" in signals
    assert _match_in_family(
        "A009 - Monthly Status Report/47QFRA22F0009_IGSI-2497_Monthly-Status-Report.docx",
        "",
        signals,
    )


def test_family_signal_mapping_expands_logistics_family_terms():
    qdef = {
        "query_id": "PQ-121",
        "expected_document_family": "Logistics",
    }

    signals = _family_signals_for_query(qdef)

    assert "dd250" in signals
    assert "shipment" in signals
    assert _match_in_family(
        "5.0 Logistics/DD250/Niger transfer artifact.pdf",
        "",
        signals,
    )


def test_family_signal_mapping_expands_cybersecurity_family_terms():
    qdef = {
        "query_id": "PQ-201",
        "expected_document_family": "Cybersecurity",
    }

    signals = _family_signals_for_query(qdef)

    assert "acas" in signals
    assert "authorization" in signals
    assert _match_in_family(
        "Cyber/Authorization Package/ACAS security scan results.xlsx",
        "",
        signals,
    )

