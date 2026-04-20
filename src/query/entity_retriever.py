"""
Entity retriever — searches entity and relationship stores.

Handles ENTITY, AGGREGATE, and TABULAR query types by dispatching
to the appropriate SQLite store methods.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field

from src.store.entity_store import EntityStore, EntityResult, TableResult
from src.store.relationship_store import RelationshipStore, RelationshipResult
from src.query.query_router import QueryClassification

logger = logging.getLogger(__name__)

# Stopwords excluded from query-term extraction for relationship/aggregate search
_QUERY_STOPWORDS = frozenset({
    "what", "which", "where", "when", "who", "how", "many", "much", "does",
    "did", "are", "is", "was", "were", "the", "a", "an", "and", "or", "for",
    "from", "into", "that", "this", "have", "has", "been", "with", "show",
    "me", "all", "any", "each", "every", "list", "find", "get", "tell",
    "about", "across", "under", "documented", "available", "exist", "exists",
    "filed", "submitted", "delivered", "processed", "active", "latest",
    "recent", "current", "specific", "particular",
    "enterprise", "program",  # sanitized domain terms
})


def _extract_query_terms(query: str, min_len: int = 3) -> list[str]:
    """Extract meaningful search terms from a query, excluding stopwords.

    Returns terms in order of specificity (longer/rarer terms first).
    Used to search the relationship and entity stores when the router
    doesn't provide an explicit text_pattern.
    """
    tokens = re.findall(r"[A-Za-z0-9][\w.-]*", query)
    terms = [
        t for t in tokens
        if len(t) >= min_len and t.lower() not in _QUERY_STOPWORDS
    ]
    # Sort by length descending — longer terms are more specific
    terms.sort(key=lambda t: -len(t))
    return terms[:8]  # cap to avoid query explosion


def _is_quality_relationship(r) -> bool:
    """Filter out phantom relationships at query time.

    Catches the 45% phantom rate identified in QA spot-check:
    single-word subjects, run-on captures, known noise terms.
    """
    subj = r.subject_text.strip()
    obj = r.object_text.strip()
    # Single-word subjects under 4 chars are usually phantoms
    if len(subj.split()) < 2 and len(subj) < 4:
        return False
    # Run-on captures (>60 chars) are sentence fragments, not entities
    if len(subj) > 60 or len(obj) > 60:
        return False
    # Known noise
    low = subj.lower()
    if low in ("assessed", "rivileges", "system", "hipaa", "cpu", "n/a"):
        return False
    return True
VALID_ENTITY_TYPES = {"PERSON", "PART", "SITE", "DATE", "PO", "ORG", "CONTACT"}


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
    stage_timings_ms: dict[str, int] = field(default_factory=dict)


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

    def resolve_site_contacts_for_part(self, query: str) -> StructuredResult | None:
        """Resolve multi-hop part -> site -> requestor/contact lookups from tables."""
        q = " ".join(query.lower().split())
        part_number = self._extract_part_number(query)
        if not part_number:
            return None
        if "point of contact" not in q and "contact for" not in q:
            return None
        if "site where" not in q and "location where" not in q:
            return None

        rows = self.entity_store.query_tables(value_contains=part_number, limit=200)
        if not rows:
            return None

        entries = []
        sources = set()
        for row in rows:
            mapping = self._row_to_mapping(row.headers, row.values)
            site = mapping.get("site") or mapping.get("destination")
            requestor = mapping.get("requestor") or mapping.get("notes", "")
            status = mapping.get("status", "")
            po = mapping.get("po") or mapping.get("po number", "")
            if not site:
                continue
            if site.strip().lower() == "depot stock":
                continue
            if requestor.strip().lower() == "logistics":
                continue
            if status.upper() in {"CANCELLED", "DEFECTIVE"}:
                continue
            entries.append(
                {
                    "site": site,
                    "requestor": requestor,
                    "status": status,
                    "po": po,
                    "source": row.source_path,
                }
            )
            sources.add(row.source_path)

        if not entries:
            return None

        def priority(entry: dict) -> tuple[int, int, str]:
            requestor = entry["requestor"].strip().lower()
            named_requestor = int(bool(requestor) and requestor != "logistics")
            status_order = {
                "IN TRANSIT": 0,
                "ORDERED": 1,
                "DELIVERED": 2,
                "BACKORDERED": 3,
            }
            status_rank = status_order.get(entry["status"].upper(), 9)
            return (-named_requestor, status_rank, entry["site"])

        ordered_entries = sorted(entries, key=priority)
        parts = [f"## Site Contacts For {part_number}\n\n"]
        for entry in ordered_entries:
            requestor = entry["requestor"] or "not stated"
            po = f", {entry['po']}" if entry["po"] else ""
            status = f" ({entry['status']})" if entry["status"] else ""
            parts.append(
                f"- {entry['site']}{status}{po}: point-of-contact candidate/requestor "
                f"{requestor} for {part_number}\n"
            )

        return StructuredResult(
            context_text="".join(parts),
            sources=sorted(sources),
            result_count=len(ordered_entries),
            query_path="COMPLEX",
        )

    def _entity_lookup(self, c: QueryClassification) -> StructuredResult | None:
        """Direct entity lookup + relationship traversal."""
        parts = []
        sources = set()
        rels: list[RelationshipResult] = []
        entity_lookup_ms = 0
        relationship_lookup_ms = 0

        # Entity lookup
        entity_type = self._normalize_entity_type(c.entity_type, c.original_query)
        text_pattern = f"%{c.text_pattern}%" if c.text_pattern else None
        source_filter = c.site_filter if c.site_filter else None

        entity_start = time.perf_counter()
        entities = self.entity_store.lookup_entities(
            entity_type=entity_type,
            text_pattern=text_pattern,
            source_path=source_filter,
            min_confidence=self.min_confidence,
            limit=20,
        )
        entity_lookup_ms = int((time.perf_counter() - entity_start) * 1000)

        if (
            not entities
            and entity_type == "CONTACT"
            and text_pattern
        ):
            entity_start = time.perf_counter()
            entities = self._lookup_contact_for_person(
                person_pattern=text_pattern,
                source_filter=source_filter,
            )
            entity_lookup_ms += int((time.perf_counter() - entity_start) * 1000)

        if not entities and text_pattern and entity_type is not None:
            entity_start = time.perf_counter()
            entities = self.entity_store.lookup_entities(
                entity_type=None,
                text_pattern=text_pattern,
                source_path=source_filter,
                min_confidence=self.min_confidence,
                limit=20,
            )
            entity_lookup_ms += int((time.perf_counter() - entity_start) * 1000)

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
        # Use explicit text_pattern/site_filter if available, otherwise
        # extract key terms from the query and search for each.
        rel_start = time.perf_counter()
        if c.text_pattern:
            rels = self.relationship_store.find_related(
                text=c.text_pattern, min_confidence=self.min_confidence, limit=20,
            )
        elif c.site_filter:
            rels = self.relationship_store.find_related(
                text=c.site_filter, min_confidence=self.min_confidence, limit=20,
            )
        else:
            # Extract key terms and search each one
            terms = _extract_query_terms(c.original_query)
            rels = []
            seen_rel_keys: set[tuple[str, str, str]] = set()
            for term in terms[:4]:  # search top 4 terms
                term_rels = self.relationship_store.find_related(
                    text=term, min_confidence=self.min_confidence, limit=10,
                )
                for r in term_rels:
                    if not _is_quality_relationship(r):
                        continue
                    key = (r.subject_text, r.predicate, r.object_text)
                    if key not in seen_rel_keys:
                        seen_rel_keys.add(key)
                        rels.append(r)
                if len(rels) >= 20:
                    break
            rels = rels[:20]
        relationship_lookup_ms = int((time.perf_counter() - rel_start) * 1000)

        if rels:
            parts.append("\n## Relationship Results\n")
            for r in rels:
                parts.append(
                    f"- {r.subject_text} --[{r.predicate}]-> {r.object_text} "
                    f"(confidence: {r.confidence:.1f}, source: {r.source_path})\n"
                    f"  Context: {r.context}\n"
                )
                sources.add(r.source_path)

        if not parts:
            return None

        return StructuredResult(
            context_text="".join(parts),
            sources=list(sources),
            result_count=len(entities) + len(rels),
            query_path="ENTITY",
            stage_timings_ms={
                "entity_lookup": entity_lookup_ms,
                "relationship_lookup": relationship_lookup_ms,
                "structured_lookup": entity_lookup_ms + relationship_lookup_ms,
            },
        )

    def _aggregate_query(self, c: QueryClassification) -> StructuredResult | None:
        """Count and list entity occurrences across documents."""
        aggregate_start = time.perf_counter()
        custom = (
            self._aggregate_sites_for_part(c)
            or self._aggregate_unique_part_numbers(c)
        )
        if custom:
            custom.stage_timings_ms.setdefault(
                "aggregate_lookup",
                int((time.perf_counter() - aggregate_start) * 1000),
            )
            custom.stage_timings_ms.setdefault(
                "structured_lookup",
                custom.stage_timings_ms["aggregate_lookup"],
            )
            return custom

        entity_type = self._normalize_entity_type(c.entity_type, c.original_query)
        text_pattern = c.text_pattern or self._extract_part_number(c.original_query)
        # If router gave no text_pattern and no part number, extract key terms
        # from the query to avoid full-table scan on 19.9M rows.
        if not text_pattern:
            terms = _extract_query_terms(c.original_query)
            if terms:
                text_pattern = terms[0]  # use most specific term
        text_pattern = f"%{text_pattern}%" if text_pattern else None

        agg = self.entity_store.aggregate_entity(
            entity_type=entity_type,
            text_pattern=text_pattern,
            min_confidence=self.min_confidence,
        )

        parts = []
        sources = set()

        if agg:
            parts.append("## Aggregation Results\n\n")
            for item in agg:
                parts.append(
                    f"- **{item['text']}**: found {item['count']} time(s) "
                    f"across {len(item['sources'])} source(s)\n"
                    f"  Sources: {', '.join(item['sources'])}\n"
                )
                sources.update(item["sources"])
            parts.append(f"\n**Total unique matches: {len(agg)}**\n")

        # Query relationship store for cross-document evidence
        # (same pattern as _entity_lookup — AGGREGATE queries need this
        # for "which sites had shipments" / "what parts were replaced" type queries)
        terms = _extract_query_terms(c.original_query)
        rels: list[RelationshipResult] = []
        if terms:
            seen_rel_keys: set[tuple[str, str, str]] = set()
            for term in terms[:4]:
                term_rels = self.relationship_store.find_related(
                    text=term, min_confidence=self.min_confidence, limit=10,
                )
                for r in term_rels:
                    if not _is_quality_relationship(r):
                        continue
                    key = (r.subject_text, r.predicate, r.object_text)
                    if key not in seen_rel_keys:
                        seen_rel_keys.add(key)
                        rels.append(r)
                if len(rels) >= 20:
                    break
            rels = rels[:20]

        if rels:
            parts.append("\n## Cross-Document Relationships\n\n")
            for r in rels:
                parts.append(
                    f"- {r.subject_text} --[{r.predicate}]-> {r.object_text} "
                    f"(confidence: {r.confidence:.1f}, source: {r.source_path})\n"
                )
                sources.add(r.source_path)

        if not parts:
            return None

        return StructuredResult(
            context_text="".join(parts),
            sources=list(sources),
            result_count=len(agg or []) + len(rels),
            query_path="AGGREGATE",
            stage_timings_ms={
                "aggregate_lookup": int((time.perf_counter() - aggregate_start) * 1000),
                "structured_lookup": int((time.perf_counter() - aggregate_start) * 1000),
            },
        )

    def _tabular_query(self, c: QueryClassification) -> StructuredResult | None:
        """Query extracted table rows."""
        table_start = time.perf_counter()
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
            stage_timings_ms={
                "tabular_lookup": int((time.perf_counter() - table_start) * 1000),
                "structured_lookup": int((time.perf_counter() - table_start) * 1000),
            },
        )

    def _normalize_entity_type(self, raw: str, query: str) -> str | None:
        """Map free-form router labels onto the structured-store schema."""
        if raw:
            upper = raw.strip().upper()
            if upper in VALID_ENTITY_TYPES:
                return upper

        value = " ".join((raw or "").lower().split())
        q = query.lower()

        if any(token in value or token in q for token in ("contact", "email", "phone")):
            return "CONTACT"
        if any(
            token in value or token in q
            for token in ("purchase order", "po-", "po ", "requisition")
        ):
            return "PO"
        if any(
            token in value or token in q
            for token in ("site", "location", "destination", "observatory", "air base")
        ):
            return "SITE"
        if any(
            token in value or token in q
            for token in ("part", "module", "card", "board", "serial")
        ):
            return "PART"
        if any(
            token in value or token in q
            for token in (
                "person",
                "technician",
                "requestor",
                "point of contact",
                "field technician",
                "requested parts",
            )
        ):
            return "PERSON"
        if "date" in value or "scheduled" in q:
            return "DATE"
        if any(token in value for token in ("org", "organization", "team")):
            return "ORG"
        return None

    def _lookup_contact_for_person(
        self,
        person_pattern: str,
        source_filter: str | None,
    ) -> list[EntityResult]:
        """Resolve contact rows by first locating the referenced person."""
        people = self.entity_store.lookup_entities(
            entity_type="PERSON",
            text_pattern=person_pattern,
            source_path=source_filter,
            min_confidence=self.min_confidence,
            limit=10,
        )
        if not people:
            return []

        want_email = "@" not in person_pattern
        contacts: dict[tuple[str, str], EntityResult] = {}
        for person in people:
            matches = self.entity_store.lookup_entities(
                entity_type="CONTACT",
                source_path=person.source_path,
                min_confidence=self.min_confidence,
                limit=20,
            )
            for contact in matches:
                if want_email and "@" not in contact.text:
                    continue
                contacts[(contact.source_path, contact.text)] = contact

        return list(contacts.values())

    def _aggregate_sites_for_part(self, c: QueryClassification) -> StructuredResult | None:
        """List site destinations for part-distribution queries."""
        q = " ".join(c.original_query.lower().split())
        if "which sites" not in q and "which locations" not in q:
            return None

        part_number = self._extract_part_number(c.original_query)
        if not part_number:
            return None

        rows = self.entity_store.query_tables(value_contains=part_number, limit=200)
        site_rows: dict[str, dict] = {}
        for row in rows:
            mapping = self._row_to_mapping(row.headers, row.values)
            site = mapping.get("site") or mapping.get("destination")
            if not site:
                continue
            site_rows[site] = {
                "site": site,
                "status": mapping.get("status", ""),
                "po": mapping.get("po") or mapping.get("po number", ""),
                "source": row.source_path,
            }

        if not site_rows:
            return None

        ordered_sites = sorted(site_rows.values(), key=lambda item: item["site"])
        parts = [f"## Sites For {part_number}\n\n"]
        sources = set()
        for item in ordered_sites:
            status = f" ({item['status']})" if item["status"] else ""
            po = f", {item['po']}" if item["po"] else ""
            parts.append(f"- {item['site']}{status}{po}\n")
            sources.add(item["source"])

        return StructuredResult(
            context_text="".join(parts),
            sources=list(sources),
            result_count=len(ordered_sites),
            query_path="AGGREGATE",
            stage_timings_ms={},
        )

    def _aggregate_unique_part_numbers(
        self, c: QueryClassification
    ) -> StructuredResult | None:
        """Collapse part variants down to canonical part numbers across the store."""
        q = " ".join(c.original_query.lower().split())
        if "unique part numbers" not in q:
            return None

        agg = self.entity_store.aggregate_entity(
            entity_type="PART",
            min_confidence=self.min_confidence,
        )
        if not agg:
            return None

        canonical_sources: dict[str, set[str]] = {}
        for item in agg:
            for token in self._canonical_part_numbers(item["text"]):
                canonical_sources.setdefault(token, set()).update(item["sources"])

        if not canonical_sources:
            return None

        parts = ["## Unique Part Numbers\n\n"]
        for token in sorted(canonical_sources):
            sources = sorted(canonical_sources[token])
            parts.append(
                f"- {token}: referenced in {len(sources)} source(s)\n"
                f"  Sources: {', '.join(sources)}\n"
            )

        return StructuredResult(
            context_text="".join(parts),
            sources=sorted({src for srcs in canonical_sources.values() for src in srcs}),
            result_count=len(canonical_sources),
            query_path="AGGREGATE",
            stage_timings_ms={},
        )

    def _row_to_mapping(self, headers: list[str], values: list[str]) -> dict[str, str]:
        """Normalize a table row into a lowercase header -> value mapping."""
        if len(headers) != len(values):
            return {}

        mapping: dict[str, str] = {}
        for header, value in zip(headers, values, strict=False):
            key = header.strip().lower()
            mapping[key] = value.strip()

        if "po number" in mapping and "po" not in mapping:
            mapping["po"] = mapping["po number"]
        return mapping

    def _extract_part_number(self, query: str) -> str | None:
        """Extract the most relevant part token from a query string."""
        match = re.search(r"\b(?:SEMS3D-\d+|[A-Z]{2,}-\d{3,4})\b", query, re.IGNORECASE)
        if not match:
            return None
        return match.group(0).upper()

    def _canonical_part_numbers(self, text: str) -> list[str]:
        """Extract canonical non-serial part numbers from a text field."""
        tokens = re.findall(
            r"\b(?:ARC-\d{4}|WR-\d{4}|AB-\d{3}|FM-\d{3}|PS-\d{3}|AH-\d{3}|SEMS3D-\d+)\b",
            text.upper(),
        )
        return list(dict.fromkeys(tokens))
