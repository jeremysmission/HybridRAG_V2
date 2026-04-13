from scripts.audit_tier1_regex_gate import (
    SampleChunk,
    SampleSelection,
    build_extractor,
    classify_chunk_stratum,
    evaluate_curated_cases,
    evaluate_sample_selection,
)
from src.store.entity_store import Entity


def test_curated_regex_gate_passes():
    extractor = build_extractor()
    outcomes = evaluate_curated_cases(extractor)

    assert outcomes
    assert all(outcome.ok for outcome in outcomes), [
        (outcome.name, outcome.details) for outcome in outcomes if not outcome.ok
    ]


def test_chunk_strata_classification_uses_risk_buckets():
    extractor = build_extractor()

    assert classify_chunk_stratum("Control AS-5021 applies.", extractor) == "security_candidate"
    assert classify_chunk_stratum("Call 555-234-5678 now.", extractor) == "phone_candidate"
    assert classify_chunk_stratum("Installed ARC-4471 at Thule.", extractor) == "other"


def test_sample_selection_passes_when_outputs_are_clean():
    extractor = build_extractor()
    selection = SampleSelection(
        chunks=[
            SampleChunk(
                chunk_id="c1",
                source_path="docs/logistics.txt",
                text="Backordered part PS-800 at Granite Peak.",
                stratum="other",
            ),
            SampleChunk(
                chunk_id="c2",
                source_path="docs/pm.txt",
                text="Raised PO 5000585586 to Grainger.",
                stratum="other",
            ),
        ],
        scanned_chunks=2,
        sample_mode="stratified",
        stratum_seen={
            "security_candidate": 1,
            "phone_candidate": 0,
            "other": 1,
        },
    )

    outcome = evaluate_sample_selection(extractor, selection)

    assert outcome.ok
    assert outcome.dangerous_hits == []
    assert outcome.invalid_phone_hits == []
    assert any(item["text"] == "PS-800" for item in outcome.top_entities)


def test_sample_selection_flags_dangerous_outputs(monkeypatch):
    extractor = build_extractor()
    selection = SampleSelection(
        chunks=[
            SampleChunk(
                chunk_id="c1",
                source_path="docs/security.txt",
                text="Control text",
                stratum="security_candidate",
            ),
            SampleChunk(
                chunk_id="c2",
                source_path="docs/contacts.txt",
                text="Phone text",
                stratum="phone_candidate",
            ),
        ],
        scanned_chunks=2,
        sample_mode="stratified",
        stratum_seen={
            "security_candidate": 1,
            "phone_candidate": 1,
            "other": 0,
        },
    )

    scripted = {
        "c1": [
            Entity(
                entity_type="PART",
                text="AS-5021",
                raw_text="AS-5021",
                confidence=1.0,
                chunk_id="c1",
                source_path="docs/security.txt",
                context="Control AS-5021 applies.",
            )
        ],
        "c2": [
            Entity(
                entity_type="CONTACT",
                text="3333333344",
                raw_text="3333333344",
                confidence=1.0,
                chunk_id="c2",
                source_path="docs/contacts.txt",
                context="bad phone",
            )
        ],
    }

    def fake_extract(text, chunk_id, source_path):
        return scripted[chunk_id]

    monkeypatch.setattr(extractor, "extract", fake_extract)
    outcome = evaluate_sample_selection(extractor, selection)

    assert not outcome.ok
    assert any("AS-5021" in hit for hit in outcome.dangerous_hits)
    assert any("3333333344" in hit for hit in outcome.invalid_phone_hits)
