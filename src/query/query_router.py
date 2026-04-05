"""
Query router — LLM-powered classification and dispatch.

Classifies incoming queries into types and routes to the appropriate
retrieval path(s). The router is the brain of the tri-store architecture.

Query types:
  SEMANTIC   — narrative/conceptual → LanceDB hybrid search
  ENTITY     — who/what factual lookup → entity store
  AGGREGATE  — counting/listing across docs → entity store aggregation
  TABULAR    — structured data lookup → table store
  COMPLEX    — multi-part → decompose into sub-queries, fan-out

The router also expands queries (synonyms, acronyms) for better recall.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

ROUTER_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "query_classification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["SEMANTIC", "ENTITY", "AGGREGATE", "TABULAR", "COMPLEX"],
                },
                "sub_queries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query_text": {"type": "string"},
                            "query_type": {
                                "type": "string",
                                "enum": ["SEMANTIC", "ENTITY", "AGGREGATE", "TABULAR"],
                            },
                        },
                        "required": ["query_text", "query_type"],
                        "additionalProperties": False,
                    },
                },
                "entity_filters": {
                    "type": "object",
                    "properties": {
                        "entity_type": {"type": "string"},
                        "text_pattern": {"type": "string"},
                        "site_filter": {"type": "string"},
                    },
                    "required": ["entity_type", "text_pattern", "site_filter"],
                    "additionalProperties": False,
                },
                "expanded_query": {"type": "string"},
                "reasoning": {"type": "string"},
            },
            "required": ["query_type", "sub_queries", "entity_filters",
                         "expanded_query", "reasoning"],
            "additionalProperties": False,
        },
    },
}

ROUTER_SYSTEM_PROMPT = """You are a query classifier for an IGS/NEXION military maintenance document system.

Classify the user's query into one of these types:

SEMANTIC — Narrative or conceptual questions answered by reading document text.
  Examples: "Describe the calibration procedure", "What was the transmitter power after repair?"

ENTITY — Direct factual lookup: who, what specific entity, contact info.
  Examples: "Who is the POC for Thule?", "What is Mike Torres's email?"

AGGREGATE — Counting, listing, or summarizing across multiple documents.
  Examples: "How many times has part ARC-4471 failed?", "List all parts consumed at Thule"

TABULAR — Structured data lookup from spreadsheets/tables (PO status, tracking).
  Examples: "What's the status of PO-2024-0501?", "What parts are backordered?"

COMPLEX — Multi-part question that needs decomposition into sub-queries.
  Examples: "Compare maintenance at Thule vs Riverside", "Who ordered parts for Cedar Ridge and what's their status?"

Also provide:
- sub_queries: For COMPLEX type, break into 2-4 simpler sub-queries with their types. For non-COMPLEX, return empty array.
- entity_filters: For ENTITY/AGGREGATE/TABULAR, provide filters to narrow the search. Use empty strings if not applicable.
- expanded_query: Rewrite the query with synonyms and acronyms expanded for better retrieval.
- reasoning: Brief explanation of why you chose this type."""


@dataclass
class QueryClassification:
    """Result from the query router."""

    query_type: str
    original_query: str
    expanded_query: str
    sub_queries: list[SubQuery] = field(default_factory=list)
    entity_type: str = ""
    text_pattern: str = ""
    site_filter: str = ""
    reasoning: str = ""


@dataclass
class SubQuery:
    """A decomposed sub-query for COMPLEX queries."""

    query_text: str
    query_type: str


class QueryRouter:
    """
    LLM-powered query classifier and dispatcher.

    Uses GPT-4o with structured outputs to classify queries
    and extract routing metadata.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def classify(self, query: str) -> QueryClassification:
        """
        Classify a query and return routing information.

        Falls back to rule-based routing if LLM is unavailable or classification fails.
        """
        if not self.llm.available:
            logger.warning("LLM unavailable — using rule-based fallback router")
            return self._fallback_classify(query)

        try:
            return self._llm_classify(query)
        except Exception as e:
            logger.error("Router classification failed: %s — using rule-based fallback router", e)
            return self._fallback_classify(query)

    def _llm_classify(self, query: str) -> QueryClassification:
        """Classify using LLM structured outputs."""
        llm_response = self.llm.call(
            prompt=query,
            system_prompt=ROUTER_SYSTEM_PROMPT,
            temperature=0,
            max_tokens=1024,
            response_format=ROUTER_SCHEMA,
        )

        parsed = json.loads(llm_response.text)

        sub_queries = [
            SubQuery(query_text=sq["query_text"], query_type=sq["query_type"])
            for sq in parsed.get("sub_queries", [])
        ]

        filters = parsed.get("entity_filters", {})

        return QueryClassification(
            query_type=parsed["query_type"],
            original_query=query,
            expanded_query=parsed.get("expanded_query", query),
            sub_queries=sub_queries,
            entity_type=filters.get("entity_type", ""),
            text_pattern=filters.get("text_pattern", ""),
            site_filter=filters.get("site_filter", ""),
            reasoning=parsed.get("reasoning", ""),
        )

    def _fallback_classify(self, query: str) -> QueryClassification:
        """
        Rule-based fallback when LLM is unavailable.

        Uses keyword heuristics for basic routing.
        """
        q = query.lower()

        if any(w in q for w in ["how many", "count", "list all", "total"]):
            qtype = "AGGREGATE"
        elif any(w in q for w in ["who is", "who are", "poc for", "contact for", "email", "phone"]):
            qtype = "ENTITY"
        elif any(w in q for w in ["status of po", "purchase order", "backordered", "shipped"]):
            qtype = "TABULAR"
        elif any(w in q for w in ["compare", "vs ", "versus", "difference between"]):
            qtype = "COMPLEX"
        else:
            qtype = "SEMANTIC"

        return QueryClassification(
            query_type=qtype,
            original_query=query,
            expanded_query=query,
            reasoning="fallback: rule-based classification (LLM unavailable)",
        )
