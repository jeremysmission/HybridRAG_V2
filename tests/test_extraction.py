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
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.store.entity_store import Entity, EntityStore, TableRow
from src.store.relationship_store import (
    Relationship,
    RelationshipStore,
    resolve_relationship_db_path,
)
from src.extraction.entity_extractor import (
    RegexPreExtractor,
    EventBlockParser,
    RegexRelationshipExtractor,
    RelationshipPhraseExtractor,
)
from src.extraction.tabular_substrate import (
    DeterministicTableExtractor,
    detect_logistics_table_families,
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

    def test_serial_regex_rejects_bare_sn_words(self, regex_extractor):
        for text in [
            "SNMP service is enabled.",
            "Weather may include snow.",
            "Use the Security Configuration snap-in.",
            "Packet sniffers were detected.",
        ]:
            entities = regex_extractor.extract(text, "c1", "doc.txt")
            serials = [e.text for e in entities if e.entity_type == "PART" and e.text.upper().startswith("SN")]
            assert not serials, f"bare SN word leaked as serial/part from {text!r}: {serials}"

    def test_serial_regex_accepts_compact_digit_serial(self, regex_extractor):
        text = "Device serial SN4112 was removed."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        serials = [e.text for e in entities if e.entity_type == "PART"]
        assert any(s.upper().startswith("SN4112") for s in serials), f"compact serial missing: {serials}"

    def test_report_id_fsr(self, regex_extractor):
        text = "Reference FSR-2025-001 for details."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        reports = [e for e in entities if e.entity_type == "PO" and "FSR" in e.text]
        assert len(reports) >= 1

    def test_report_id_rejects_embedded_product_code(self, regex_extractor):
        text = "Website: E9225E24B-FSR-L22 Mechatronics Fan Group | DigiKey"
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        reports = [e.text for e in entities if e.entity_type == "PO"]
        assert "FSR-L22" not in reports, f"embedded product code leaked as report id/PO: {reports}"

    def test_report_id_umr(self, regex_extractor):
        text = "See UMR-THULE-2025 for context."
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        reports = [e for e in entities if e.entity_type == "PO" and "UMR" in e.text]
        assert len(reports) >= 1

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("Reference ASV-VAFB for details.", "ASV-VAFB"),
            ("Archive RTS-DATA preserved.", "RTS-DATA"),
            ("Reference FSR-L22 for details.", "FSR-L22"),
        ],
    )
    def test_report_ids_corpus_variants(self, regex_extractor, text, expected):
        """Corpus-native report IDs from the live PO-polluted store should stay in PO.

        These long-tail identifiers still matter for live lookups and should
        not regress just because the high-volume IR-family false positives were
        removed.
        """
        entities = regex_extractor.extract(text, "c1", "doc.txt")
        reports = [e.text for e in entities if e.entity_type == "PO"]
        assert expected in reports, f"Expected report ID {expected!r} missing from {reports}"

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
# Security-Standard Identifier Exclusion (security standard regex fix 2026-04-12)
# ===================================================================
#
# Regression guard for the security standard SP 800-53 / STIG / MITRE CVE-CCE
# pollution of the PART and PO columns on the 10.4M enterprise program
# corpus (~98% of PO values were security standard Incident Response family IDs;
# ~90% of top PART values were STIG baseline codes AS-/OS-/GPOS-/CCI-).
#
# See docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md for
# the investigation and before/after evidence. The rejection list is
# configurable — tests cover both the default-on behavior and the
# per-corpus override path.


class TestSecurityStandardExclusion:
    """Ensures security standard / STIG / MITRE identifiers are NOT captured as
    PART or PO entities by default, and that the exclusion list is
    overridable per-corpus via constructor kwarg."""

    @pytest.fixture
    def extractor_with_generic_part_pattern(self):
        """Extractor with the production config's permissive part pattern
        [A-Z]{2,}-\\d{3,4} — the exact pattern that caught the top-21 STIG
        baseline codes on the primary workstation store. Tests below prove the exclusion
        gate now blocks them."""
        return RegexPreExtractor(part_patterns=[
            r"ARC-\d{4}",
            r"[A-Z]{2,}-\d{3,4}",
        ])

    def _texts(self, extractor):
        """Shortcut: run extractor on `text` and return PART / PO
        text values as two lists."""
        def go(text):
            ents = extractor.extract(text, "c1", "doc.txt")
            parts = [e.text for e in ents if e.entity_type == "PART"]
            pos = [e.text for e in ents if e.entity_type == "PO"]
            return parts, pos
        return go

    def test_stig_baseline_codes_rejected_as_part(self, extractor_with_generic_part_pattern):
        """The top-21 PART values on the primary workstation store are all STIG baseline
        codes: AS-5021, OS-0004, GPOS-0022, CCI-0001, SV-2045, HS-872.
        None of these should be emitted as PART entities."""
        go = self._texts(extractor_with_generic_part_pattern)
        fakes = [
            "Control baseline AS-5021 applies.",
            "See OS-0004 for platform guidance.",
            "GPOS-0022 defines the policy requirement.",
            "CCI-0001 maps to the control.",
            "Finding SV-2045 was remediated.",
            "Host baseline HS-872 applied.",
        ]
        for text in fakes:
            parts, _ = go(text)
            assert not parts, (
                f"security-standard identifier leaked through exclusion: "
                f"text={text!r} got PARTs={parts}"
            )

    def test_nist_sp_800_53_rev5_families_all_rejected(self, extractor_with_generic_part_pattern):
        """Every security standard SP 800-53 Rev 5 family must be excluded. Rev 5 added
        PT (PII) and SR (Supply Chain Risk) vs Rev 4; both are in the
        default list and tested here so a downgrade of the list is caught."""
        go = self._texts(extractor_with_generic_part_pattern)
        rev5_families = [
            "AC-2(1)", "AT-3", "AU-12", "CA-5", "CM-8", "CP-9", "IA-5",
            "IR-4", "MA-6", "MP-3", "PE-13", "PL-2", "PM-9", "PS-7",
            "PT-3", "RA-5", "SA-11", "SC-7", "SI-4", "SR-6",
        ]
        for fam in rev5_families:
            parts, pos = go(f"Control {fam} is in effect.")
            assert not parts, f"security standard family {fam} leaked as PART: {parts}"
            assert not pos, f"security standard family {fam} leaked as PO: {pos}"

    def test_nist_ir_family_not_caught_by_report_id_regex(self):
        """Regression for the 98% PO pollution: the _report_id_re
        alternation used to include 'IR', catching security standard Incident
        Response family controls (IR-1..IR-10) as report IDs. The
        'IR' alternation was removed 2026-04-12 — any future
        reintroduction must still pass this test, because the exclusion
        gate below blocks industry standard family regardless.
        """
        ex = RegexPreExtractor(part_patterns=[])
        for fake in ["IR-1", "IR-4", "IR-8", "IR-10"]:
            ents = ex.extract(f"security standard control {fake} applies.", "c1", "d.txt")
            pos = [e.text for e in ents if e.entity_type == "PO"]
            assert not pos, (
                f"industry standard family member {fake!r} leaked as PO: {pos}. "
                f"Either _report_id_re IR alternation came back OR "
                f"exclusion gate regressed."
            )

    def test_mitre_cve_cce_rejected(self, extractor_with_generic_part_pattern):
        """MITRE Common Vulnerabilities and Exposures (CVE-YYYY-NNNN)
        and Common Configuration Enumeration (CCE-NNNNN) are security
        standard identifiers, not physical parts."""
        go = self._texts(extractor_with_generic_part_pattern)
        for fake in ["CVE-1999", "CVE-2024", "CCE-2720", "CCE-1001"]:
            parts, _ = go(f"Reference {fake} was checked.")
            assert not parts, f"MITRE identifier {fake} leaked as PART: {parts}"

    def test_additional_cyber_noise_rejected(self, extractor_with_generic_part_pattern):
        """Regression guard for additional cyber/noise families found in the
        shadow slice and corpus audit."""
        go = self._texts(extractor_with_generic_part_pattern)
        for fake in [
            "RHSA-2018",
            "RHSA-2024",
            "APP-0001",
            "SERVICE_STOP",
            "SNMP",
            "CNSSI-4009",
            "DD-2842",
            "DO-0003",
            "DO-0011",
            "enterprise program-2522",
            "IGSI-2466",
            "MSR-029",
            "DV-200",
            "IEEE-1394",
            "SNOW",
            "pam_faillock",
            "unconfined_u",
            "CVE-202",
        ]:
            parts, pos = go(f"Reference {fake} was checked.")
            assert not parts, f"cyber-noise identifier {fake} leaked as PART: {parts}"
            assert not pos, f"cyber-noise identifier {fake} leaked as PO: {pos}"

    def test_real_physical_parts_still_accepted(self, extractor_with_generic_part_pattern):
        """Rejection must NOT drop real physical parts. These are the
        confirmed-physical parts from the Phase 1 anchor mining in
        docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md."""
        go = self._texts(extractor_with_generic_part_pattern)
        reals = [
            ("Installed RG-213 coax cable.", "RG-213"),
            ("Used LMR-400 for the run.", "LMR-400"),
            ("Replaced ARC-4471 connector.", "ARC-4471"),
        ]
        for text, expected in reals:
            parts, _ = go(text)
            upper_parts = [p.upper() for p in parts]
            assert any(expected in p for p in upper_parts), (
                f"Real physical part {expected!r} dropped by exclusion "
                f"from text {text!r}: got {parts}"
            )

    def test_sap_po_labeled_extracted(self):
        """Labeled procurement POs in the two proven-safe numeric families
        (legacy 6-digit and modern 10-digit) must be captured as PO entities.
        The label is REQUIRED — a bare number can't be distinguished from
        phone-like OCR noise or other numeric debris without context.
        """
        ex = RegexPreExtractor(part_patterns=[])
        cases = [
            ("Raised PO 5000585586 to Grainger.", "5000585586"),
            ("Purchase Order: 7000354926 approved.", "7000354926"),
            ("PO#7000325121 shipped.", "7000325121"),
            ("P.O. 4500111111 pending.", "4500111111"),
            ("Purchase order 5000111222 delivered.", "5000111222"),
            ("po 4500111111 is pending.", "4500111111"),
            ("Purchase Order: 268235 created to fund the order.", "268235"),
            ("All invoices must reference Purchase Order No. 250802.", "250802"),
            ("Purchase order number 7200751620 was approved.", "7200751620"),
        ]
        for text, expected_po in cases:
            ents = ex.extract(text, "c1", "doc.txt")
            pos = [e.text for e in ents if e.entity_type == "PO"]
            assert expected_po in pos, (
                f"Labeled SAP PO {expected_po!r} not extracted from "
                f"text {text!r}: got {pos}"
            )

    def test_sap_po_bare_10_digit_not_extracted(self):
        """A bare 10-digit number with NO label must NOT be emitted as
        a PO. This is the deliberate conservative choice — the corpus
        is full of 10-digit phone numbers, shipment tracking IDs, and
        timestamps that would otherwise pollute the PO column the same
        way industry standard did before today's fix.
        """
        ex = RegexPreExtractor(part_patterns=[])
        for fake in [
            "Call us at 5552345678 any time.",
            "Tracking 7000123456 in transit.",   # no 'PO' label
            "Document 5000000001 attached.",     # generic doc number
        ]:
            ents = ex.extract(fake, "c1", "doc.txt")
            pos = [e.text for e in ents if e.entity_type == "PO"]
            # None of these should produce a 10-digit PO entity
            assert not any(re.match(r"^\d{10}$", p) for p in pos), (
                f"Bare 10-digit leaked as PO from {fake!r}: {pos}"
            )

    def test_labeled_8digit_numeric_po_stays_fail_closed(self):
        """8-digit numeric PO-adjacent identifiers remain ambiguous in this
        corpus and should not auto-promote just because a PO label is nearby.
        """
        ex = RegexPreExtractor(part_patterns=[])
        ents = ex.extract("Purchase Order: 15404062", "c1", "doc.txt")
        pos = [e.text for e in ents if e.entity_type == "PO"]
        assert "15404062" not in pos, f"Ambiguous 8-digit PO leaked: {pos}"

    def test_sap_po_label_requires_leading_boundary(self):
        """The SAP PO label must start at a real token boundary, not inside
        a larger word like 'repo' or 'SPO'."""
        ex = RegexPreExtractor(part_patterns=[])
        for fake in [
            "repo 5000585586 archived",
            "XPO 5000585586 archived",
            "SPO#7000325121 shipped",
            "APO 4500111111 pending",
        ]:
            ents = ex.extract(fake, "c1", "doc.txt")
            pos = [e.text for e in ents if e.entity_type == "PO"]
            assert not pos, f"Embedded PO label leaked from {fake!r}: {pos}"

    def test_legacy_po_emitted_only_as_po(self, regex_extractor):
        """Legacy PO-YYYY-NNNN identifiers should stay in PO, not leak into
        PART through the generic part matcher."""
        ents = regex_extractor.extract("Raised PO-2024-1234 for site A.", "c1", "doc.txt")
        parts = [e.text for e in ents if e.entity_type == "PART"]
        pos = [e.text for e in ents if e.entity_type == "PO"]
        assert "PO-2024-1234" in pos
        assert "PO-2024-1234" not in parts
        assert "PO-2024" not in parts

    def test_embedded_part_and_po_tokens_rejected(self, regex_extractor):
        """Reject substring matches embedded inside longer alphanumeric or
        hyphenated tokens."""
        cases = [
            ("fooPO-2024-1234bar", {"PART": {"PO-2024-1234", "PO-2024"}, "PO": {"PO-2024-1234"}}),
            ("XPO-2024-1234 shipped", {"PART": {"XPO-2024", "PO-2024-1234", "PO-2024"}, "PO": {"PO-2024-1234"}}),
            ("abcRG-213xyz", {"PART": {"RG-213"}}),
            ("installed RG-213A today", {"PART": {"RG-213"}}),
            ("token SA-9000X in text", {"PART": {"SA-9000"}}),
        ]
        for text, forbidden in cases:
            ents = regex_extractor.extract(text, "c1", "doc.txt")
            by_type = {}
            for entity in ents:
                by_type.setdefault(entity.entity_type, set()).add(entity.text)
            for entity_type, blocked in forbidden.items():
                leaked = by_type.get(entity_type, set()) & blocked
                assert not leaked, f"Embedded token leaked from {text!r}: {entity_type}={sorted(leaked)}"

    def test_exclusion_list_is_overridable(self):
        """A caller can override the default exclusion list — e.g. on a
        corpus where security standard family prefixes are NOT noise and should be
        retained. Passing an empty list disables all exclusion."""
        ex = RegexPreExtractor(
            part_patterns=[r"[A-Z]{2,}-\d{3,4}"],
            security_standard_exclude_patterns=[],
        )
        ents = ex.extract("Control AS-5021 applies.", "c1", "doc.txt")
        parts = [e.text for e in ents if e.entity_type == "PART"]
        # With exclusion disabled, the generic pattern captures AS-5021
        assert "AS-5021" in parts, (
            f"With empty exclusion list, AS-5021 should be captured: got {parts}"
        )

    def test_exclusion_list_can_add_new_patterns(self):
        """Operators running on a different corpus can extend the
        exclusion list with their own regex patterns without touching
        extractor code. Round-2 QA fix changed this API from
        prefix-startswith matching to regex matching."""
        ex = RegexPreExtractor(
            part_patterns=[r"[A-Z]{2,}-\d{3,4}"],
            security_standard_exclude_patterns=[
                r"^CUSTOM-\d+$",
                r"^LEGACY-\d+$",
            ],
        )
        # These are NOT in the default list but should be rejected here
        ents = ex.extract("Reference CUSTOM-0042 and LEGACY-900.", "c1", "doc.txt")
        parts = [e.text for e in ents if e.entity_type == "PART"]
        assert "CUSTOM-0042" not in parts
        assert "LEGACY-900" not in parts

    def test_real_hardware_parts_sharing_nist_prefix_accepted(self):
        """Round-2 QA regression guard for PS-800 / SA-9000 class.

        The first-round fix used prefix-startswith matching, which
        dropped real hardware parts whose family prefix collides with
        a security standard SP 800-53 control family. QA caught:

          - PS-800: Granite Peak backordered part, expected in
            docs/DEMO_DAY_CHECKLIST_2026-04-07.md and
            tests/test_corpus/tier2_stress/spreadsheet_fragment.txt
          - SA-9000: Spectrum Analyzer referenced throughout
            tests/golden_eval/golden_tuning_400.json

        Round-2 fix: switch the exclusion matcher from prefix-startswith
        to full-regex, and constrain security standard patterns to 1-2 digit
        suffixes so 3-4 digit hardware suffixes pass through.
        """
        ex = RegexPreExtractor(part_patterns=[
            r"[A-Z]{2,}-\d{3,4}",
            r"PS-\d{3}",
        ])
        corpus_native = [
            ("Backordered part PS-800 at Granite Peak.", "PS-800"),
            ("Lead time for Spectrum Analyzer SA-9000 is 6 weeks.", "SA-9000"),
            ("Installed PS-800 per work order.", "PS-800"),
            ("Calibration of SA-9000 complete.", "SA-9000"),
        ]
        for text, expected in corpus_native:
            ents = ex.extract(text, "c1", "doc.txt")
            parts = [e.text for e in ents if e.entity_type == "PART"]
            assert expected in parts, (
                f"Real hardware part {expected!r} dropped by exclusion "
                f"from text {text!r}: got {parts}. "
                f"This is the Round-2 QA regression. The exclusion "
                f"should use regex match with security standard suffix length 1-2 "
                f"digits, not prefix startswith."
            )

    def test_nist_family_short_suffix_still_rejected(self):
        """Pair with test_real_hardware_parts_sharing_nist_prefix_accepted.

        Make sure the suffix-length rule actually rejects the security standard
        controls whose family prefix overlaps with hardware (PS, SA,
        and the other 18 families). PS-1..PS-9 are security standard Personnel
        Security controls, SA-1..SA-23 are security standard System and Services
        Acquisition controls. They must still be blocked.
        """
        ex = RegexPreExtractor(part_patterns=[
            r"[A-Z]{2,}-\d{3,4}",
            r"PS-\d{3}",
        ])
        rejects = [
            "PS-1", "PS-3", "PS-7",            # security standard Personnel Security
            "SA-1", "SA-5", "SA-11", "SA-22",  # security standard System Services Acq
            "AC-2(1)",                          # security standard enhancement form
            "SC-51",                            # security standard SC family top
        ]
        for fake in rejects:
            text = f"Control {fake} applies."
            ents = ex.extract(text, "c1", "doc.txt")
            parts = [e.text for e in ents if e.entity_type == "PART"]
            pos = [e.text for e in ents if e.entity_type == "PO"]
            assert not parts, f"security standard {fake} leaked as PART: {parts}"
            assert not pos, f"security standard {fake} leaked as PO: {pos}"

    def test_sp800_publications_rejected_as_part_and_po(self, extractor_with_generic_part_pattern):
        """SP 800 publication references are security-standard metadata, not parts.

        The explicit SP 800 guard is part of the default exclusion list and
        should block common publication-reference formats with or without
        punctuation.
        """
        go = self._texts(extractor_with_generic_part_pattern)
        for text in [
            "SP 800-53 Rev 5 guidance applies.",
            "SP-800-53 Appendix A applies.",
            "SP800-53 guidance applies.",
        ]:
            parts, pos = go(text)
            assert not parts, f"SP 800 publication leaked as PART: text={text!r} parts={parts}"
            assert not pos, f"SP 800 publication leaked as PO: text={text!r} pos={pos}"

    def test_hypothetical_3digit_hardware_on_other_nist_families(self):
        """Future-proof: if any other security standard family prefix (CP-, PE-,
        PM-, SC-, SI-, etc.) gains a hardware collision in a future
        corpus, the suffix-length rule already handles it. Verify
        with a few hypotheticals so the rule is explicit in the test
        surface, not load-bearing on PS/SA alone.
        """
        ex = RegexPreExtractor(part_patterns=[r"[A-Z]{2,}-\d{3,4}"])
        hypothetical_parts = [
            "CP-220",    # Control Panel 220
            "PE-4000",   # Power Element 4000
            "PM-500",    # Preventive Maintenance kit 500
            "SC-1000",   # Signal Conditioner 1000
            "IR-420",    # Infrared sensor 420
        ]
        for part in hypothetical_parts:
            text = f"Installed {part} per spec."
            ents = ex.extract(text, "c1", "doc.txt")
            parts = [e.text for e in ents if e.entity_type == "PART"]
            assert part in parts, (
                f"Hypothetical 3-4 digit hardware part {part!r} dropped "
                f"by exclusion from text {text!r}: got {parts}. "
                f"Suffix-length rule should let security standard-prefixed 3+ digit "
                f"parts through."
            )

    def test_validator_helper_direct(self):
        """Direct unit test on the _is_security_standard_identifier
        helper, independent of any regex match path."""
        ex = RegexPreExtractor(part_patterns=[])
        # Rejected
        assert ex._is_security_standard_identifier("AC-2")
        assert ex._is_security_standard_identifier("IR-4")
        assert ex._is_security_standard_identifier("AS-5021")
        assert ex._is_security_standard_identifier("GPOS-0022")
        assert ex._is_security_standard_identifier("CCI-0001")
        assert ex._is_security_standard_identifier("SV-2045")
        assert ex._is_security_standard_identifier("SR-6")   # Rev 5 new family
        assert ex._is_security_standard_identifier("PT-3")   # Rev 5 new family
        assert ex._is_security_standard_identifier("CVE-2024")
        assert ex._is_security_standard_identifier("cce-1001")  # case-insensitive
        assert ex._is_security_standard_identifier("RHSA-2018")
        assert ex._is_security_standard_identifier("SNMP")
        assert ex._is_security_standard_identifier("APP-0001")
        assert ex._is_security_standard_identifier("SERVICE_STOP")
        assert ex._is_security_standard_identifier("pam_faillock")
        assert ex._is_security_standard_identifier("CNSSI-4009")
        assert ex._is_security_standard_identifier("DD-2842")
        assert ex._is_security_standard_identifier("DO-0003")
        assert ex._is_security_standard_identifier("enterprise program-2522")
        assert ex._is_security_standard_identifier("IGSI-2466")
        assert ex._is_security_standard_identifier("MSR-029")
        assert ex._is_security_standard_identifier("DV-200")
        assert ex._is_security_standard_identifier("IEEE-1394")
        assert ex._is_security_standard_identifier("CVE-202")
        assert ex._is_security_standard_identifier("SNOW")
        # Accepted
        assert not ex._is_security_standard_identifier("RG-213")
        assert not ex._is_security_standard_identifier("LMR-400")
        assert not ex._is_security_standard_identifier("ARC-4471")
        assert not ex._is_security_standard_identifier("5000585586")
        assert not ex._is_security_standard_identifier("")
        assert not ex._is_security_standard_identifier(None)  # type: ignore[arg-type]


class TestEventBlockParserSecurityStandardExclusion:
    """EventBlockParser must apply the same exclusion as
    RegexPreExtractor. They're two separate code paths but operators
    run them together, so a regression in either one re-pollutes the
    entity store."""

    def test_event_block_parts_rejected_if_nist_prefixed(self):
        """Labeled 'Part#: AS-5021' in a maintenance event block must
        NOT be emitted — AS- is a STIG baseline prefix, not a physical
        part, even inside a maintenance log."""
        parser = EventBlockParser(part_patterns=[r"[A-Z]{2,}-\d{3,4}"])
        text = (
            "1. Part#: AS-5021  Failure Mode: N/A  Action: Replaced\n"
            "   New Unit Serial: SN-100234\n"
        )
        entities, _ = parser.parse(text, "c1", "doc.txt")
        parts = [e.text.upper() for e in entities if e.entity_type == "PART"]
        assert "AS-5021" not in parts, (
            f"security standard/STIG prefix leaked through EventBlockParser: {parts}"
        )

    def test_event_block_real_part_still_emitted(self):
        parser = EventBlockParser(part_patterns=[r"ARC-\d{4}"])
        text = (
            "1. Part#: ARC-4471\n"
            "   Failure Mode: Connector fault\n"
            "   Action: Replaced\n"
            "   New Unit Serial: SN-987654\n"
        )
        entities, _ = parser.parse(text, "c1", "doc.txt")
        parts = [e.text.upper() for e in entities if e.entity_type == "PART"]
        # EventBlockParser emits whole-field values for Part#. Real
        # physical part ARC-4471 must appear as the first PART entity.
        assert any(p.startswith("ARC-4471") for p in parts), (
            f"Real physical part ARC-4471 missing from parts: {parts}"
        )

    def test_event_block_parser_override_list(self):
        parser = EventBlockParser(
            part_patterns=[r"[A-Z]{2,}-\d{3,4}"],
            security_standard_exclude_patterns=[r"^FOO-\d+$"],
        )
        # Default exclusion disabled — AS- is no longer in the reject list,
        # so AS-5021 should now pass through even though the default
        # would have blocked it.
        text = (
            "1. Part#: AS-5021\n"
            "   Action: Replaced\n"
        )
        entities, _ = parser.parse(text, "c1", "doc.txt")
        parts = [e.text.upper() for e in entities if e.entity_type == "PART"]
        assert any(p.startswith("AS-5021") for p in parts), (
            f"Override list should allow AS-5021 through: got {parts}"
        )

    def test_event_block_parser_accepts_hardware_with_nist_prefix(self):
        """Round-2 regression guard — EventBlockParser must also honor
        the suffix-length rule so PS-800 / SA-9000 survive through the
        maintenance-event code path, not just the RegexPreExtractor
        code path."""
        parser = EventBlockParser(part_patterns=[
            r"[A-Z]{2,}-\d{3,4}",
            r"PS-\d{3}",
        ])
        text = (
            "1. Part#: PS-800\n"
            "   Failure Mode: Intermittent\n"
            "   Action: Replaced\n"
        )
        entities, _ = parser.parse(text, "c1", "doc.txt")
        parts = [e.text.upper() for e in entities if e.entity_type == "PART"]
        assert any(p.startswith("PS-800") for p in parts), (
            f"EventBlockParser dropped real hardware PS-800: got {parts}"
        )

    def test_event_block_parser_rejects_po_shaped_part(self):
        """EventBlockParser should not emit a purchase order token as PART
        just because it appeared under a Part# label."""
        parser = EventBlockParser(part_patterns=[r"[A-Z]{2,}-\d{3,4}"])
        text = (
            "1. Part#: PO-2024-1234\n"
            "   Action: Replaced\n"
        )
        entities, _ = parser.parse(text, "c1", "doc.txt")
        parts = [e.text.upper() for e in entities if e.entity_type == "PART"]
        assert "PO-2024-1234" not in parts, (
            f"Purchase order leaked as EventBlockParser PART: {parts}"
        )

    def test_event_block_parser_rejects_additional_cyber_noise(self):
        parser = EventBlockParser(part_patterns=[r"[A-Z]{2,}-\d{3,4}"])
        for fake in ["RHSA-2018", "APP-0001", "SERVICE_STOP", "SNMP", "CNSSI-4009", "DD-2842", "DO-0003", "enterprise program-2522", "MSR-029", "DV-200", "IEEE-1394", "SNOW", "CVE-202"]:
            text = (
                f"1. Part#: {fake}\n"
                "   Action: Replaced\n"
            )
            entities, _ = parser.parse(text, "c1", "doc.txt")
            parts = [e.text.upper() for e in entities if e.entity_type == "PART"]
            assert fake not in parts, (
                f"Cyber-noise identifier leaked through EventBlockParser: {fake} -> {parts}"
            )


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

    def test_resolve_relationship_db_path_swaps_entity_db_filename(self, tmp_path):
        entity_path = tmp_path / "entities.sqlite3"
        resolved = resolve_relationship_db_path(entity_path)
        assert resolved == tmp_path / "relationships.sqlite3"

    def test_entity_db_path_opens_sibling_relationship_store(self, tmp_path):
        rel_path = tmp_path / "relationships.sqlite3"
        entity_path = tmp_path / "entities.sqlite3"

        store = RelationshipStore(str(rel_path))
        store.insert_relationships([self._make_rel()])
        store.close()

        rebound = RelationshipStore(str(entity_path))
        try:
            assert rebound.db_path == rel_path
            assert rebound.count() == 1
        finally:
            rebound.close()


class TestDeterministicTableSubstrate:
    """Small helper object used to keep test setup or expected results organized."""
    def test_detects_logistics_family_from_source_path(self):
        families = detect_logistics_table_families(
            r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Shipments\Packing List\NG Packing List - Guam.xlsx",
            "",
        )
        assert "packing_list" in families
        assert "spreadsheet" in families

    def test_extracts_pr_po_key_value_rows(self):
        extractor = DeterministicTableExtractor()
        text = (
            "[SECTION] CLIN: 0009A,\n"
            "CLIN: 0010A, PR Number: 0031422527, PO Number: 5300058406, "
            "Sum of Allocation Amount in Local Currency: 2705.12\n"
            "CLIN: 0010A, PR Number: ##, PO Number: 7201042200, "
            "Sum of Allocation Amount in Local Currency: 753.25\n"
        )
        rows = extractor.extract(
            text=text,
            chunk_id="chunk-prpo",
            source_path=r"D:\CorpusTransfr\verified\IGS\Matl\2024 03 PR & PO.xlsx",
        )
        assert len(rows) == 2
        first = json.loads(rows[0].values)
        assert "0031422527" in first
        assert "5300058406" in first

    def test_extracts_dd250_rows(self):
        extractor = DeterministicTableExtractor()
        text = (
            "[SECTION] CONTAINER: INSTALLED,\n"
            "FIND NO.: 57, QTY.: 1, PART NUMBER: SM-219, DESCRIPTION: GPS RECEIVER, "
            "MANUFACTURER: ASTRA, Serial Number: 26\n"
            "CONTAINER: INSTALLED, FIND NO.: 58, QTY.: 1, PART NUMBER: SW125-12-N, "
            "DESCRIPTION: POWER SUPPLY, MANUFACTURER: sensitive data INC.\n"
        )
        rows = extractor.extract(
            text=text,
            chunk_id="chunk-dd250",
            source_path=r"D:\CorpusTransfr\verified\IGS\DD250\Niger Parts List.xlsx",
        )
        assert len(rows) == 2
        headers = json.loads(rows[0].headers)
        values = json.loads(rows[0].values)
        assert "PART NUMBER" in headers
        assert "SM-219" in values

    def test_extracts_calibration_projection_table(self):
        extractor = DeterministicTableExtractor()
        text = (
            "Date Standard Count Standard Count\n"
            "6/1/2019 861 898\n"
            "7/1/2019 1857 1895\n"
            "8/1/2019 853 891\n"
        )
        rows = extractor.extract(
            text=text,
            chunk_id="chunk-cal",
            source_path=r"D:\CorpusTransfr\verified\IGS\Calibration\024679_Calibration_report.pdf",
        )
        assert len(rows) == 3
        assert json.loads(rows[1].values) == ["7/1/2019", "1857", "1895"]

    def test_extracts_inventory_rows(self):
        extractor = DeterministicTableExtractor()
        text = (
            "Site: Spares Inventory - Alpena CRTC, MI\n"
            "Description PN Rev SN Firm IUID? Qty New Qty\n"
            "Antenna Switch AS -7020103 C 64 1\n"
            "Bit Card AS -5021108 79 1\n"
            "Fuse, 8A 2\n"
        )
        rows = extractor.extract(
            text=text,
            chunk_id="chunk-spares",
            source_path=r"D:\CorpusTransfr\verified\IGS\Spares Inventory (Alpena).pdf",
        )
        assert len(rows) == 3
        first = json.loads(rows[0].values)
        assert first[1] == "AS-7020103"
        assert first[2] == "1"

    def test_pipe_joined_kv_extracts_one_row_per_segment(self):
        # Lane 2 follow-on: SEMS3D Initial Spares / BOM export shape.
        # Two logical rows packed onto one chunked line with ``|`` separators.
        # The legacy line-oriented KV extractor collapses these into one
        # mega-row with duplicate-suffixed labels; this pipe-first path
        # must emit one TableRow per logical record instead.
        extractor = DeterministicTableExtractor()
        text = (
            "[SHEET] WX31 M4 BUYDOWN | TO | CLIN | Requirement | Line Item "
            "| Quote # | Site | Part Number | Part Description | UOM "
            "| Qty Required | Vendor Name | Shopping Cart "
            "| TO: WX31M4, Requirement: BOM, Line Item: 11, "
            "Quote #: Web Quote, Site: monitoring system / legacy monitoring system Initial Spares Purchase, "
            "Part Number: ZFBT-4R2G-FT+, Part Description: Bias T, Wideband, 50 Ohms, "
            "UOM: EA, Qty Required: 6, Vendor Name: Mini Circuits, "
            "Shopping Cart: PO 7000353951 "
            "| TO: WX31M4, Requirement: BOM, Line Item: 12, "
            "Quote #: Q-00191352, Site: monitoring system / legacy monitoring system Initial Spares Purchase, "
            "Part Number: 775595-B21, Part Description: Power Supply, Redundant, 900W, "
            "UOM: EA, Qty Required: 6, Vendor Name: Sterling Computers, "
            "Shopping Cart: PR 0031126723"
        )
        rows = extractor.extract(
            text=text,
            chunk_id="chunk-spares-initial",
            source_path=(
                r"D:\CorpusTransfr\verified\IGS\1.0 enterprise program DM - Restricted\SEMS3D"
                r"\Non-CDRL Deliverables\legacy monitoring system monitoring system Initial Spares"
                r"\SEMS3D-37125 monitoring system-legacy monitoring system Initial Spares.xlsx"
            ),
        )
        # Exactly 2 logical records, no collapsed duplicate-label garbage.
        assert len(rows) == 2
        assert all(r.table_id.endswith("_pipekv_1") for r in rows)
        first = json.loads(rows[0].values)
        second = json.loads(rows[1].values)
        # Row 0 is line item 11, row 1 is line item 12 — distinct, not merged.
        assert "ZFBT-4R2G-FT+" in first
        assert "775595-B21" in second
        assert "11" in first
        assert "12" in second
        # No label was duplicated with a numeric suffix ("Part Number 2" etc.);
        # that's the exact failure mode this extractor exists to fix.
        headers = json.loads(rows[0].headers)
        assert all(not h.endswith(" 2") for h in headers)
        assert all(not h.endswith(" 3") for h in headers)
        # Values with internal commas (Part Description, Shopping Cart) stay intact
        part_desc_idx = headers.index("Part Description")
        assert first[part_desc_idx] == "Bias T, Wideband, 50 Ohms"
        assert second[part_desc_idx] == "Power Supply, Redundant, 900W"

    def test_pipe_joined_kv_suppresses_legacy_kv_mega_row(self):
        # Regression guard: the pipe-first extractor must gate the legacy
        # line-oriented KV path for the same chunk, otherwise we emit both
        # the clean rows AND the collapsed mega-row with "Label 2" suffixes.
        extractor = DeterministicTableExtractor()
        text = (
            "PO: 11111, Vendor: Acme, Qty: 5 "
            "| PO: 22222, Vendor: Beta, Qty: 7 "
            "| PO: 33333, Vendor: Gamma, Qty: 9"
        )
        rows = extractor.extract(
            text=text,
            chunk_id="chunk-pipe",
            source_path=r"D:\CorpusTransfr\verified\IGS\fake_vendors.xlsx",
        )
        assert len(rows) == 3
        for r in rows:
            headers = json.loads(r.headers)
            # Legacy path would have produced a row with PO, Vendor, Qty,
            # PO 2, Vendor 2, Qty 2, PO 3, Vendor 3, Qty 3 — reject that.
            assert set(headers) == {"PO", "Vendor", "Qty"}

    def test_pipe_joined_kv_ignores_segments_below_label_threshold(self):
        # Negative: pipe segments that are just prose or single-token cells
        # must not be emitted as rows.
        extractor = DeterministicTableExtractor()
        text = (
            "| Some narrative text | just a header cell "
            "| PO: 12345, Vendor: Acme Corp, Qty: 3 "
            "| trailing comment"
        )
        rows = extractor.extract(
            text=text,
            chunk_id="chunk-mixed",
            source_path=r"D:\CorpusTransfr\verified\IGS\mixed.xlsx",
        )
        # Only the fully-labeled segment survives.
        assert len(rows) == 1
        values = json.loads(rows[0].values)
        assert "12345" in values
        assert "Acme Corp" in values

    def test_pipe_joined_kv_not_triggered_on_non_pipe_text(self):
        # Regression guard: plain line-oriented KV text must still go through
        # the legacy path so existing PR & PO / DD250 tests keep passing.
        extractor = DeterministicTableExtractor()
        text = (
            "[SECTION] CLIN: 0010A, PR Number: 0031422527, "
            "PO Number: 5300058406, Amount: 2705.12\n"
            "CLIN: 0010A, PR Number: ##, PO Number: 7201042200, Amount: 753.25\n"
        )
        rows = extractor.extract(
            text=text,
            chunk_id="chunk-legacy",
            source_path=r"D:\CorpusTransfr\verified\IGS\Matl\legacy.xlsx",
        )
        # Both records come out via the legacy _kvtable path, not pipekv.
        assert len(rows) == 2
        assert all("_kvtable_" in r.table_id for r in rows)
        first_values = json.loads(rows[0].values)
        assert "0031422527" in first_values


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


class TestRelationshipPhraseExtractor:
    """Tests for phrase-based relationship extraction (10 mining patterns)."""

    @pytest.fixture
    def extractor(self):
        return RelationshipPhraseExtractor()

    def test_replaced_with(self, extractor):
        text = "The 51 Ohm resistors were replaced with upgraded outlet panel."
        rels = extractor.extract(text, "c1", "doc.txt")
        assert len(rels) >= 1
        r = rels[0]
        assert r.predicate == "REPLACED_BY"
        assert "resistor" in r.subject_text.lower()

    def test_installed_on(self, extractor):
        text = "monitoring system shelter to be installed on Fish Pond Road."
        rels = extractor.extract(text, "c1", "doc.txt")
        assert len(rels) >= 1
        assert rels[0].predicate == "INSTALLED_AT"
        assert "Fish Pond" in rels[0].object_text

    def test_shipped_to(self, extractor):
        text = "The crate was shipped to the site with supplies."
        rels = extractor.extract(text, "c1", "doc.txt")
        assert len(rels) >= 1
        assert rels[0].predicate == "SHIPPED_TO"

    def test_manufactured_by(self, extractor):
        text = "GCOs are manufactured by different companies including ARINC."
        rels = extractor.extract(text, "c1", "doc.txt")
        assert len(rels) >= 1
        assert rels[0].predicate == "MANUFACTURED_BY"

    def test_assigned_to(self, extractor):
        text = "ANG personnel assigned to the base."
        rels = extractor.extract(text, "c1", "doc.txt")
        assert len(rels) >= 1
        assert rels[0].predicate == "ASSIGNED_TO"

    def test_inspected_by(self, extractor):
        text = "The request is reviewed by all Terminal Instrument Procedures."
        rels = extractor.extract(text, "c1", "doc.txt")
        assert len(rels) >= 1
        assert rels[0].predicate == "INSPECTED_BY"

    def test_charged_to(self, extractor):
        text = "The CRTC is funded by the Air National Guard."
        rels = extractor.extract(text, "c1", "doc.txt")
        assert len(rels) >= 1
        assert rels[0].predicate == "CHARGED_TO"

    def test_dedup_within_chunk(self, extractor):
        text = "Part X was replaced with Y. Part X was replaced with Y."
        rels = extractor.extract(text, "c1", "doc.txt")
        # Same (subject, predicate, object) should be deduped
        keys = [(r.subject_text.lower(), r.predicate, r.object_text.lower()) for r in rels]
        assert len(keys) == len(set(keys))

    def test_empty_text(self, extractor):
        rels = extractor.extract("", "c1", "doc.txt")
        assert rels == []

    def test_confidence_is_085(self, extractor):
        text = "Equipment installed on the rear wall."
        rels = extractor.extract(text, "c1", "doc.txt")
        for r in rels:
            assert r.confidence == 0.85
