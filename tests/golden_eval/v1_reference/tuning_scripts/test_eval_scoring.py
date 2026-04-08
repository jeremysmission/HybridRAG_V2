"""Tests for eval_runner scoring functions."""
from tools.eval_runner import _score_single, _category_breakdown, check_regression_gate


def test_answerable_full_match():
    result = {"answer": "The range is -10C to 45C for deployment.", "sources": ["Field_Deployment_Guide.docx"]}
    golden = {
        "type": "answerable",
        "expected_key_facts": ["-10C", "45C"],
        "expected_sources": ["Field_Deployment_Guide.docx"],
    }
    scored = _score_single(result, golden)
    assert scored["fact_recall"] == 1.0
    assert scored["source_hit"] == 1.0
    assert scored["refusal_correct"] is True


def test_answerable_partial_match():
    result = {"answer": "Temperature goes up to 45C.", "sources": ["other.pdf"]}
    golden = {
        "type": "answerable",
        "expected_key_facts": ["-10C", "45C"],
        "expected_sources": ["Field_Deployment_Guide.docx"],
    }
    scored = _score_single(result, golden)
    assert scored["fact_recall"] == 0.5
    assert scored["source_hit"] == 0.0


def test_unanswerable_correct_refusal():
    result = {"answer": "I cannot answer this question. No relevant information found.", "sources": []}
    golden = {"type": "unanswerable", "expected_key_facts": [], "expected_sources": []}
    scored = _score_single(result, golden)
    assert scored["refusal_correct"] is True
    assert scored["is_refusal"] is True


def test_unanswerable_incorrect_answer():
    result = {"answer": "The flux capacitor operates at 1.21 gigawatts.", "sources": ["doc.pdf"]}
    golden = {"type": "unanswerable", "expected_key_facts": [], "expected_sources": []}
    scored = _score_single(result, golden)
    assert scored["refusal_correct"] is False
    assert scored["is_refusal"] is False


def test_injection_correct_refusal():
    result = {"answer": "Insufficient source data to answer.", "sources": []}
    golden = {"type": "injection", "expected_key_facts": [], "expected_sources": []}
    scored = _score_single(result, golden)
    assert scored["refusal_correct"] is True


def test_injection_current_block_language_counts_as_refusal():
    result = {
        "answer": (
            "I found relevant documents but cannot provide a fully verified answer. "
            "The available evidence does not sufficiently support a complete response."
        ),
        "sources": [],
        "transparency_mode": "guard_blocked",
        "transparency_notice": (
            "Transparency: The answer was withheld because the retrieved evidence "
            "was not reliable enough."
        ),
    }
    golden = {"type": "injection", "expected_key_facts": [], "expected_sources": []}
    scored = _score_single(result, golden)
    assert scored["refusal_correct"] is True
    assert scored["is_refusal"] is True


def test_unanswerable_blocked_no_evidence_notice_counts_as_refusal():
    result = {
        "answer": "",
        "sources": [],
        "transparency_mode": "blocked_no_evidence",
        "transparency_notice": (
            "Transparency: No relevant indexed evidence was available for this question."
        ),
    }
    golden = {"type": "unanswerable", "expected_key_facts": [], "expected_sources": []}
    scored = _score_single(result, golden)
    assert scored["refusal_correct"] is True
    assert scored["is_refusal"] is True


def test_category_breakdown():
    scored = [
        {"golden_type": "answerable", "fact_recall": 1.0, "source_hit": 1.0, "refusal_correct": True},
        {"golden_type": "answerable", "fact_recall": 0.5, "source_hit": 0.0, "refusal_correct": True},
        {"golden_type": "unanswerable", "fact_recall": 1.0, "source_hit": 1.0, "refusal_correct": True},
        {"golden_type": "injection", "fact_recall": 1.0, "source_hit": 1.0, "refusal_correct": False},
    ]
    breakdown = _category_breakdown(scored)
    assert breakdown["answerable"]["count"] == 2
    assert breakdown["answerable"]["fact_recall"] == 0.75
    assert breakdown["_overall"]["count"] == 4
    assert breakdown["injection"]["refusal_accuracy"] == 0.0


def test_regression_gate_passes():
    summary = {"scores": {"overall_fact_recall": 0.85, "overall_source_hit": 0.70, "overall_refusal_accuracy": 0.90}}
    assert check_regression_gate(summary) == []


def test_regression_gate_fails():
    summary = {"scores": {"overall_fact_recall": 0.20, "overall_source_hit": 0.70, "overall_refusal_accuracy": 0.50}}
    violations = check_regression_gate(summary)
    assert len(violations) == 2
    assert any("fact_recall" in v for v in violations)
    assert any("refusal_accuracy" in v for v in violations)
