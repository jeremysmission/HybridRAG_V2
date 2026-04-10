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

