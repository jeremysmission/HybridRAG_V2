"""
GPT-4o entity extractor — structured extraction from document chunks.

Uses Azure OpenAI structured outputs (response_format json_schema)
for guaranteed valid JSON. Extracts:
  - PERSON: names, roles, contact info
  - PART: part numbers, serial numbers, descriptions
  - SITE: locations, site names, bases
  - DATE: dates, schedules, deadlines
  - PO: purchase orders, requisitions
  - ORG: organizations, units, teams
  - CONTACT: emails, phone numbers

Also extracts entity-entity relationships as triples.

GLiNER first-pass is stubbed for when waiver clears.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from json import JSONDecodeError

from src.llm.client import LLMClient
from src.store.entity_store import Entity, TableRow
from src.store.relationship_store import Relationship

logger = logging.getLogger(__name__)

# Structured outputs JSON schema for entity extraction
ENTITY_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "entity_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "entity_type": {
                                "type": "string",
                                "enum": ["PERSON", "PART", "SITE", "DATE",
                                         "PO", "ORG", "CONTACT"],
                            },
                            "text": {"type": "string"},
                            "raw_text": {"type": "string"},
                            "confidence": {"type": "number"},
                            "context": {"type": "string"},
                        },
                        "required": ["entity_type", "text", "raw_text",
                                     "confidence", "context"],
                        "additionalProperties": False,
                    },
                },
                "relationships": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subject_type": {"type": "string"},
                            "subject_text": {"type": "string"},
                            "predicate": {
                                "type": "string",
                                "enum": [
                                    "POC_FOR", "WORKS_AT", "REPLACED_AT",
                                    "CONSUMED_AT", "ORDERED_FOR", "MAINTAINED_BY",
                                    "LOCATED_AT", "REPORTS_TO", "SCHEDULED_FOR",
                                    "SHIPPED_TO", "REQUESTED_BY", "FAILED_AT",
                                    "INSTALLED_AT", "TESTED_AT", "OTHER",
                                ],
                            },
                            "object_type": {"type": "string"},
                            "object_text": {"type": "string"},
                            "confidence": {"type": "number"},
                            "context": {"type": "string"},
                        },
                        "required": ["subject_type", "subject_text", "predicate",
                                     "object_type", "object_text", "confidence",
                                     "context"],
                        "additionalProperties": False,
                    },
                },
                "table_rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "headers": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "values": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["headers", "values"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["entities", "relationships", "table_rows"],
            "additionalProperties": False,
        },
    },
}

EXTRACTION_SYSTEM_PROMPT = """You are an entity extraction engine for IGS/NEXION military maintenance documents.

Extract ALL entities and relationships from the provided text chunk.

ENTITY TYPES:
- PERSON: Full names with role if available (e.g., "SSgt Marcus Webb, Site POC")
- PART: Part numbers, serial numbers with descriptions (e.g., "ARC-4471, RF Connector")
- SITE: Location names, bases, observatories (e.g., "Thule Air Base", "Riverside Observatory")
- DATE: Dates, schedules, deadlines in ISO format when possible (e.g., "2025-06-15")
- PO: Purchase orders, requisition numbers (e.g., "PO-2025-0142")
- ORG: Organizations, units, teams (e.g., "ACME Weather Radar")
- CONTACT: Email addresses, phone numbers (e.g., "(970) 555-0142")

RELATIONSHIP PREDICATES:
- POC_FOR: person is point of contact for a site/system
- WORKS_AT: person works at a site
- REPLACED_AT: part was replaced at a site
- CONSUMED_AT: part was consumed/used at a site
- ORDERED_FOR: PO was ordered for a site/part
- MAINTAINED_BY: site/system is maintained by a person
- LOCATED_AT: equipment/system is at a site
- SCHEDULED_FOR: maintenance is scheduled for a date
- SHIPPED_TO: part/PO shipped to a site
- REQUESTED_BY: part/PO requested by a person
- FAILED_AT: part/equipment failed at a site
- INSTALLED_AT: part was installed at a site
- TESTED_AT: equipment tested at a site
- REPORTS_TO: person reports to another person
- OTHER: any other clear relationship

TABLE ROWS: If the text contains tabular data (pipe-separated, CSV-like, or clearly columnar), extract each row as headers + values.

RULES:
- Normalize text: proper case for names, uppercase for part numbers
- Confidence 0.0-1.0: 1.0 for explicitly stated, 0.7-0.9 for inferred, <0.7 for uncertain
- context: the sentence or phrase where the entity/relationship appears
- Extract EVERY entity — do not skip anything that matches the types above
- For dates, convert to ISO 8601 (YYYY-MM-DD) when possible
- For part numbers, preserve the exact format from the document"""


@dataclass
class ExtractionResult:
    """Result from extracting a single chunk."""

    entities: list[Entity]
    relationships: list[Relationship]
    table_rows: list[TableRow]
    input_tokens: int = 0
    output_tokens: int = 0


class EntityExtractor:
    """
    GPT-4o entity extractor with structured outputs.

    Processes chunks and returns typed entities, relationships,
    and table rows ready for insertion into stores.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def extract_from_chunk(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> ExtractionResult:
        """
        Extract entities, relationships, and table rows from a single chunk.

        Uses GPT-4o structured outputs for guaranteed valid JSON.
        """
        if not self.llm.available:
            logger.warning("LLM not available — skipping extraction for %s", chunk_id)
            return ExtractionResult([], [], [])

        if not text.strip():
            return ExtractionResult([], [], [])

        try:
            raw = self._call_extraction(text)
            return self._parse_result(raw, chunk_id, source_path)
        except Exception as e:
            logger.error("Extraction failed for chunk %s: %s", chunk_id, e)
            return ExtractionResult([], [], [])

    def extract_batch(
        self,
        chunks: list[dict],
    ) -> list[ExtractionResult]:
        """
        Extract entities from a batch of chunks.

        Each chunk dict must have: text, chunk_id, source_path.
        Processes sequentially (API rate limits make parallelism risky).
        """
        results = []
        for chunk in chunks:
            result = self.extract_from_chunk(
                text=chunk["text"],
                chunk_id=chunk["chunk_id"],
                source_path=chunk["source_path"],
            )
            results.append(result)
        return results

    def _call_extraction(self, text: str) -> dict:
        """Call LLM with structured output for entity extraction."""
        prompt = f"Extract all entities and relationships from this text:\n\n{text}"
        token_budget = max(4096, getattr(self.llm, "max_tokens", 4096))

        for attempt in range(2):
            llm_response = self.llm.call(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                temperature=0,
                max_tokens=token_budget,
                response_format=ENTITY_SCHEMA,
            )

            self._last_input_tokens = llm_response.input_tokens
            self._last_output_tokens = llm_response.output_tokens

            try:
                return json.loads(llm_response.text)
            except JSONDecodeError:
                truncated = llm_response.output_tokens >= token_budget
                if attempt == 0 and truncated:
                    logger.warning(
                        "Extraction response hit token budget (%d); retrying with a larger limit",
                        token_budget,
                    )
                    token_budget = min(max(token_budget * 2, 8192), 16384)
                    continue
                raise

        raise RuntimeError("Extraction retry loop exhausted")

    def _parse_result(
        self, raw: dict, chunk_id: str, source_path: str
    ) -> ExtractionResult:
        """Convert raw JSON extraction result into typed dataclasses."""
        entities = []
        for e in raw.get("entities", []):
            entities.append(Entity(
                entity_type=e["entity_type"],
                text=e["text"],
                raw_text=e["raw_text"],
                confidence=float(e["confidence"]),
                chunk_id=chunk_id,
                source_path=source_path,
                context=e.get("context", ""),
            ))

        relationships = []
        for r in raw.get("relationships", []):
            relationships.append(Relationship(
                subject_type=r["subject_type"],
                subject_text=r["subject_text"],
                predicate=r["predicate"],
                object_type=r["object_type"],
                object_text=r["object_text"],
                confidence=float(r["confidence"]),
                source_path=source_path,
                chunk_id=chunk_id,
                context=r.get("context", ""),
            ))

        table_rows = []
        for i, t in enumerate(raw.get("table_rows", [])):
            table_rows.append(TableRow(
                source_path=source_path,
                table_id=f"{chunk_id}_table",
                row_index=i,
                headers=json.dumps(t["headers"]),
                values=json.dumps(t["values"]),
                chunk_id=chunk_id,
            ))

        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            table_rows=table_rows,
            input_tokens=getattr(self, "_last_input_tokens", 0),
            output_tokens=getattr(self, "_last_output_tokens", 0),
        )


class RegexPreExtractor:
    """
    Fast regex-based pre-extraction for known patterns.

    Runs before GPT-4o to catch obvious entities cheaply.
    Results are merged with LLM extraction (LLM wins on conflicts).
    """

    def __init__(self, part_patterns: list[str] | None = None):
        self._part_patterns = [re.compile(p) for p in (part_patterns or [])]
        self._email_re = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
        self._phone_re = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
        self._date_re = re.compile(
            r"\b\d{4}-\d{2}-\d{2}\b"
            r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
            r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}\b"
        )
        self._po_re = re.compile(r"PO-\d{4}-\d{4}")

    def extract(
        self, text: str, chunk_id: str, source_path: str
    ) -> list[Entity]:
        """Extract entities using regex patterns. Returns high-confidence matches."""
        entities = []

        for pattern in self._part_patterns:
            for match in pattern.finditer(text):
                entities.append(Entity(
                    entity_type="PART",
                    text=match.group().upper(),
                    raw_text=match.group(),
                    confidence=1.0,
                    chunk_id=chunk_id,
                    source_path=source_path,
                    context=self._surrounding(text, match.start()),
                ))

        for match in self._email_re.finditer(text):
            entities.append(Entity(
                entity_type="CONTACT",
                text=match.group().lower(),
                raw_text=match.group(),
                confidence=1.0,
                chunk_id=chunk_id,
                source_path=source_path,
                context=self._surrounding(text, match.start()),
            ))

        for match in self._phone_re.finditer(text):
            entities.append(Entity(
                entity_type="CONTACT",
                text=match.group(),
                raw_text=match.group(),
                confidence=1.0,
                chunk_id=chunk_id,
                source_path=source_path,
                context=self._surrounding(text, match.start()),
            ))

        for match in self._date_re.finditer(text):
            entities.append(Entity(
                entity_type="DATE",
                text=match.group(),
                raw_text=match.group(),
                confidence=0.9,
                chunk_id=chunk_id,
                source_path=source_path,
                context=self._surrounding(text, match.start()),
            ))

        for match in self._po_re.finditer(text):
            entities.append(Entity(
                entity_type="PO",
                text=match.group().upper(),
                raw_text=match.group(),
                confidence=1.0,
                chunk_id=chunk_id,
                source_path=source_path,
                context=self._surrounding(text, match.start()),
            ))

        return entities

    def _surrounding(self, text: str, pos: int, window: int = 80) -> str:
        """Get surrounding text for context."""
        start = max(0, pos - window)
        end = min(len(text), pos + window)
        return text[start:end].strip()
