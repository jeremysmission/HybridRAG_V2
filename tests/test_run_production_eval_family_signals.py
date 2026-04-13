from scripts.run_production_eval import _family_signals_for_query, _match_in_family


def test_family_signal_mapping_still_honors_legacy_25_query_overrides():
    qdef = {
        "query_id": "PQ-001",
        "expected_document_family": "Program Management",
    }

    signals = _family_signals_for_query(qdef)

    assert "cdrl" in signals
    assert "monthly status" in signals


def test_family_signal_mapping_falls_back_to_expected_document_family():
    qdef = {
        "query_id": "PQ-101",
        "expected_document_family": "Program Management",
    }

    signals = _family_signals_for_query(qdef)

    assert "program management" in signals
    assert "program" in signals
    assert "management" in signals
    assert _match_in_family("1.0 enterprise program/Program Management/foo", "", signals)

