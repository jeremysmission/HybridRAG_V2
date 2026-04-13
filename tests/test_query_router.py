"""
Focused unit tests for the current query router behavior.

These tests lock down the typed-routing baseline that the
family-aware routing plan will build on top of.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.query.query_router import QueryRouter


@dataclass
class _StubResponse:
    text: str


class _UnavailableLLM:
    available = False
    provider = "ollama"


class _StubLLM:
    def __init__(self, payload: dict, provider: str = "ollama"):
        self.available = True
        self.provider = provider
        self._payload = payload

    def call(self, **kwargs):  # pragma: no cover - signature compatibility only
        return _StubResponse(text=json.dumps(self._payload))


def test_fallback_routes_po_status_to_tabular():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What's the status of PO-2024-0501?")

    assert result.query_type == "TABULAR"
    assert result.text_pattern == "PO-2024-0501"
    assert result.entity_type == ""
    assert result.site_filter == ""


def test_fallback_routes_contact_lookup_to_entity():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What is Mike Torres's email?")

    assert result.query_type == "ENTITY"
    assert result.entity_type == "CONTACT"
    assert result.text_pattern == "Mike Torres"


def test_fallback_routes_part_count_query_to_aggregate():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("How many times has ARC-4471 failed?")

    assert result.query_type == "AGGREGATE"
    assert result.entity_type == "PART"
    assert result.text_pattern == "ARC-4471"


def test_fallback_routes_procedure_query_to_semantic():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("Describe the calibration procedure for the backup transmitter.")

    assert result.query_type == "SEMANTIC"
    assert result.sub_queries == []
    assert result.expanded_query == result.original_query


def test_ollama_guard_overrides_type_for_high_signal_tabular_query():
    payload = {
        "query_type": "SEMANTIC",
        "sub_queries": [],
        "entity_filters": {
            "entity_type": "",
            "text_pattern": "PO-2024-0501",
            "site_filter": "",
        },
        "expanded_query": "summarize procurement activity",
        "reasoning": "llm guess",
    }
    router = QueryRouter(_StubLLM(payload, provider="ollama"))

    result = router.classify("What's the status of PO-2024-0501?")

    assert result.query_type == "TABULAR"
    assert result.text_pattern == "PO-2024-0501"
    assert "guard_override=type=TABULAR" in result.reasoning


def test_ollama_guard_builds_multi_hop_subqueries():
    payload = {
        "query_type": "SEMANTIC",
        "sub_queries": [],
        "entity_filters": {
            "entity_type": "",
            "text_pattern": "",
            "site_filter": "",
        },
        "expanded_query": "generic rewrite",
        "reasoning": "llm guess",
    }
    router = QueryRouter(_StubLLM(payload, provider="ollama"))

    result = router.classify(
        "Who is the point of contact for the site where ARC-4471 was ordered?"
    )

    assert result.query_type == "COMPLEX"
    assert result.expanded_query == (
        "ARC-4471 destination site requestor point of contact purchase order contact"
    )
    assert [sq.query_type for sq in result.sub_queries] == ["SEMANTIC", "SEMANTIC"]
    assert "ARC-4471 destination site requestor purchase order status" == result.sub_queries[0].query_text
    assert "point of contact site requestor contact" == result.sub_queries[1].query_text


def test_fallback_routes_corpus_tabular_lookup_to_tabular():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What does the enterprise program Weekly Hours Variance report show?")

    assert result.query_type == "TABULAR"


def test_fallback_routes_corpus_aggregate_inventory_to_aggregate():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What procurement records exist for the monitoring system Sustainment option year 2 period?")

    assert result.query_type == "AGGREGATE"


def test_fallback_routes_corpus_entity_single_record_lookup_to_entity():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("Which CDRL is A002 and what maintenance service reports have been submitted under it?")

    assert result.query_type == "ENTITY"


def test_fallback_routes_budget_query_to_tabular():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What is the LDI suborganization 2024 budget for ORG enterprise program and how is it organized by option year?")

    assert result.query_type == "TABULAR"


def test_fallback_routes_documented_under_query_to_aggregate():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What are the configuration change requests documented under CDRL A050?")

    assert result.query_type == "AGGREGATE"


def test_fallback_routes_tracker_query_to_tabular():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What is the Part Failure Tracker and what parts have been replaced?")

    assert result.query_type == "TABULAR"


def test_fallback_routes_report_dated_query_to_entity():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify(
        "What is documented in the enterprise program Weekly Hours Variance report dated 2025-01-10?"
    )

    assert result.query_type == "ENTITY"


def test_deterministic_guard_overrides_stubbed_llm_for_tabular_query():
    payload = {
        "query_type": "SEMANTIC",
        "sub_queries": [],
        "entity_filters": {
            "entity_type": "",
            "text_pattern": "",
            "site_filter": "",
        },
        "expanded_query": "summarize the spreadsheet",
        "reasoning": "llm guess",
    }
    router = QueryRouter(_StubLLM(payload, provider="api"))

    result = router.classify("Show me the enterprise program Weekly Hours Variance report for the week ending 2024-12-31.")

    assert result.query_type == "TABULAR"
    assert "guard_override=type=TABULAR" in result.reasoning


def test_deterministic_guard_applies_expansion_on_api_provider():
    payload = {
        "query_type": "SEMANTIC",
        "sub_queries": [],
        "entity_filters": {
            "entity_type": "",
            "text_pattern": "",
            "site_filter": "",
        },
        "expanded_query": "summarize the spreadsheet",
        "reasoning": "llm guess",
    }
    router = QueryRouter(_StubLLM(payload, provider="api"))

    result = router.classify(
        "Show me the enterprise program Weekly Hours Variance report for the week ending 2024-12-31."
    )

    assert result.query_type == "TABULAR"
    assert result.expanded_query == (
        "enterprise program Weekly Hours Variance report week ending 2024-12-31"
    )
    assert "guard_override=type=TABULAR,expanded_query" in result.reasoning


def test_deterministic_guard_applies_complex_subqueries_on_api_provider():
    payload = {
        "query_type": "SEMANTIC",
        "sub_queries": [],
        "entity_filters": {
            "entity_type": "",
            "text_pattern": "",
            "site_filter": "",
        },
        "expanded_query": "generic rewrite",
        "reasoning": "llm guess",
    }
    router = QueryRouter(_StubLLM(payload, provider="api"))

    result = router.classify(
        "Who is the point of contact for the site where ARC-4471 was ordered?"
    )

    assert result.query_type == "COMPLEX"
    assert [sq.query_type for sq in result.sub_queries] == ["SEMANTIC", "SEMANTIC"]


@pytest.mark.parametrize(
    "query, expected_fragment",
    [
        (
            "What does the Program Management Plan (CDRL A008) say about contract deliverables and schedules?",
            "guard_override=type=SEMANTIC",
        ),
        (
            "What are the Contingency Plan Report and After Action Review templates used for?",
            "guard_override=type=SEMANTIC",
        ),
        (
            "What is in the System Engineering Management Plan (CDRL A013) for the enterprise program?",
            "guard_override=type=SEMANTIC",
        ),
        (
            "What is the Integrated Logistics Support Plan (CDRL A023) and what does it cover?",
            "guard_override=type=SEMANTIC",
        ),
        (
            "What is the status of the enterprise program follow-on contract Sources Sought response?",
            "guard_override=type=SEMANTIC",
        ),
        (
            "What are the cost and schedule variances reported in the latest Program Management Review?",
            "guard_override=type=SEMANTIC",
        ),
    ],
)
def test_deterministic_guard_keeps_document_content_questions_semantic_on_api_provider(
    query, expected_fragment
):
    payload = {
        "query_type": "ENTITY",
        "sub_queries": [],
        "entity_filters": {
            "entity_type": "",
            "text_pattern": "",
            "site_filter": "",
        },
        "expanded_query": "llm guess",
        "reasoning": "llm guess",
    }
    router = QueryRouter(_StubLLM(payload, provider="api"))

    result = router.classify(query)

    assert result.query_type == "SEMANTIC"
    assert expected_fragment in result.reasoning


def test_deterministic_guard_does_not_override_scan_report_contain_query():
    payload = {
        "query_type": "ENTITY",
        "sub_queries": [],
        "entity_filters": {
            "entity_type": "",
            "text_pattern": "",
            "site_filter": "",
        },
        "expanded_query": "llm guess",
        "reasoning": "llm guess",
    }
    router = QueryRouter(_StubLLM(payload, provider="api"))

    result = router.classify(
        "What does the monitoring system Scan Report from May 2023 (IGSI-965) contain?"
    )

    assert result.query_type == "ENTITY"


def test_fallback_routes_deliverable_lookup_to_entity():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What is deliverable IGSI-965?")

    assert result.query_type == "ENTITY"


def test_fallback_routes_shipment_question_to_entity():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify(
        "What Thule monitoring system ASV shipment was sent in July 2024 and what was its travel mode?"
    )

    assert result.query_type == "ENTITY"
    assert "packing list" in result.expanded_query.lower()
    assert "2024_07" in result.expanded_query.lower()


def test_fallback_routes_which_listing_query_to_aggregate():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("Which shipments occurred in August 2025?")

    assert result.query_type == "AGGREGATE"


def test_fallback_routes_bill_of_materials_query_to_tabular():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify("What is the Priced Bill of Materials in CDRL A014 for the enterprise program?")

    assert result.query_type == "TABULAR"
    assert "deliverables report" in result.expanded_query.lower()
    assert "pbom" in result.expanded_query.lower()


def test_cdrl_management_plan_query_adds_deliverable_bias_to_expanded_query():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify(
        "What does the Program Management Plan (CDRL A008) say about contract deliverables and schedules?"
    )

    assert result.query_type == "SEMANTIC"
    assert "deliverables report" in result.expanded_query.lower()
    assert "systems management plan" in result.expanded_query.lower()


def test_exact_date_shipment_query_adds_path_friendly_date_tokens():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify(
        "What was in the Azores return equipment shipment of 2024-06-14?"
    )

    assert result.query_type == "ENTITY"
    assert "packing list" in result.expanded_query.lower()
    assert "2024_06_14" in result.expanded_query.lower()


def test_compare_query_stays_semantic():
    router = QueryRouter(_UnavailableLLM())

    result = router.classify(
        "What is the difference between the enterprise program Weekly Hours Variance reports and the enterprise program PMR decks for tracking program health?"
    )

    assert result.query_type == "SEMANTIC"
