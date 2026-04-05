"""
Entity retriever — searches entity and relationship stores.

Handles ENTITY, AGGREGATE, and TABULAR query types by dispatching
to the appropriate SQLite store methods.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.store.entity_store import EntityStore, EntityResult, TableResult
from src.store.relationship_store import RelationshipStore, RelationshipResult
from src.query.query_router import QueryClassification

logger = logging.getLogger(__name__)


@dataclass
class StructuredResult:
    """
    Result from structured (non-vector) retrieval.

    Formatted as context text for the LLM generator, with provenance.
    """

    context_text: str
    sources: list[str]
    result_count: int
    query_path: str


class EntityRetriever:
    """
    Retrieves from entity store, relationship store, and table store.

    Routes based on QueryClassification.query_type:
      ENTITY    → entity lookup + relationship traversal
      AGGREGATE → entity aggregation (count + list sources)
      TABULAR   → table row query
    """

    def __init__(
        self,
        entity_store: EntityStore,
        relationship_store: RelationshipStore,
        min_confidence: float = 0.7,
    ):
        self.entity_store = entity_store
        self.relationship_store = relationship_store
        self.min_confidence = min_confidence

    def search(self, classification: QueryClassification) -> StructuredResult | None:
        """
        Search structured stores based on classification.

        Returns formatted context for the LLM, or None if no results.
        """
        qtype = classification.query_type

        if qtype == "ENTITY":
            return self._entity_lookup(classification)
        elif qtype == "AGGREGATE":
            return self._aggregate_query(classification)
        elif qtype == "TABULAR":
            return self._tabular_query(classification)
        else:
            return None

    def _entity_lookup(self, c: QueryClassification) -> StructuredResult | None:
        """Direct entity lookup + relationship traversal."""
        parts = []
        sources = set()

        # Entity lookup
        entity_type = c.entity_type if c.entity_type else None
        text_pattern = f"%{c.text_pattern}%" if c.text_pattern else None
        source_filter = c.site_filter if c.site_filter else None

        entities = self.entity_store.lookup_entities(
            entity_type=entity_type,
            text_pattern=text_pattern,
            source_path=source_filter,
            min_confidence=self.min_confidence,
            limit=20,
        )

        if entities:
            parts.append("## Entity Results\n")
            for e in entities:
                parts.append(
                    f"- **{e.entity_type}**: {e.text} "
                    f"(confidence: {e.confidence:.1f}, source: {e.source_path})\n"
                    f"  Context: {e.context}\n"
                )
                sources.add(e.source_path)

        # Relationship traversal — search for related entities
        search_text = c.text_pattern or c.site_filter or c.original_query
        if search_text:
            rels = self.relationship_store.find_related(
                text=search_text,
                min_confidence=self.min_confidence,
                limit=20,
            )

            if rels:
                parts.append("\n## Relationship Results\n")
                for r in rels:
                    parts.append(
                        f"- {r.subject_text} —[{r.predicate}]→ {r.object_text} "
                        f"(confidence: {r.confidence:.1f}, source: {r.source_path})\n"
                        f"  Context: {r.context}\n"
                    )
                    sources.add(r.source_path)

        if not parts:
            return None

        return StructuredResult(
            context_text="".join(parts),
            sources=list(sources),
            result_count=len(entities) + len(rels) if entities else 0,
            query_path="ENTITY",
        )

    def _aggregate_query(self, c: QueryClassification) -> StructuredResult | None:
        """Count and list entity occurrences across documents."""
        entity_type = c.entity_type if c.entity_type else None
        text_pattern = f"%{c.text_pattern}%" if c.text_pattern else None

        agg = self.entity_store.aggregate_entity(
            entity_type=entity_type,
            text_pattern=text_pattern,
            min_confidence=self.min_confidence,
        )

        if not agg:
            return None

        parts = ["## Aggregation Results\n\n"]
        sources = set()

        for item in agg:
            parts.append(
                f"- **{item['text']}**: found {item['count']} time(s) "
                f"across {len(item['sources'])} source(s)\n"
                f"  Sources: {', '.join(item['sources'])}\n"
            )
            sources.update(item["sources"])

        parts.append(f"\n**Total unique matches: {len(agg)}**\n")

        return StructuredResult(
            context_text="".join(parts),
            sources=list(sources),
            result_count=len(agg),
            query_path="AGGREGATE",
        )

    def _tabular_query(self, c: QueryClassification) -> StructuredResult | None:
        """Query extracted table rows."""
        # Use text_pattern to search values, site_filter for source
        rows = self.entity_store.query_tables(
            source_pattern=c.site_filter if c.site_filter else None,
            value_contains=c.text_pattern if c.text_pattern else None,
            limit=30,
        )

        if not rows:
            return None

        parts = ["## Table Results\n\n"]
        sources = set()

        for row in rows:
            header_str = " | ".join(row.headers)
            value_str = " | ".join(row.values)
            parts.append(f"| {header_str} |\n| {value_str} |\n")
            parts.append(f"(Source: {row.source_path})\n\n")
            sources.add(row.source_path)

        return StructuredResult(
            context_text="".join(parts),
            sources=list(sources),
            result_count=len(rows),
            query_path="TABULAR",
        )
