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

EXTRACTION_SYSTEM_PROMPT = """You are an entity extraction engine for enterprise program military maintenance documents.

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
        if not text.strip():
            return ExtractionResult([], [], [])

        result = ExtractionResult([], [], [])
        if self.llm.available:
            try:
                raw = self._call_extraction(text)
                result = self._parse_result(raw, chunk_id, source_path)
            except Exception as e:
                logger.error("Extraction failed for chunk %s: %s", chunk_id, e)
        else:
            logger.warning("LLM not available — deterministic table extraction only for %s", chunk_id)
        deterministic_rows = self._extract_deterministic_table_rows(
            text=text,
            chunk_id=chunk_id,
            source_path=source_path,
        )
        if deterministic_rows:
            result.table_rows = self._merge_table_rows(result.table_rows, deterministic_rows)
        return result

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

    def _extract_deterministic_table_rows(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        """Parse obvious table layouts directly from the chunk text."""
        rows = []
        rows.extend(self._extract_markdown_tables(text, chunk_id, source_path))
        rows.extend(self._extract_bracket_row_tables(text, chunk_id, source_path))
        return rows

    def _extract_markdown_tables(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        """Extract standard markdown pipe tables."""
        lines = [line.rstrip() for line in text.splitlines()]
        rows: list[TableRow] = []
        table_index = 0
        i = 0

        while i < len(lines) - 1:
            header_line = lines[i].strip()
            separator_line = lines[i + 1].strip()
            if not self._looks_like_pipe_row(header_line) or not self._is_markdown_separator(
                separator_line
            ):
                i += 1
                continue

            headers = self._split_pipe_row(header_line)
            if not headers:
                i += 1
                continue

            table_id = f"{chunk_id}_mdtable_{table_index}"
            table_index += 1
            row_index = 0
            j = i + 2
            while j < len(lines):
                candidate = lines[j].strip()
                if not self._looks_like_pipe_row(candidate) or self._is_markdown_separator(
                    candidate
                ):
                    break
                values = self._split_pipe_row(candidate)
                if len(values) == len(headers):
                    rows.append(
                        TableRow(
                            source_path=source_path,
                            table_id=table_id,
                            row_index=row_index,
                            headers=json.dumps(headers),
                            values=json.dumps(values),
                            chunk_id=chunk_id,
                        )
                    )
                    row_index += 1
                j += 1
            i = j

        return rows

    def _extract_bracket_row_tables(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        """Extract `[ROW n] value | value | ...` spreadsheet fragments."""
        row_re = re.compile(r"^\[ROW\s+(\d+)\]\s*(.+)$", re.IGNORECASE)
        lines = [line.strip() for line in text.splitlines()]
        rows: list[TableRow] = []
        current_headers: list[str] | None = None
        table_index = 0
        row_index = 0

        for line in lines:
            match = row_re.match(line)
            if not match:
                continue

            logical_row = int(match.group(1))
            cells = [cell.strip() for cell in match.group(2).split("|")]
            if self._looks_like_header_row(logical_row, cells):
                current_headers = cells
                row_index = 0
                table_index += 1
                continue

            if not current_headers or len(cells) != len(current_headers):
                continue

            table_id = f"{chunk_id}_rowtable_{table_index}"
            rows.append(
                TableRow(
                    source_path=source_path,
                    table_id=table_id,
                    row_index=row_index,
                    headers=json.dumps(current_headers),
                    values=json.dumps(cells),
                    chunk_id=chunk_id,
                )
            )
            row_index += 1

        return rows

    def _merge_table_rows(
        self,
        llm_rows: list[TableRow],
        deterministic_rows: list[TableRow],
    ) -> list[TableRow]:
        """Deduplicate table rows while preferring deterministic captures."""
        merged: dict[tuple[str, int, str], TableRow] = {}
        for row in llm_rows + deterministic_rows:
            key = (row.table_id, row.row_index, row.values)
            merged[key] = row
        return list(merged.values())

    def _looks_like_pipe_row(self, line: str) -> bool:
        """Return True when a line resembles a pipe-delimited row."""
        return line.startswith("|") and line.endswith("|") and line.count("|") >= 2

    def _is_markdown_separator(self, line: str) -> bool:
        """Return True for markdown table separator rows."""
        if "|" not in line:
            return False
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        return bool(cells) and all(cells) and all(set(cell) <= {"-", ":"} for cell in cells)

    def _split_pipe_row(self, line: str) -> list[str]:
        """Split a pipe-delimited row into trimmed cell values."""
        return [cell.strip() for cell in line.strip("|").split("|")]

    def _looks_like_header_row(self, logical_row: int, cells: list[str]) -> bool:
        """Detect header rows in `[ROW n]` spreadsheet fragments."""
        if logical_row == 1:
            return True

        header_tokens = {
            "po number",
            "po",
            "part number",
            "description",
            "qty",
            "quantity",
            "status",
            "ship date",
            "eta",
            "destination",
            "site",
            "requestor",
            "notes",
            "order date",
            "delivery date",
        }
        lowered = {cell.strip().lower() for cell in cells}
        return bool(lowered & header_tokens)


class RegexPreExtractor:
    """
    Tier 1: Fast regex-based pre-extraction for known patterns.

    Runs on every chunk at near-zero cost. Handles 60-70% of entity types:
    parts, POs, dates, emails, phones, serial numbers, report IDs.
    Results feed the same entity store as GLiNER (Tier 2) and LLM (Tier 3).
    """

    # Default security-standard prefix exclusion list. Matches the
    # config.schema.ExtractionConfig.security_standard_exclude_prefixes
    # default exactly so callers who don't pass a list still get the
    # full Rev-5 + STIG + MITRE coverage. When callers DO pass a list
    # (RegexPreExtractor(security_standard_exclude_prefixes=...)), it
    # overrides this default verbatim — this is the per-corpus override
    # point.
    #
    # The exclusion guards the class against the laptop-10M class of
    # pollution for the PART/PO columns: the 98% industry standard-N pollution
    # on the 10.4M enterprise program corpus traced back to the
    # '_report_id_re' alternation including IR and to the generic
    # '[A-Z]{2,}-\\d{3,4}' part pattern catching STIG baseline codes
    # (AS-5021, OS-0004, GPOS-0022). See
    # docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md.
    _DEFAULT_SECURITY_STANDARD_PREFIXES: tuple[str, ...] = (
        # security standard SP 800-53 Rev 5 control families (all 20)
        "AC-", "AT-", "AU-", "CA-", "CM-", "CP-", "IA-", "IR-", "MA-",
        "MP-", "PE-", "PL-", "PM-", "PS-", "PT-", "RA-", "SA-", "SC-",
        "SI-", "SR-",
        # STIG baseline platform prefixes
        "AS-", "OS-", "GPOS-", "HS-",
        # STIG / DISA identifier prefixes
        "CCI-", "SV-", "SP-800", "SP-",
        # MITRE security identifier prefixes
        "CVE-", "CCE-",
    )

    def __init__(
        self,
        part_patterns: list[str] | None = None,
        security_standard_exclude_prefixes: list[str] | tuple[str, ...] | None = None,
    ):
        self._part_patterns = [re.compile(p) for p in (part_patterns or [])]
        # Normalize exclusion prefixes to uppercase tuple for cheap startswith.
        # Empty list is a legitimate "disable all exclusion" override.
        if security_standard_exclude_prefixes is None:
            self._security_exclude_prefixes: tuple[str, ...] = \
                self._DEFAULT_SECURITY_STANDARD_PREFIXES
        else:
            self._security_exclude_prefixes = tuple(
                p.upper() for p in security_standard_exclude_prefixes
            )
        self._email_re = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
        # Phone regex: broad candidate matcher, validated by _is_valid_phone().
        #
        # Why not just tighten the regex? Phone number formats are messy
        # (parens, dots, dashes, spaces, optional country code). Trying to
        # encode every validity rule in regex alone produced either false
        # positives (the 16M CONTACT over-match on the 10.4M corpus — see
        # docs/PHONE_REGEX_FIX_2026-04-11.md) or false negatives (missing
        # real phones). Two-stage match + validate is cleaner.
        #
        # Boundary guards:
        #
        #   Leading: (?<![\w.-])
        #     Reject when a letter, digit, underscore, dot, or dash sits
        #     immediately before the candidate. This blocks alphanumeric
        #     serials (ABC3043618872XYZ) and matches embedded inside
        #     dotted version/IP sequences (1.2.3.4.5552345678).
        #
        #   Trailing: (?!\w)(?!\.[A-Za-z0-9])(?!-\w)
        #     Three zero-width checks; all must pass:
        #       (?!\w)              — next char is not word char (blocks
        #                             5552345678X and 5552345678_var)
        #       (?!\.[A-Za-z0-9])   — not a dot followed by alphanumeric
        #                             (blocks .example.com, .serial, .pdf)
        #       (?!-\w)             — not a dash followed by word char
        #                             (blocks -12345, -v2, -serial)
        #     This allows ordinary trailing sentence punctuation (.  ,  ;
        #     :  !  ?  newline) while still rejecting embeddings in larger
        #     alphanumeric tokens. Round-2 QA fix — see the "Round 2 QA
        #     fix" section of PHONE_REGEX_FIX_2026-04-11.md.
        self._phone_re = re.compile(
            r"(?<![\w.-])"
            r"(?:\+?1[\s.-]?)?"                        # optional +1 country code
            r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"     # NXX-NXX-XXXX core
            r"(?!\w)(?!\.[A-Za-z0-9])(?!-\w)"
        )
        self._date_re = re.compile(
            r"\b\d{4}-\d{2}-\d{2}\b"
            r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
            r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}\b"
        )
        self._po_re = re.compile(r"PO-\d{4}-\d{4}")
        # Labeled SAP PO — 10-digit procurement number preceded by an
        # explicit PO / Purchase Order label. Requiring a label is the
        # only way to distinguish a real SAP PO from the dozens of
        # other 10-digit tokens on every enterprise program page
        # (phone numbers, shipment tracking, timestamps, OCR noise).
        # See docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md
        # for the per-100-chunk measurement confirming the SAP PO
        # column is empty in the current store — all 98% of the PO
        # values are industry standard-N, not real procurement.
        self._sap_po_re = re.compile(
            r"(?:Purchase\s*Order|PO\s*Number|P\.?O\.?|PO)"
            r"\s*[#:.\-]?\s*"
            r"(\d{10})"
            r"\b",
            re.IGNORECASE,
        )
        # V1-ported patterns.
        # NOTE: 'IR' was removed from the _report_id_re alternation in
        # the 2026-04-12 security standard fix — 98% of matches were security standard Incident
        # Response family controls (IR-1..IR-10), not real Incident
        # Reports. The enterprise program corpus uses FSR/UMR/ASV/RTS
        # for real reports; IR-* was 100% collision with security standard.
        self._serial_re = re.compile(r"\bSN[-: ]?[A-Za-z0-9-]+\b", re.IGNORECASE)
        self._report_id_re = re.compile(r"\b(?:FSR|UMR|ASV|RTS)-[A-Za-z0-9_-]+\b", re.IGNORECASE)
        # Field-label extraction (V1 service_event_extractor pattern)
        self._field_value_re = re.compile(
            r"^\s*(?P<label>(?:Site|Location|Point of Contact|POC|Technician|Engineer)"
            r")\s*:\s*(?P<value>.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        self._field_label_map = {
            "site": "SITE", "location": "SITE",
            "point of contact": "PERSON", "poc": "PERSON",
            "technician": "PERSON", "engineer": "PERSON",
        }

    def _is_security_standard_identifier(self, candidate: str) -> bool:
        """Return True if the candidate matches a configured security-standard
        prefix (security standard SP 800-53 family, STIG CCI/SV, MITRE CVE/CCE, STIG
        baseline platform codes, etc.) and should NOT be emitted as a
        PART or PO entity.

        Called at every candidate-emit site in this class and in
        EventBlockParser. Cheap — single startswith scan over a short
        tuple. See
        docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md.
        """
        if not candidate:
            return False
        upper = candidate.upper()
        return any(upper.startswith(p) for p in self._security_exclude_prefixes)

    def extract(
        self, text: str, chunk_id: str, source_path: str
    ) -> list[Entity]:
        """Extract entities using regex patterns. Returns high-confidence matches."""
        entities = []

        for pattern in self._part_patterns:
            for match in pattern.finditer(text):
                candidate = match.group()
                if self._is_security_standard_identifier(candidate):
                    continue
                entities.append(Entity(
                    entity_type="PART",
                    text=candidate.upper(),
                    raw_text=candidate,
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
            candidate = match.group()
            if not self._is_valid_phone(candidate):
                continue
            entities.append(Entity(
                entity_type="CONTACT",
                text=candidate,
                raw_text=candidate,
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
            candidate = match.group()
            if self._is_security_standard_identifier(candidate):
                continue
            entities.append(Entity(
                entity_type="PO",
                text=candidate.upper(),
                raw_text=candidate,
                confidence=1.0,
                chunk_id=chunk_id,
                source_path=source_path,
                context=self._surrounding(text, match.start()),
            ))

        # SAP-format labeled POs (e.g., "PO 5000585586", "Purchase Order: 7000354926")
        # Added 2026-04-12 as part of the security standard regex over-match fix. The
        # 10-digit SAP PO column is effectively empty in the current
        # Tier 1 store because no label-free 10-digit pattern exists.
        for match in self._sap_po_re.finditer(text):
            po_number = match.group(1)
            if self._is_security_standard_identifier(po_number):
                continue
            entities.append(Entity(
                entity_type="PO",
                text=po_number,
                raw_text=match.group(),
                confidence=0.95,
                chunk_id=chunk_id,
                source_path=source_path,
                context=self._surrounding(text, match.start()),
            ))

        # Serial numbers (V1 pattern)
        for match in self._serial_re.finditer(text):
            candidate = match.group()
            if self._is_security_standard_identifier(candidate):
                continue
            entities.append(Entity(
                entity_type="PART",
                text=candidate.upper(),
                raw_text=candidate,
                confidence=0.95,
                chunk_id=chunk_id,
                source_path=source_path,
                context=self._surrounding(text, match.start()),
            ))

        # Report IDs (FSR, UMR, ASV, RTS — IR removed 2026-04-12 due
        # to 98% collision with security standard Incident Response family)
        for match in self._report_id_re.finditer(text):
            candidate = match.group()
            if self._is_security_standard_identifier(candidate):
                continue
            entities.append(Entity(
                entity_type="PO",
                text=candidate.upper(),
                raw_text=candidate,
                confidence=0.9,
                chunk_id=chunk_id,
                source_path=source_path,
                context=self._surrounding(text, match.start()),
            ))

        # Field-label extraction (Site: X, POC: Y, etc.)
        for match in self._field_value_re.finditer(text):
            label = match.group("label").strip().lower()
            value = match.group("value").strip()
            entity_type = self._field_label_map.get(label)
            if entity_type and value and len(value) > 1:
                entities.append(Entity(
                    entity_type=entity_type,
                    text=value,
                    raw_text=value,
                    confidence=0.9,
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

    @staticmethod
    def _is_valid_phone(candidate: str) -> bool:
        """
        Validate a candidate phone match against US NANP rules.

        The regex `self._phone_re` is intentionally permissive so it catches
        all reasonable phone formats. This validator rejects the garbage:

          - Repeated-digit strings (2222222222, 3333222222, 9999999999)
          - OCR/spreadsheet noise masquerading as digit runs
          - NANP-invalid numbers (area code or prefix starting with 0/1)
          - Wrong-length digit sequences

        The 16M CONTACT over-match from Sprint 7.4 Tier 1 came almost
        entirely from repeated-digit sequences in OCR'd tables — this
        validator is the primary fix. See docs/PHONE_REGEX_FIX_2026-04-11.md
        for the diagnosis and before/after evidence.

        Accepts (returns True):
          (555) 234-5678, 555-234-5678, +1 555 234 5678,
          555.234.5678, 5552345678, 1-555-234-5678

        Rejects (returns False):
          2222222222, 4444444444, 3333222222, 2211111111, 3333333344,
          1234567890 (NANP area starts with 1), any 9+ consecutive same digit
        """
        # Strip to digits only
        digits = re.sub(r"\D", "", candidate)

        # 11 digits only valid if leading 1 (US country code)
        if len(digits) == 11:
            if digits[0] != "1":
                return False
            digits = digits[1:]
        if len(digits) != 10:
            return False

        # NANP rules: area code and prefix first digits must be 2-9
        if digits[0] in "01":
            return False
        if digits[3] in "01":
            return False

        # Uniqueness: real US phones have broad digit diversity.
        # The fake OCR/tabular matches are always 1-3 unique digits
        # (2222222222, 3333222222, 2211111111, etc). A floor of 4 unique
        # digits rejects every documented fake in the primary workstation sample while
        # leaving real phones untouched.
        if len(set(digits)) < 4:
            return False

        # Reject any run of 7+ identical consecutive digits (5550000000,
        # 8005551234 passes because only 3 zeros in a row).
        for i in range(len(digits) - 6):
            if len(set(digits[i:i + 7])) == 1:
                return False

        return True


# ---------------------------------------------------------------------------
# Event block parsing (ported from V1 service_event_extractor.py)
# ---------------------------------------------------------------------------

_NUMBERED_BLOCK_RE = re.compile(r"(?m)^\s*(?=\d+\.\s+)")
_FIELD_VALUE_BROAD_RE = re.compile(
    r"^\s*(?:\d+\.\s+)?(?P<label>[A-Za-z][A-Za-z0-9 /#()_-]{1,40}):\s*(?P<value>.*)$",
    re.MULTILINE,
)
_QTY_RE = re.compile(r"\bqty(?:uantity)?\s*[:=]?\s*(\d+)\b", re.IGNORECASE)

_EVENT_LABELS: dict[str, str] = {
    "part#": "part_number",
    "part": "part_number",
    "component": "component_name",
    "description": "part_description",
    "part description": "part_description",
    "action": "action_raw",
    "failure mode": "failure_mode",
    "condition": "failure_mode",
    "condition found": "failure_mode",
    "downtime": "downtime_raw",
    "new unit": "new_unit_serial",
    "failed unit": "failed_unit_serial",
    "installed": "installed_serial",
    "removed": "removed_serial",
    "installed part#": "installed_part_number",
    "removed part#": "removed_part_number",
}

_ACTION_SYNONYMS: list[tuple[str, tuple[str, ...]]] = [
    ("replaced", ("replace", "replaced", "swap", "swapped", "replacement")),
    ("installed", ("install", "installed", "installation")),
    ("removed", ("remove", "removed", "uninstalled")),
    ("repaired", ("repair", "repaired", "fixed", "restored")),
    ("inspected", ("inspect", "inspected", "checked", "tested", "verified")),
    ("adjusted", ("adjust", "adjusted", "aligned", "calibrated", "tuned")),
    ("upgraded", ("upgrade", "upgraded", "updated")),
]

_EVENT_BLOCK_MARKERS = (
    "Part#", "Component:", "Action:", "Failure Mode:",
    "Condition:", "New Unit:", "Failed Unit:", "Removed:",
)
_EVENT_FALLBACK_MARKERS = (
    "Part#", "Component:", "Failure Mode:", "Action:",
    "RESOLUTION:", "CORRECTIVE ACTION",
)


def _normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_action_type(action_raw: str, **serials: str) -> str:
    """Classify action text into a compact type."""
    lowered = re.sub(r"[^a-z0-9]+", " ", str(action_raw or "").lower()).strip()
    for action_type, synonyms in _ACTION_SYNONYMS:
        if any(tok in lowered for tok in synonyms):
            return action_type
    if serials.get("new_unit_serial") and (
        serials.get("removed_serial") or serials.get("failed_unit_serial")
    ):
        return "replaced"
    if serials.get("new_unit_serial") or serials.get("installed_serial"):
        return "installed"
    if serials.get("removed_serial") or serials.get("failed_unit_serial"):
        return "removed"
    return "other"


def _is_power_text(text: str) -> tuple[bool, bool]:
    """Detect power/lightning events."""
    normalized = _normalize_whitespace(text).lower()
    is_lightning = "lightning" in normalized
    is_power = is_lightning or any(
        tok in normalized
        for tok in ("power surge", "power event", "brownout",
                    "power outage", "voltage transient", "strike damage")
    )
    return is_power, is_lightning


class EventBlockParser:
    """
    Parse maintenance event blocks from chunk text (V1 pattern).

    Splits numbered maintenance items (e.g. "1. Part#: ARC-4471 ...")
    and extracts structured fields: part numbers, serials, actions,
    failure modes. Produces Entity and Relationship objects directly.
    """

    def __init__(
        self,
        part_patterns: list[str] | None = None,
        security_standard_exclude_prefixes: list[str] | tuple[str, ...] | None = None,
    ):
        self._serial_re = re.compile(r"\bSN[-: ]?[A-Za-z0-9-]+\b", re.IGNORECASE)
        self._part_patterns = [re.compile(p) for p in (part_patterns or [])]
        # Same exclusion list RegexPreExtractor uses. When callers don't
        # pass one explicitly, fall back to the RegexPreExtractor
        # default so the two classes stay in lockstep on corpus-specific
        # rejection rules. See
        # docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md.
        if security_standard_exclude_prefixes is None:
            self._security_exclude_prefixes: tuple[str, ...] = \
                RegexPreExtractor._DEFAULT_SECURITY_STANDARD_PREFIXES
        else:
            self._security_exclude_prefixes = tuple(
                p.upper() for p in security_standard_exclude_prefixes
            )

    def _is_security_standard_identifier(self, candidate: str) -> bool:
        """Mirror of RegexPreExtractor._is_security_standard_identifier."""
        if not candidate:
            return False
        upper = candidate.upper()
        return any(upper.startswith(p) for p in self._security_exclude_prefixes)

    def parse(
        self, text: str, chunk_id: str, source_path: str,
    ) -> tuple[list[Entity], list[Relationship]]:
        """Parse event blocks from text. Returns (entities, relationships)."""
        blocks = self._iter_event_blocks(text)
        if not blocks:
            return [], []

        all_entities: list[Entity] = []
        all_rels: list[Relationship] = []

        for block in blocks:
            fields = self._extract_field_map(block)
            if not fields:
                continue

            part_number = _normalize_whitespace(fields.get("part_number", "")).upper()
            component = _normalize_whitespace(fields.get("component_name", ""))
            action_raw = _normalize_whitespace(fields.get("action_raw", ""))
            failure_mode = _normalize_whitespace(fields.get("failure_mode", ""))
            new_serial = self._extract_serial(fields.get("new_unit_serial", ""))
            failed_serial = self._extract_serial(fields.get("failed_unit_serial", ""))
            installed_serial = self._extract_serial(fields.get("installed_serial", ""))
            removed_serial = self._extract_serial(fields.get("removed_serial", ""))
            installed_part = _normalize_whitespace(fields.get("installed_part_number", "")).upper()
            removed_part = _normalize_whitespace(fields.get("removed_part_number", "")).upper()

            action_type = _normalize_action_type(
                action_raw,
                new_unit_serial=new_serial,
                removed_serial=removed_serial,
                failed_unit_serial=failed_serial,
                installed_serial=installed_serial,
            )

            ctx = block[:160].strip()

            # Emit part entity
            if part_number and not self._is_security_standard_identifier(part_number):
                all_entities.append(Entity(
                    entity_type="PART", text=part_number, raw_text=part_number,
                    confidence=1.0, chunk_id=chunk_id,
                    source_path=source_path, context=ctx,
                ))

            # Emit component as PART
            if (component and component.upper() != part_number
                    and not self._is_security_standard_identifier(component)):
                all_entities.append(Entity(
                    entity_type="PART", text=component, raw_text=component,
                    confidence=0.85, chunk_id=chunk_id,
                    source_path=source_path, context=ctx,
                ))

            # Emit installed/removed parts
            for p in (installed_part, removed_part):
                if p and p != part_number and not self._is_security_standard_identifier(p):
                    all_entities.append(Entity(
                        entity_type="PART", text=p, raw_text=p,
                        confidence=0.95, chunk_id=chunk_id,
                        source_path=source_path, context=ctx,
                    ))

            # Emit serial numbers
            for sn in (new_serial, failed_serial, installed_serial, removed_serial):
                if sn and not self._is_security_standard_identifier(sn):
                    all_entities.append(Entity(
                        entity_type="PART", text=sn.upper(), raw_text=sn,
                        confidence=0.95, chunk_id=chunk_id,
                        source_path=source_path, context=ctx,
                    ))

            # Emit failure mode. We do NOT gate failure_mode through the
            # security-standard exclusion — failure descriptions are free
            # text like "receiver fault" or "antenna cable shorted" and
            # can't collide with security standard family prefixes. Leaving the gate
            # off here preserves EventBlockParser's signal on maintenance
            # narrative even if a future rejection list grows aggressive.
            if failure_mode:
                all_entities.append(Entity(
                    entity_type="PART", text=failure_mode, raw_text=failure_mode,
                    confidence=0.8, chunk_id=chunk_id,
                    source_path=source_path, context=ctx,
                ))

            # Power/lightning classification
            is_power, is_lightning = _is_power_text(block)

            # --- Relationships ---
            target_part = part_number or component

            # REPLACED_AT / INSTALLED_AT / action relationships
            if target_part and action_type == "replaced":
                if installed_part or new_serial:
                    replacement = installed_part or new_serial.upper()
                    all_rels.append(Relationship(
                        subject_type="PART", subject_text=replacement,
                        predicate="REPLACED_AT",
                        object_type="PART", object_text=target_part,
                        confidence=0.95, source_path=source_path,
                        chunk_id=chunk_id, context=ctx,
                    ))
                if removed_part or removed_serial:
                    removed = removed_part or removed_serial.upper()
                    all_rels.append(Relationship(
                        subject_type="PART", subject_text=removed,
                        predicate="REPLACED_AT",
                        object_type="PART", object_text=target_part,
                        confidence=0.95, source_path=source_path,
                        chunk_id=chunk_id, context=ctx,
                    ))

            if target_part and failure_mode:
                all_rels.append(Relationship(
                    subject_type="PART", subject_text=target_part,
                    predicate="FAILED_AT",
                    object_type="PART", object_text=failure_mode,
                    confidence=0.85, source_path=source_path,
                    chunk_id=chunk_id, context=ctx,
                ))

        return all_entities, all_rels

    def _iter_event_blocks(self, text: str) -> list[str]:
        """Split chunk into per-item event blocks (V1 pattern)."""
        raw = str(text or "")
        segments = [s.strip() for s in _NUMBERED_BLOCK_RE.split(raw) if s.strip()]
        blocks = [
            s for s in segments
            if any(marker in s for marker in _EVENT_BLOCK_MARKERS)
        ]
        if blocks:
            return blocks
        if any(marker in raw for marker in _EVENT_FALLBACK_MARKERS):
            return [raw]
        return []

    def _extract_field_map(self, block_text: str) -> dict[str, str]:
        """Extract labeled fields from a block."""
        fields: dict[str, str] = {}
        for match in _FIELD_VALUE_BROAD_RE.finditer(str(block_text or "")):
            label = _normalize_whitespace(match.group("label")).lower()
            target = _EVENT_LABELS.get(label)
            if not target:
                continue
            value = _normalize_whitespace(match.group("value"))
            if value and not fields.get(target):
                fields[target] = value
        return fields

    def _extract_serial(self, value: str) -> str:
        """Clean serial from field value."""
        match = self._serial_re.search(str(value or ""))
        if match:
            return _normalize_whitespace(match.group(0))
        return _normalize_whitespace(value)


# ---------------------------------------------------------------------------
# Regex-based relationship extraction (co-occurrence patterns)
# ---------------------------------------------------------------------------

class RegexRelationshipExtractor:
    """
    Extract relationships from co-occurring entities within chunks.

    Detects patterns like:
      - "POC: X" + "Site: Y" in same chunk -> PERSON POC_FOR SITE
      - "Part#: X replaced at Site: Y" -> PART REPLACED_AT SITE
      - "PO-XXXX for Site: Y" -> PO ORDERED_FOR SITE
      - "Technician: X at Site: Y" -> PERSON WORKS_AT SITE
    """

    def __init__(self):
        # Field-label patterns for entity co-occurrence
        self._poc_re = re.compile(
            r"^\s*(?:Point of Contact|POC)\s*:\s*(?P<name>.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        self._site_re = re.compile(
            r"^\s*(?:Site|Location)\s*:\s*(?P<site>.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        self._tech_re = re.compile(
            r"^\s*(?:Technician|Engineer)\s*:\s*(?P<name>.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        self._part_re = re.compile(
            r"^\s*(?:Part#|Part|Component)\s*:\s*(?P<part>.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        self._po_re = re.compile(r"PO-\d{4}-\d{4}")
        self._action_re = re.compile(
            r"^\s*Action\s*:\s*(?P<action>.+)$",
            re.MULTILINE | re.IGNORECASE,
        )

    def extract(
        self, text: str, chunk_id: str, source_path: str,
    ) -> list[Relationship]:
        """Extract relationships from field co-occurrence in text."""
        rels: list[Relationship] = []
        ctx = text[:160].strip()

        # Extract field values
        poc_match = self._poc_re.search(text)
        site_match = self._site_re.search(text)
        tech_match = self._tech_re.search(text)
        part_match = self._part_re.search(text)
        po_match = self._po_re.search(text)
        action_match = self._action_re.search(text)

        poc_name = poc_match.group("name").strip() if poc_match else ""
        site_name = site_match.group("site").strip() if site_match else ""
        tech_name = tech_match.group("name").strip() if tech_match else ""
        part_text = part_match.group("part").strip().upper() if part_match else ""
        po_text = po_match.group().upper() if po_match else ""
        action_text = action_match.group("action").strip() if action_match else ""

        action_type = _normalize_action_type(action_text) if action_text else ""

        # POC -> Site
        if poc_name and site_name:
            rels.append(Relationship(
                subject_type="PERSON", subject_text=poc_name,
                predicate="POC_FOR",
                object_type="SITE", object_text=site_name,
                confidence=0.95, source_path=source_path,
                chunk_id=chunk_id, context=ctx,
            ))

        # Technician -> Site
        if tech_name and site_name:
            rels.append(Relationship(
                subject_type="PERSON", subject_text=tech_name,
                predicate="WORKS_AT",
                object_type="SITE", object_text=site_name,
                confidence=0.9, source_path=source_path,
                chunk_id=chunk_id, context=ctx,
            ))

        # Part -> Site (action-based)
        if part_text and site_name:
            predicate = "CONSUMED_AT"
            if action_type == "replaced":
                predicate = "REPLACED_AT"
            elif action_type == "installed":
                predicate = "INSTALLED_AT"
            elif action_type in ("inspected", "adjusted"):
                predicate = "TESTED_AT"
            elif action_type == "removed":
                predicate = "REPLACED_AT"

            rels.append(Relationship(
                subject_type="PART", subject_text=part_text,
                predicate=predicate,
                object_type="SITE", object_text=site_name,
                confidence=0.9, source_path=source_path,
                chunk_id=chunk_id, context=ctx,
            ))

        # PO -> Site
        if po_text and site_name:
            rels.append(Relationship(
                subject_type="PO", subject_text=po_text,
                predicate="ORDERED_FOR",
                object_type="SITE", object_text=site_name,
                confidence=0.9, source_path=source_path,
                chunk_id=chunk_id, context=ctx,
            ))

        # Part failure at site
        if part_text and site_name and action_type in ("replaced", "removed", "repaired"):
            rels.append(Relationship(
                subject_type="PART", subject_text=part_text,
                predicate="FAILED_AT",
                object_type="SITE", object_text=site_name,
                confidence=0.8, source_path=source_path,
                chunk_id=chunk_id, context=ctx,
            ))

        # PO -> Part
        if po_text and part_text:
            rels.append(Relationship(
                subject_type="PO", subject_text=po_text,
                predicate="ORDERED_FOR",
                object_type="PART", object_text=part_text,
                confidence=0.85, source_path=source_path,
                chunk_id=chunk_id, context=ctx,
            ))

        # POC -> maintains site
        if poc_name and site_name:
            rels.append(Relationship(
                subject_type="PERSON", subject_text=poc_name,
                predicate="MAINTAINED_BY",
                object_type="SITE", object_text=site_name,
                confidence=0.8, source_path=source_path,
                chunk_id=chunk_id, context=ctx,
            ))

        return rels
