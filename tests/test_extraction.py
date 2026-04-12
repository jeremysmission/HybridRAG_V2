"""
Unit tests for entity extraction pipeline.

Covers:
  - RegexPreExtractor (Tier 1): all regex patterns
  - QualityGate: confidence filtering, dedup, normalization
  - EntityStore: insert/lookup/aggregate/dedup
  - RelationshipStore: insert/lookup/traversal/dedup
  - EventBlockParser: V1-ported event block splitting + field extraction
  - RegexRelationshipExtractor: co-occurrence relationship extraction
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.store.entity_store import Entity, EntityStore, TableRow
from src.store.relationship_store import Relationship, RelationshipStore
from src.extraction.entity_extractor import (
    RegexPreExtractor,
    EventBlockParser,
    RegexRelationshipExtractor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def regex_extractor():
    """RegexPreExtractor with default V2 part patterns."""
    return RegexPreExtractor(part_patterns=[
        r"ARC-\d{4}",
        r"IGSI-\d+",
        r"PO-\d{4}-\d{4}",
        r"SN[-: ]?\d+",
        r"SEMS3D-\d+",
        r"[A-Z]{2,}-\d{3,4}",
        r"WR-\d{4}",
        r"FM-\d{3}",
        r"AB-\d{3}",
        r"PS-\d{3}",
        r"AH-\d{3}",
    ])


@pytest.fixture
def entity_store(tmp_path):
    """Fresh in-memory entity store."""
    db = str(tmp_path / "test_entities.sqlite3")
    store = EntityStore(db)
    yield store
    store.close()


@pytest.fixture
def rel_store(tmp_path):
    """Fresh in-memory relationship store."""
    db = str(tmp_path / "test_rels.sqlite3")
    store = RelationshipStore(db)
    yield store
    store.close()


# ===================================================================
# RegexPreExtractor Tests
# ===================================================================

class TestRegexPreExtractor:
    """Tests for Tier 1 regex extraction patterns."""

    def test_email_extraction(self, regex_extractor):
        text = "Contact john.doe@example.com for details."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        emails = [e for e in entities if e.entity_type == "CONTACT" and "@" in e.text]
        assert len(emails) >= 1
        assert emails[0].text == "john.doe@example.com"
        assert emails[0].confidence == 1.0

    def test_phone_extraction(self, regex_extractor):
        text = "Call (970) 555-0142 for support."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        phones = [e for e in entities if e.entity_type == "CONTACT" and "@" not in e.text]
        assert len(phones) >= 1
        assert "970" in phones[0].text

    def test_phone_accepts_real_formats(self, regex_extractor):
        """Real phone formats must all be extracted."""
        samples = [
            ("Call (555) 234-5678 today", "(555) 234-5678"),
            ("Phone 555-234-5678", "555-234-5678"),
            ("Reach +1 555 234 5678", "+1 555 234 5678"),
            ("Try 555.234.5678 next", "555.234.5678"),
            ("Direct 5552345678 now", "5552345678"),
            ("Call 1-555-234-5678", "1-555-234-5678"),
            ("Toll free 800-555-1212", "800-555-1212"),
        ]
        for text, expected_fragment in samples:
            entities = regex_extractor.extract(text, "c1", "doc.txt")
            phones = [
                e.text for e in entities
                if e.entity_type == "CONTACT" and "@" not in e.text
            ]
            assert phones, f"No phone extracted from {text!r}"
            # Validator should accept the exact match the regex captured
            assert any(p.replace(" ", "").replace("-", "").replace(".", "")
                       .replace("(", "").replace(")", "").replace("+", "")
                       .endswith("5552345678") or "970" in p or "8005551212" in p.replace("-", "").replace(" ", "")
                       for p in phones), f"Phone content wrong for {text!r}: {phones}"

    def test_phone_rejects_repeated_digit_garbage(self, regex_extractor):
        """The 16M CONTACT over-match from Sprint 7.4 was repeated-digit OCR noise.

        These strings must NOT produce phone entities. They are the literal
        samples primary workstation surfaced from the 10.4M corpus store.
        """
        fakes = [
            "3333333344",
            "4444444444",
            "2222222222",
            "3333222222",
            "2211111111",
            "9999999999",
            "0000000000",
            "1111111111",
        ]
        for fake in fakes:
            text = f"Value in table: {fake} end"
            entities = regex_extractor.extract(text, "c1", "doc.txt")
            phones = [
                e for e in entities
                if e.entity_type == "CONTACT" and "@" not in e.text
            ]
            assert not phones, (
                f"Fake phone {fake!r} leaked through validator: "
                f"{[e.text for e in phones]}"
            )

    def test_phone_rejects_nanp_invalid(self, regex_extractor):
        """NANP area code and prefix first digit must be 2-9."""
        # Area code starts with 0 or 1
        invalid_area = [
            "0123456789",  # area 012
            "1234567890",  # area 123 (first digit 1)
        ]
        for fake in invalid_area:
            text = f"Number {fake} here"
            entities = regex_extractor.extract(text, "c1", "doc.txt")
            phones = [
                e for e in entities
                if e.entity_type == "CONTACT" and "@" not in e.text
            ]
            assert not phones, f"NANP-invalid {fake!r} leaked: {phones}"

    def test_phone_rejects_inside_longer_digit_runs(self, regex_extractor):
        """Don't match a 10-digit window inside a longer digit sequence.

        Serial numbers, document IDs, and raw tabular runs often contain
        12-16 consecutive digits. The regex lookbehind/lookahead must
        prevent matching any 10-digit subsequence.
        """
        cases = [
            "Serial 12345678901234",          # 14 digits
            "Doc ID: 5552345678901",          # 13 digits, first 10 would be NANP-valid
            "Run: 999555234567801234",        # 18 digits
        ]
        for text in cases:
            entities = regex_extractor.extract(text, "c1", "doc.txt")
            phones = [
                e for e in entities
                if e.entity_type == "CONTACT" and "@" not in e.text
            ]
            assert not phones, f"Leaked from long digit run {text!r}: {phones}"

    def test_phone_rejects_long_repeat_runs(self, regex_extractor):
        """7+ consecutive identical digits should never be a phone."""
        cases = [
            "Call 5550000000 now",   # 7 zeros in a row
            "Call 5557777777 now",   # 7 sevens in a row
        ]
        for text in cases:
            entities = regex_extractor.extract(text, "c1", "doc.txt")
            phones = [
                e for e in entities
                if e.entity_type == "CONTACT" and "@" not in e.text
            ]
            assert not phones, f"Leaked from repeat run {text!r}: {phones}"

    def test_phone_accepts_sentence_punctuation(self, regex_extractor):
        """Round-2 QA regression — phones followed by sentence punctuation.

        Earlier boundary guard `(?![\\w.-])` rejected any phone followed by
        a dot, which broke common prose like 'Call 555-234-5678.'. The new
        guard `(?!\\w)(?!\\.[A-Za-z0-9])(?!-\\w)` allows trailing punctuation
        while still rejecting embeddings in larger tokens.

        CoPilot+ QA finding: 2026-04-11.
        """
        cases = [
            # (input, expected phone text in top result)
            ("Call 555-234-5678.", "555-234-5678"),
            ("Call (555) 234-5678.", "(555) 234-5678"),
            ("Phone: +1 555 234 5678.", "+1 555 234 5678"),
            ("Support 555.234.5678.", "555.234.5678"),
            ("Number is 555-234-5678, please call", "555-234-5678"),
            ("Call 555-234-5678; thanks", "555-234-5678"),
            ("See 555-234-5678?", "555-234-5678"),
            ("Phone: 555-234-5678!", "555-234-5678"),
            ("End of line 555-234-5678\n", "555-234-5678"),
            ("555-234-5678", "555-234-5678"),  # bare, no trailing
        ]
        for text, expected in cases:
            entities = regex_extractor.extract(text, "c1", "doc.txt")
            phones = [
                e.text for e in entities
                if e.entity_type == "CONTACT" and "@" not in e.text
            ]
            assert phones, (
                f"Sentence-punctuation regression: no phone extracted "
                f"from {text!r}"
            )
            assert expected in phones, (
                f"Expected {expected!r} in phones for {text!r}, got {phones}"
            )

    def test_phone_rejects_embedded_in_larger_tokens(self, regex_extractor):
        """Round-2 QA regression — must not match inside larger tokens.

        The trailing guard's three lookaheads block:
          (?!\\w)             — alphanumeric suffix
          (?!\\.[A-Za-z0-9])  — dotted alphanumeric continuation
          (?!-\\w)            — dashed alphanumeric continuation
        """
        cases = [
            "555-234-5678.example.com",
            "555-234-5678.serial",
            "555-234-5678-12345",
            "555-234-5678X",
            "doc_555-234-5678_v2",
            "file555-234-5678.pdf",
            "host-555-234-5678.local",
        ]
        for text in cases:
            entities = regex_extractor.extract(text, "c1", "doc.txt")
            phones = [
                e.text for e in entities
                if e.entity_type == "CONTACT" and "@" not in e.text
            ]
            assert not phones, (
                f"Embedded-token regression: phone extracted from {text!r}: "
                f"{phones}"
            )

    def test_phone_validator_unit(self):
        """Direct unit test for RegexPreExtractor._is_valid_phone()."""
        from src.extraction.entity_extractor import RegexPreExtractor
        v = RegexPreExtractor._is_valid_phone

        # Valid
        assert v("(555) 234-5678")
        assert v("555-234-5678")
        assert v("+1 555 234 5678")
        assert v("555.234.5678")
        assert v("5552345678")
        assert v("1-555-234-5678")
        assert v("15552345678")
        assert v("(970) 555-0142")

        # Invalid
        assert not v("2222222222")
        assert not v("3333333344")
        assert not v("3333222222")
        assert not v("9999999999")
        assert not v("0123456789")   # area 012
        assert not v("1234567890")   # area starts with 1
        assert not v("5550000000")   # 7 zeros in a row
        assert not v("12345")        # too short
        assert not v("25552345678")  # 11 digits, leading digit not 1

    def test_date_iso_format(self, regex_extractor):
        text = "Scheduled for 2025-06-15."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        dates = [e for e in entities if e.entity_type == "DATE"]
        assert len(dates) >= 1
        assert "2025-06-15" in dates[0].text

    def test_date_slash_format(self, regex_extractor):
        text = "Report date: 3/15/2025."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        dates = [e for e in entities if e.entity_type == "DATE"]
        assert len(dates) >= 1
        assert "3/15/2025" in dates[0].text

    def test_date_month_name(self, regex_extractor):
        text = "Completed on March 15, 2025."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        dates = [e for e in entities if e.entity_type == "DATE"]
        assert len(dates) >= 1
        assert "March 15, 2025" in dates[0].text

    def test_po_extraction(self, regex_extractor):
        text = "Issued PO-2025-0142 for replacement parts."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        pos = [e for e in entities if e.entity_type == "PO" and e.text.startswith("PO-")]
        assert len(pos) >= 1
        assert pos[0].text == "PO-2025-0142"

    def test_part_number_arc(self, regex_extractor):
        text = "Replaced ARC-4471 RF connector."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        parts = [e for e in entities if e.entity_type == "PART" and "ARC" in e.text]
        assert len(parts) >= 1
        assert "ARC-4471" in parts[0].text

    def test_part_number_fm(self, regex_extractor):
        text = "Component FM-220 failed during test."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        parts = [e for e in entities if e.entity_type == "PART" and "FM" in e.text]
        assert len(parts) >= 1

    def test_serial_number(self, regex_extractor):
        text = "Unit SN 12345-A was removed."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        serials = [e for e in entities if e.entity_type == "PART" and "SN" in e.text.upper()]
        assert len(serials) >= 1

    def test_report_id_fsr(self, regex_extractor):
        text = "Reference FSR-2025-001 for details."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        reports = [e for e in entities if e.entity_type == "PO" and "FSR" in e.text]
        assert len(reports) >= 1

    def test_report_id_umr(self, regex_extractor):
        text = "See UMR-THULE-2025 for context."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        reports = [e for e in entities if e.entity_type == "PO" and "UMR" in e.text]
        assert len(reports) >= 1

    def test_field_label_site(self, regex_extractor):
        text = "Site: Thule Air Base\nPOC: SSgt Webb"
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        sites = [e for e in entities if e.entity_type == "SITE"]
        assert len(sites) >= 1
        assert "Thule Air Base" in sites[0].text

    def test_field_label_poc(self, regex_extractor):
        text = "Point of Contact: SSgt Marcus Webb"
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        persons = [e for e in entities if e.entity_type == "PERSON"]
        assert len(persons) >= 1
        assert "SSgt Marcus Webb" in persons[0].text

    def test_field_label_technician(self, regex_extractor):
        text = "Technician: John Smith"
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        persons = [e for e in entities if e.entity_type == "PERSON"]
        assert len(persons) >= 1

    def test_empty_text(self, regex_extractor):
        entities = regex_extractor.extract("", "c1", "doc.txt")
        assert entities == []

    def test_no_entities(self, regex_extractor):
        text = "This is a plain sentence with no extractable entities."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        # May pick up some false positives from generic patterns, but should be minimal
        assert isinstance(entities, list)

    def test_multiple_entities_same_chunk(self, regex_extractor):
        text = """Site: Riverside Observatory
        POC: TSgt Torres
        Part#: ARC-4471
        Date: 2025-06-15
        Contact: torres@enterprise.mil
        PO: PO-2025-0142"""
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        types = {e.entity_type for e in entities}
        assert "SITE" in types
        assert "PERSON" in types
        assert "PART" in types
        assert "DATE" in types
        assert "CONTACT" in types
        assert "PO" in types

    def test_context_populated(self, regex_extractor):
        text = "The connector ARC-4471 was replaced at Thule."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        for e in entities:
            assert e.context  # should never be empty

    def test_chunk_id_source_propagated(self, regex_extractor):
        text = "Part FM-220 installed."
        entities = regex_extractor.extract(text, "chunk_99", "reports/fsr.txt")
        for e in entities:
            assert e.chunk_id == "chunk_99"
            assert e.source_path == "reports/fsr.txt"


# ===================================================================
# QualityGate Tests
# ===================================================================

class TestQualityGate:
    """Tests for quality gate filtering and normalization."""

    def _make_entity(self, entity_type="PART", text="ARC-4471",
                     confidence=0.9, chunk_id="c1"):
        return Entity(
            entity_type=entity_type, text=text, raw_text=text,
            confidence=confidence, chunk_id=chunk_id,
            source_path="doc.txt", context="test context",
        )

    def test_confidence_filter(self):
        from src.extraction.quality_gate import QualityGate
        gate = QualityGate(min_confidence=0.7, vocab_path="nonexistent.yaml")
        entities = [
            self._make_entity(confidence=0.9),
            self._make_entity(confidence=0.5, text="LOW-001"),
            self._make_entity(confidence=0.3, text="VLOW-001"),
        ]
        passed = gate.filter_entities(entities)
        assert len(passed) == 1
        assert passed[0].text == "ARC-4471"

    def test_dedup_within_batch(self):
        from src.extraction.quality_gate import QualityGate
        gate = QualityGate(min_confidence=0.0, vocab_path="nonexistent.yaml")
        entities = [
            self._make_entity(text="ARC-4471"),
            self._make_entity(text="ARC-4471"),  # duplicate
            self._make_entity(text="FM-220"),
        ]
        passed = gate.filter_entities(entities)
        assert len(passed) == 2

    def test_part_normalization_uppercase(self):
        from src.extraction.quality_gate import QualityGate
        gate = QualityGate(min_confidence=0.0, vocab_path="nonexistent.yaml")
        entities = [self._make_entity(text="arc-4471")]
        passed = gate.filter_entities(entities)
        assert passed[0].text == "ARC-4471"

    def test_contact_email_lowercase(self):
        from src.extraction.quality_gate import QualityGate
        gate = QualityGate(min_confidence=0.0, vocab_path="nonexistent.yaml")
        entities = [self._make_entity(entity_type="CONTACT", text="John@EXAMPLE.com")]
        passed = gate.filter_entities(entities)
        assert passed[0].text == "john@example.com"

    def test_person_title_case(self):
        from src.extraction.quality_gate import QualityGate
        gate = QualityGate(min_confidence=0.0, vocab_path="nonexistent.yaml")
        entities = [self._make_entity(entity_type="PERSON", text="SSGT MARCUS WEBB, Site POC")]
        passed = gate.filter_entities(entities)
        assert passed[0].text == "Ssgt Marcus Webb"  # title case, role stripped

    def test_relationship_confidence_filter(self):
        from src.extraction.quality_gate import QualityGate
        gate = QualityGate(min_confidence=0.7, vocab_path="nonexistent.yaml")
        rels = [
            Relationship(
                subject_type="PERSON", subject_text="Webb",
                predicate="POC_FOR", object_type="SITE", object_text="Thule",
                confidence=0.9, source_path="doc.txt", chunk_id="c1",
            ),
            Relationship(
                subject_type="PERSON", subject_text="Smith",
                predicate="WORKS_AT", object_type="SITE", object_text="Riverside",
                confidence=0.3, source_path="doc.txt", chunk_id="c1",
            ),
        ]
        passed = gate.filter_relationships(rels)
        assert len(passed) == 1
        assert passed[0].subject_text == "Webb"


# ===================================================================
# EntityStore Tests
# ===================================================================

class TestEntityStore:
    """Tests for SQLite entity store CRUD operations."""

    def _make_entity(self, text="ARC-4471", entity_type="PART",
                     chunk_id="c1", source_path="doc.txt"):
        return Entity(
            entity_type=entity_type, text=text, raw_text=text,
            confidence=0.9, chunk_id=chunk_id,
            source_path=source_path, context="test",
        )

    def test_insert_and_count(self, entity_store):
        entities = [self._make_entity(), self._make_entity(text="FM-220")]
        entity_store.insert_entities(entities)
        assert entity_store.count_entities() == 2

    def test_dedup_on_insert(self, entity_store):
        e = self._make_entity()
        entity_store.insert_entities([e])
        entity_store.insert_entities([e])  # same entity again
        assert entity_store.count_entities() == 1

    def test_lookup_by_type(self, entity_store):
        entity_store.insert_entities([
            self._make_entity(entity_type="PART"),
            self._make_entity(entity_type="PERSON", text="Webb"),
        ])
        results = entity_store.lookup_entities(entity_type="PART")
        assert len(results) == 1
        assert results[0].entity_type == "PART"

    def test_lookup_by_text_pattern(self, entity_store):
        entity_store.insert_entities([
            self._make_entity(text="ARC-4471"),
            self._make_entity(text="FM-220"),
        ])
        results = entity_store.lookup_entities(text_pattern="%ARC%")
        assert len(results) == 1
        assert "ARC" in results[0].text

    def test_aggregate(self, entity_store):
        entity_store.insert_entities([
            self._make_entity(text="ARC-4471", chunk_id="c1"),
            self._make_entity(text="ARC-4471", chunk_id="c2"),
            self._make_entity(text="FM-220", chunk_id="c3"),
        ])
        agg = entity_store.aggregate_entity(entity_type="PART")
        texts = {a["text"]: a["count"] for a in agg}
        assert texts["ARC-4471"] == 2
        assert texts["FM-220"] == 1

    def test_type_summary(self, entity_store):
        entity_store.insert_entities([
            self._make_entity(entity_type="PART"),
            self._make_entity(entity_type="PERSON", text="Webb"),
            self._make_entity(entity_type="PERSON", text="Torres"),
        ])
        summary = entity_store.entity_type_summary()
        assert summary["PART"] == 1
        assert summary["PERSON"] == 2

    def test_table_row_insert(self, entity_store):
        rows = [TableRow(
            source_path="sheet.xlsx", table_id="t1",
            row_index=0, headers='["Part", "Qty"]',
            values='["ARC-4471", "5"]', chunk_id="c1",
        )]
        entity_store.insert_table_rows(rows)
        assert entity_store.count_table_rows() == 1

    def test_query_tables(self, entity_store):
        rows = [TableRow(
            source_path="sheet.xlsx", table_id="t1",
            row_index=0, headers='["Part", "Qty"]',
            values='["ARC-4471", "5"]', chunk_id="c1",
        )]
        entity_store.insert_table_rows(rows)
        results = entity_store.query_tables(header_contains="Part")
        assert len(results) == 1
        assert results[0].headers == ["Part", "Qty"]


# ===================================================================
# RelationshipStore Tests
# ===================================================================

class TestRelationshipStore:
    """Tests for relationship triple store operations."""

    def _make_rel(self, subject="Webb", predicate="POC_FOR", obj="Thule",
                  chunk_id="c1"):
        return Relationship(
            subject_type="PERSON", subject_text=subject,
            predicate=predicate,
            object_type="SITE", object_text=obj,
            confidence=0.9, source_path="doc.txt",
            chunk_id=chunk_id, context="test",
        )

    def test_insert_and_count(self, rel_store):
        rels = [self._make_rel(), self._make_rel(subject="Torres", obj="Riverside")]
        rel_store.insert_relationships(rels)
        assert rel_store.count() == 2

    def test_dedup_on_insert(self, rel_store):
        r = self._make_rel()
        rel_store.insert_relationships([r])
        rel_store.insert_relationships([r])
        assert rel_store.count() == 1

    def test_find_by_subject(self, rel_store):
        rel_store.insert_relationships([
            self._make_rel(subject="Webb", obj="Thule"),
            self._make_rel(subject="Torres", obj="Riverside"),
        ])
        results = rel_store.find_by_subject("Webb")
        assert len(results) == 1
        assert results[0].object_text == "Thule"

    def test_find_by_object(self, rel_store):
        rel_store.insert_relationships([
            self._make_rel(subject="Webb", obj="Thule"),
        ])
        results = rel_store.find_by_object("Thule")
        assert len(results) == 1
        assert results[0].subject_text == "Webb"

    def test_find_related(self, rel_store):
        rel_store.insert_relationships([
            self._make_rel(subject="Webb", obj="Thule"),
            self._make_rel(subject="Thule", predicate="LOCATED_AT", obj="Greenland"),
        ])
        results = rel_store.find_related("Thule")
        assert len(results) == 2

    def test_multi_hop(self, rel_store):
        rel_store.insert_relationships([
            self._make_rel(subject="Webb", predicate="POC_FOR", obj="Thule"),
            Relationship(
                subject_type="SITE", subject_text="Thule",
                predicate="LOCATED_AT",
                object_type="ORG", object_text="Greenland Region",
                confidence=0.9, source_path="doc.txt",
                chunk_id="c2", context="test",
            ),
        ])
        paths = rel_store.multi_hop("Webb", hops=2)
        assert len(paths) >= 1
        assert any(len(p) == 2 for p in paths)

    def test_predicate_summary(self, rel_store):
        rel_store.insert_relationships([
            self._make_rel(predicate="POC_FOR"),
            self._make_rel(subject="Torres", predicate="WORKS_AT", obj="Riverside"),
        ])
        summary = rel_store.predicate_summary()
        assert summary["POC_FOR"] == 1
        assert summary["WORKS_AT"] == 1


# ===================================================================
# EventBlockParser Tests
# ===================================================================

class TestEventBlockParser:
    """Tests for V1-ported event block parsing."""

    @pytest.fixture
    def parser(self):
        return EventBlockParser(part_patterns=[r"ARC-\d{4}", r"FM-\d{3}"])

    def test_numbered_event_block(self, parser):
        text = """1. Part#: ARC-4471
   Component: RF Connector
   Action: Replaced
   Failure Mode: Corrosion
   New Unit: SN 99887
   Failed Unit: SN 12345"""
        entities, rels = parser.parse(text, "c1", "doc.txt")
        types = {e.entity_type for e in entities}
        assert "PART" in types
        assert len(entities) >= 3  # part + serials + failure mode

    def test_multiple_event_blocks(self, parser):
        text = """1. Part#: ARC-4471
   Action: Replaced

2. Part#: FM-220
   Action: Inspected"""
        entities, rels = parser.parse(text, "c1", "doc.txt")
        part_texts = {e.text for e in entities if e.entity_type == "PART"}
        assert "ARC-4471" in part_texts
        assert "FM-220" in part_texts

    def test_replacement_relationship(self, parser):
        text = """1. Part#: ARC-4471
   Action: Replaced
   New Unit: SN 99887
   Failed Unit: SN 12345"""
        entities, rels = parser.parse(text, "c1", "doc.txt")
        replaced = [r for r in rels if r.predicate == "REPLACED_AT"]
        assert len(replaced) >= 1

    def test_failure_mode_relationship(self, parser):
        text = """1. Part#: ARC-4471
   Failure Mode: Corrosion damage"""
        entities, rels = parser.parse(text, "c1", "doc.txt")
        failed = [r for r in rels if r.predicate == "FAILED_AT"]
        assert len(failed) == 1
        assert failed[0].subject_text == "ARC-4471"

    def test_no_event_blocks(self, parser):
        text = "This is a narrative paragraph with no maintenance events."
        entities, rels = parser.parse(text, "c1", "doc.txt")
        assert entities == []
        assert rels == []

    def test_fallback_single_block(self, parser):
        text = """Part#: ARC-4471
Action: Installed
Component: Waveguide adapter"""
        entities, rels = parser.parse(text, "c1", "doc.txt")
        assert len(entities) >= 1  # should detect as fallback single block


# ===================================================================
# RegexRelationshipExtractor Tests
# ===================================================================

class TestRegexRelationshipExtractor:
    """Tests for co-occurrence based relationship extraction."""

    @pytest.fixture
    def extractor(self):
        return RegexRelationshipExtractor()

    def test_poc_site_relationship(self, extractor):
        text = """Site: Thule Air Base
POC: SSgt Marcus Webb"""
        rels = extractor.extract(text, "c1", "doc.txt")
        poc_rels = [r for r in rels if r.predicate == "POC_FOR"]
        assert len(poc_rels) == 1
        assert poc_rels[0].subject_text == "SSgt Marcus Webb"
        assert poc_rels[0].object_text == "Thule Air Base"

    def test_technician_site_relationship(self, extractor):
        text = """Site: Riverside Observatory
Technician: John Smith"""
        rels = extractor.extract(text, "c1", "doc.txt")
        works_at = [r for r in rels if r.predicate == "WORKS_AT"]
        assert len(works_at) == 1
        assert works_at[0].subject_text == "John Smith"

    def test_part_site_replaced(self, extractor):
        text = """Site: Cedar Ridge
Part#: ARC-4471
Action: Replaced"""
        rels = extractor.extract(text, "c1", "doc.txt")
        replaced = [r for r in rels if r.predicate == "REPLACED_AT"]
        assert len(replaced) >= 1

    def test_po_site_relationship(self, extractor):
        text = """Site: Thule Air Base
PO-2025-0142 for replacement parts."""
        rels = extractor.extract(text, "c1", "doc.txt")
        ordered = [r for r in rels if r.predicate == "ORDERED_FOR" and r.subject_type == "PO"]
        assert len(ordered) >= 1
        assert ordered[0].subject_text == "PO-2025-0142"

    def test_part_site_failure(self, extractor):
        text = """Site: Riverside Observatory
Part#: FM-220
Action: Removed"""
        rels = extractor.extract(text, "c1", "doc.txt")
        failed = [r for r in rels if r.predicate == "FAILED_AT"]
        assert len(failed) == 1

    def test_no_site_no_relationships(self, extractor):
        text = "Part#: ARC-4471 was installed."
        rels = extractor.extract(text, "c1", "doc.txt")
        # No site present, so no co-occurrence relationships
        site_rels = [r for r in rels if r.object_type == "SITE"]
        assert len(site_rels) == 0

    def test_multiple_relationships_same_chunk(self, extractor):
        text = """Site: Thule Air Base
POC: SSgt Webb
Technician: John Smith
Part#: ARC-4471
Action: Replaced
PO-2025-0142"""
        rels = extractor.extract(text, "c1", "doc.txt")
        predicates = {r.predicate for r in rels}
        assert "POC_FOR" in predicates
        assert "WORKS_AT" in predicates
        assert "REPLACED_AT" in predicates
        assert "ORDERED_FOR" in predicates
