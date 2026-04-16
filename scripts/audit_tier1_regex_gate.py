"""
Tier 1 regex acceptance gate for pre-rerun use.

This is a read-only harness. It does not run a Tier 1 rerun and does not
persist anything. The gate answers one operator question:

    Is the current RegexPreExtractor configuration safe enough to rerun?

It combines:
1. Curated adversarial and true-positive cases derived from existing
   tests/docs.
2. An optional live-store sample audit against the current LanceDB store.
3. A simple PASS / FAIL verdict with JSON-serializable detail.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

v2_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(v2_root))

from src.config.schema import load_config  # noqa: E402
from src.extraction.entity_extractor import RegexPreExtractor  # noqa: E402

STRATA = ("security_candidate", "phone_candidate", "other")
PHONE_CANDIDATE_RE = re.compile(
    r"(?<![\w.-])"
    r"(?:\+?1[\s.-]?)?"
    r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
    r"(?!\w)(?!\.[A-Za-z0-9])(?!-\w)"
)


@dataclass(frozen=True)
class GateExpectation:
    """Structured helper object used by the audit tier1 regex gate workflow."""
    entity_type: str
    text: str


@dataclass(frozen=True)
class GateCase:
    """Structured input record that keeps one unit of work easy to pass around and inspect."""
    name: str
    text: str
    must_have: tuple[GateExpectation, ...] = ()
    must_not_have: tuple[GateExpectation, ...] = ()
    source_ref: str = ""


@dataclass(frozen=True)
class SampleChunk:
    """Structured helper object used by the audit tier1 regex gate workflow."""
    chunk_id: str
    source_path: str
    text: str
    stratum: str = "other"


@dataclass
class SampleSelection:
    """Structured helper object used by the audit tier1 regex gate workflow."""
    chunks: list[SampleChunk]
    scanned_chunks: int
    sample_mode: str
    stratum_seen: dict[str, int]


@dataclass
class CaseOutcome:
    """Structured helper object used by the audit tier1 regex gate workflow."""
    name: str
    ok: bool
    source_ref: str
    details: list[str] = field(default_factory=list)


@dataclass
class SampleOutcome:
    """Structured helper object used by the audit tier1 regex gate workflow."""
    total_chunks: int
    scanned_chunks: int
    sample_mode: str
    extracted_entities: int
    stratum_selected: dict[str, int] = field(default_factory=dict)
    stratum_seen: dict[str, int] = field(default_factory=dict)
    dangerous_hits: list[str] = field(default_factory=list)
    invalid_phone_hits: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    top_entities: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.dangerous_hits and not self.invalid_phone_hits


@dataclass
class GateReport:
    """Small structured record used to keep related results together as the workflow runs."""
    curated_total: int
    curated_pass: int
    curated_fail: int
    sample: SampleOutcome | None
    cases: list[CaseOutcome]

    @property
    def ok(self) -> bool:
        return self.curated_fail == 0 and (self.sample is None or self.sample.ok)


def curated_cases() -> list[GateCase]:
    """Cases are pinned to existing repo evidence, not invented corpora."""
    return [
        GateCase(
            name="security-standard-as",
            text="Control AS-5021 applies.",
            must_not_have=(GateExpectation("PART", "AS-5021"), GateExpectation("PO", "AS-5021")),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="security-standard-os",
            text="See OS-0004 for platform guidance.",
            must_not_have=(GateExpectation("PART", "OS-0004"), GateExpectation("PO", "OS-0004")),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="security-standard-gpos",
            text="GPOS-0022 defines the policy requirement.",
            must_not_have=(GateExpectation("PART", "GPOS-0022"), GateExpectation("PO", "GPOS-0022")),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="security-standard-cci",
            text="CCI-0001 maps to the control.",
            must_not_have=(GateExpectation("PART", "CCI-0001"), GateExpectation("PO", "CCI-0001")),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="security-standard-sv",
            text="Finding SV-2045 was remediated.",
            must_not_have=(GateExpectation("PART", "SV-2045"), GateExpectation("PO", "SV-2045")),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="security-standard-cve",
            text="Reference CVE-2024 was checked.",
            must_not_have=(GateExpectation("PART", "CVE-2024"), GateExpectation("PO", "CVE-2024")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="security-standard-cce",
            text="Reference CCE-2720 was checked.",
            must_not_have=(GateExpectation("PART", "CCE-2720"), GateExpectation("PO", "CCE-2720")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="security-standard-ps1",
            text="Control PS-1 applies.",
            must_not_have=(GateExpectation("PART", "PS-1"), GateExpectation("PO", "PS-1")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="security-standard-sa11",
            text="Control SA-11 applies.",
            must_not_have=(GateExpectation("PART", "SA-11"), GateExpectation("PO", "SA-11")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="security-standard-sc51",
            text="Control SC-51 applies.",
            must_not_have=(GateExpectation("PART", "SC-51"), GateExpectation("PO", "SC-51")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="security-standard-ir4",
            text="Control IR-4 applies.",
            must_not_have=(GateExpectation("PART", "IR-4"), GateExpectation("PO", "IR-4")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="security-standard-pt3",
            text="Control PT-3 applies.",
            must_not_have=(GateExpectation("PART", "PT-3"), GateExpectation("PO", "PT-3")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="security-standard-sr6",
            text="Control SR-6 applies.",
            must_not_have=(GateExpectation("PART", "SR-6"), GateExpectation("PO", "SR-6")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="security-standard-sp800",
            text="SP 800-53 Rev 5 guidance applies.",
            must_not_have=(GateExpectation("PART", "SP 800-53"), GateExpectation("PO", "SP 800-53")),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="phone-garbage-repeat",
            text="Value in table: 3333333344 end",
            must_not_have=(GateExpectation("CONTACT", "3333333344"),),
            source_ref="tests/test_extraction.py + docs/PHONE_REGEX_FIX_2026-04-11.md",
        ),
        GateCase(
            name="phone-garbage-bare-10-digit",
            text="Tracking 7000123456 in transit.",
            must_not_have=(GateExpectation("PO", "7000123456"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="phone-garbage-embedded",
            text="555-234-5678.example.com",
            must_not_have=(GateExpectation("CONTACT", "555-234-5678"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="phone-garbage-long-run",
            text="Serial 12345678901234",
            must_not_have=(GateExpectation("CONTACT", "1234567890"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="phone-real-parentheses",
            text="Call (555) 234-5678 today.",
            must_have=(GateExpectation("CONTACT", "(555) 234-5678"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="phone-real-country-code",
            text="Reach +1 555 234 5678.",
            must_have=(GateExpectation("CONTACT", "+1 555 234 5678"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="phone-real-punctuation",
            text="Phone: 555-234-5678!",
            must_have=(GateExpectation("CONTACT", "555-234-5678"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="date-iso",
            text="Scheduled for 2025-06-15.",
            must_have=(GateExpectation("DATE", "2025-06-15"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="date-slash",
            text="Report date: 3/15/2025.",
            must_have=(GateExpectation("DATE", "3/15/2025"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="date-month-name",
            text="Completed on March 15, 2025.",
            must_have=(GateExpectation("DATE", "March 15, 2025"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="po-label",
            text="Raised PO 5000585586 to Grainger.",
            must_have=(GateExpectation("PO", "5000585586"),),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="po-period-label",
            text="P.O. 4500111111 pending.",
            must_have=(GateExpectation("PO", "4500111111"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="po-purchase-order-label",
            text="Purchase Order: 7000354926 approved.",
            must_have=(GateExpectation("PO", "7000354926"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="part-arc",
            text="Replaced ARC-4471 RF connector.",
            must_have=(GateExpectation("PART", "ARC-4471"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="part-lmr",
            text="Used LMR-400 for the run.",
            must_have=(GateExpectation("PART", "LMR-400"),),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="part-rg",
            text="Installed RG-213 coax cable.",
            must_have=(GateExpectation("PART", "RG-213"),),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="part-ps800",
            text="Backordered part PS-800 at Granite Peak.",
            must_have=(GateExpectation("PART", "PS-800"),),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="part-sa9000",
            text="Lead time for Spectrum Analyzer SA-9000 is 6 weeks.",
            must_have=(GateExpectation("PART", "SA-9000"),),
            source_ref="tests/test_extraction.py + docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md",
        ),
        GateCase(
            name="report-fsr",
            text="Reference FSR-2025-001 for details.",
            must_have=(GateExpectation("PO", "FSR-2025-001"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="report-umr",
            text="See UMR-THULE-2025 for context.",
            must_have=(GateExpectation("PO", "UMR-THULE-2025"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="report-asv",
            text="Reference ASV-VAFB for details.",
            must_have=(GateExpectation("PO", "ASV-VAFB"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="report-rts",
            text="Archive RTS-DATA preserved.",
            must_have=(GateExpectation("PO", "RTS-DATA"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="report-fsr-l22",
            text="Reference FSR-L22 for details.",
            must_have=(GateExpectation("PO", "FSR-L22"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="field-site",
            text="Site: Thule Air Base\nPOC: SSgt Webb",
            must_have=(GateExpectation("SITE", "Thule Air Base"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="field-poc",
            text="Point of Contact: SSgt Marcus Webb",
            must_have=(GateExpectation("PERSON", "SSgt Marcus Webb"),),
            source_ref="tests/test_extraction.py",
        ),
        GateCase(
            name="field-technician",
            text="Technician: John Smith",
            must_have=(GateExpectation("PERSON", "John Smith"),),
            source_ref="tests/test_extraction.py",
        ),
    ]


def build_extractor() -> RegexPreExtractor:
    """Assemble the structured object this workflow needs for its next step."""
    config = load_config(str(v2_root / "config" / "config.yaml"))
    return RegexPreExtractor(
        part_patterns=config.extraction.part_patterns,
        security_standard_exclude_patterns=config.extraction.security_standard_exclude_patterns,
    )


def _has_entity(entities, entity_type: str, expected_text: str) -> bool:
    """Support the audit tier1 regex gate workflow by handling the has entity step."""
    return any(
        entity.entity_type == entity_type and entity.text == expected_text
        for entity in entities
    )


def evaluate_curated_cases(
    extractor: RegexPreExtractor,
    cases: Iterable[GateCase] | None = None,
) -> list[CaseOutcome]:
    """Support the audit tier1 regex gate workflow by handling the evaluate curated cases step."""
    outcomes: list[CaseOutcome] = []
    for idx, case in enumerate(cases or curated_cases(), start=1):
        entities = extractor.extract(case.text, f"curated-{idx}", "curated.txt")
        details: list[str] = []

        for expected in case.must_have:
            if not _has_entity(entities, expected.entity_type, expected.text):
                details.append(f"missing {expected.entity_type}:{expected.text}")

        for expected in case.must_not_have:
            if _has_entity(entities, expected.entity_type, expected.text):
                details.append(f"forbidden {expected.entity_type}:{expected.text}")

        outcomes.append(
            CaseOutcome(
                name=case.name,
                ok=not details,
                source_ref=case.source_ref,
                details=details,
            )
        )
    return outcomes


def classify_chunk_stratum(text: str, extractor: RegexPreExtractor) -> str:
    """Support the audit tier1 regex gate workflow by handling the classify chunk stratum step."""
    upper = text.upper()
    for token in re.findall(r"[A-Z0-9().-]+", upper):
        candidate = token.strip(",;:!?[]{}<>\"'")
        if candidate and any(pattern.match(candidate) for pattern in extractor._security_exclude_patterns):
            return "security_candidate"
    if any(pattern.search(upper) for pattern in extractor._security_exclude_patterns):
        return "security_candidate"
    if PHONE_CANDIDATE_RE.search(text):
        return "phone_candidate"
    return "other"


def _reservoir_add(
    reservoir: list[SampleChunk],
    seen_count: int,
    candidate: SampleChunk,
    capacity: int,
    rng: random.Random,
) -> int:
    """Support the audit tier1 regex gate workflow by handling the reservoir add step."""
    seen_count += 1
    if capacity <= 0:
        return seen_count
    if len(reservoir) < capacity:
        reservoir.append(candidate)
        return seen_count
    pick = rng.randrange(seen_count)
    if pick < capacity:
        reservoir[pick] = candidate
    return seen_count


def _iter_offset_rows(store, offsets: list[int], batch_size: int):
    """Support the audit tier1 regex gate workflow by handling the iter offset rows step."""
    table = store._table
    if table is None:
        return

    for start in range(0, len(offsets), batch_size):
        batch_offsets = offsets[start:start + batch_size]
        rows = (
            table.take_offsets(batch_offsets)
            .select(["chunk_id", "text", "source_path"])
            .to_list()
        )
        for row in rows:
            yield row.get("chunk_id"), row.get("text"), row.get("source_path")


def sample_chunks_from_store(
    extractor: RegexPreExtractor,
    sample_limit: int,
    seed: int,
    sample_mode: str,
    max_scan_chunks: int,
    batch_size: int = 2048,
) -> SampleSelection:
    """Support the audit tier1 regex gate workflow by handling the sample chunks from store step."""
    if sample_limit <= 0:
        return SampleSelection(
            chunks=[],
            scanned_chunks=0,
            sample_mode=sample_mode,
            stratum_seen={stratum: 0 for stratum in STRATA},
        )

    config = load_config(str(v2_root / "config" / "config.yaml"))
    store = None
    rng = random.Random(seed)
    fallback_capacity = max(sample_limit * 2, sample_limit)
    fallback_reservoir: list[SampleChunk] = []
    fallback_seen = 0
    stratum_seen = {stratum: 0 for stratum in STRATA}
    scanned_chunks = 0

    if sample_mode == "random":
        reservoirs = {"all": []}
        reservoir_seen = {"all": 0}
        reservoir_capacity = {"all": sample_limit}
    else:
        base = sample_limit // len(STRATA)
        remainder = sample_limit % len(STRATA)
        reservoir_capacity = {
            stratum: base + (1 if idx < remainder else 0)
            for idx, stratum in enumerate(STRATA)
        }
        reservoirs = {stratum: [] for stratum in STRATA}
        reservoir_seen = {stratum: 0 for stratum in STRATA}

    try:
        from src.store.lance_store import LanceStore  # noqa: WPS433

        store = LanceStore(str(v2_root / config.paths.lance_db))
        total_chunks = store.count()
        if total_chunks <= 0:
            return SampleSelection(
                chunks=[],
                scanned_chunks=0,
                sample_mode=sample_mode,
                stratum_seen=stratum_seen,
            )

        scan_offsets = rng.sample(range(total_chunks), min(max_scan_chunks, total_chunks))

        for chunk_id, text, source_path in _iter_offset_rows(store, scan_offsets, batch_size=batch_size):
            scanned_chunks += 1

            body = text or ""
            if not body.strip():
                continue

            stratum = classify_chunk_stratum(body, extractor)
            stratum_seen[stratum] += 1
            chunk = SampleChunk(
                chunk_id=chunk_id or f"sample-{scanned_chunks}",
                source_path=source_path or "",
                text=body,
                stratum=stratum,
            )

            fallback_seen = _reservoir_add(
                fallback_reservoir,
                fallback_seen,
                chunk,
                fallback_capacity,
                rng,
            )

            if sample_mode == "random":
                reservoir_seen["all"] = _reservoir_add(
                    reservoirs["all"],
                    reservoir_seen["all"],
                    chunk,
                    reservoir_capacity["all"],
                    rng,
                )
            else:
                reservoir_seen[stratum] = _reservoir_add(
                    reservoirs[stratum],
                    reservoir_seen[stratum],
                    chunk,
                    reservoir_capacity[stratum],
                    rng,
                )
    finally:
        if store is not None:
            store.close()

    if sample_mode == "random":
        selected = list(reservoirs["all"])
    else:
        selected = []
        seen_ids: set[str] = set()
        for stratum in STRATA:
            for chunk in reservoirs[stratum]:
                if chunk.chunk_id in seen_ids:
                    continue
                selected.append(chunk)
                seen_ids.add(chunk.chunk_id)
        for chunk in fallback_reservoir:
            if len(selected) >= sample_limit:
                break
            if chunk.chunk_id in seen_ids:
                continue
            selected.append(chunk)
            seen_ids.add(chunk.chunk_id)

    return SampleSelection(
        chunks=selected[:sample_limit],
        scanned_chunks=scanned_chunks,
        sample_mode=sample_mode,
        stratum_seen=stratum_seen,
    )


def evaluate_sample_selection(
    extractor: RegexPreExtractor,
    selection: SampleSelection,
) -> SampleOutcome:
    """Support the audit tier1 regex gate workflow by handling the evaluate sample selection step."""
    dangerous_hits: list[str] = []
    invalid_phone_hits: list[str] = []
    top_entities: list[dict] = []
    extracted_entities = 0
    stratum_selected = {stratum: 0 for stratum in STRATA}

    for chunk in selection.chunks:
        stratum_selected[chunk.stratum] = stratum_selected.get(chunk.stratum, 0) + 1
        entities = extractor.extract(chunk.text, chunk.chunk_id, chunk.source_path)
        for entity in entities:
            extracted_entities += 1
            if entity.entity_type in {"PART", "PO"} and extractor._is_security_standard_identifier(entity.text):
                dangerous_hits.append(
                    f"{chunk.chunk_id} [{chunk.source_path}] -> {entity.entity_type}:{entity.text}"
                )
            if (
                entity.entity_type == "CONTACT"
                and "@" not in entity.text
                and not RegexPreExtractor._is_valid_phone(entity.text)
            ):
                invalid_phone_hits.append(
                    f"{chunk.chunk_id} [{chunk.source_path}] -> CONTACT:{entity.text}"
                )
            if len(top_entities) < 20 and entity.entity_type in {"PART", "PO"}:
                top_entities.append(
                    {
                        "chunk_id": chunk.chunk_id,
                        "source_path": chunk.source_path,
                        "stratum": chunk.stratum,
                        "entity_type": entity.entity_type,
                        "text": entity.text,
                    }
                )

    warnings: list[str] = []
    if selection.sample_mode == "stratified":
        for stratum in STRATA:
            if selection.stratum_seen.get(stratum, 0) == 0:
                warnings.append(
                    f"scan window contained no {stratum} chunks; stratified coverage is incomplete"
                )

    return SampleOutcome(
        total_chunks=len(selection.chunks),
        scanned_chunks=selection.scanned_chunks,
        sample_mode=selection.sample_mode,
        extracted_entities=extracted_entities,
        stratum_selected=stratum_selected,
        stratum_seen=dict(selection.stratum_seen),
        dangerous_hits=dangerous_hits,
        invalid_phone_hits=invalid_phone_hits,
        warnings=warnings,
        top_entities=top_entities,
    )


def run_gate(
    sample_limit: int = 120,
    sample_seed: int = 42,
    sample_mode: str = "stratified",
    max_scan_chunks: int = 1000,
) -> GateReport:
    """Execute one complete stage of the workflow and return its results."""
    extractor = build_extractor()
    outcomes = evaluate_curated_cases(extractor)
    curated_pass = sum(1 for outcome in outcomes if outcome.ok)
    curated_fail = len(outcomes) - curated_pass

    sample = None
    if sample_limit > 0:
        try:
            selection = sample_chunks_from_store(
                extractor=extractor,
                sample_limit=sample_limit,
                seed=sample_seed,
                sample_mode=sample_mode,
                max_scan_chunks=max_scan_chunks,
            )
            if selection.chunks:
                sample = evaluate_sample_selection(extractor, selection)
        except Exception:
            sample = None

    return GateReport(
        curated_total=len(outcomes),
        curated_pass=curated_pass,
        curated_fail=curated_fail,
        sample=sample,
        cases=outcomes,
    )


def _print_report(report: GateReport) -> None:
    """Render a readable summary for the person running the tool."""
    print("=" * 72)
    print("TIER 1 REGEX ACCEPTANCE GATE")
    print("=" * 72)
    print(f"Curated cases: {report.curated_pass}/{report.curated_total} pass")
    if report.sample is None:
        print("Live-store sample: skipped")
    else:
        print(
            f"Live-store sample: {report.sample.total_chunks} selected / "
            f"{report.sample.scanned_chunks} scanned "
            f"({report.sample.sample_mode})"
        )
        print(f"Extracted entities from sample: {report.sample.extracted_entities}")
        if report.sample.sample_mode == "stratified":
            print(f"Strata seen: {report.sample.stratum_seen}")
            print(f"Strata selected: {report.sample.stratum_selected}")
        print(f"Dangerous PART/PO hits: {len(report.sample.dangerous_hits)}")
        print(f"Invalid phone hits: {len(report.sample.invalid_phone_hits)}")
        if report.sample.warnings:
            print("Sample warnings:")
            for warning in report.sample.warnings:
                print(f"  - {warning}")
    print()
    print("Curated failures:")
    failed = [case for case in report.cases if not case.ok]
    if not failed:
        print("  - none")
    else:
        for case in failed:
            print(f"  - {case.name}: {', '.join(case.details)}")
    print()
    print("Verdict:", "PASS" if report.ok else "FAIL")


def main(argv: list[str] | None = None) -> int:
    """Parse command-line inputs and run the main audit tier1 regex gate workflow."""
    parser = argparse.ArgumentParser(description="Tier 1 regex acceptance gate")
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=120,
        help="Selected live-store sample size; 0 disables sampling.",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="Random seed for the live-store sample.",
    )
    parser.add_argument(
        "--sample-mode",
        choices=("stratified", "random"),
        default="stratified",
        help="Live-store sampling mode.",
    )
    parser.add_argument(
        "--max-scan-chunks",
        type=int,
        default=1000,
        help="Maximum live-store chunks to scan before finalizing the sample.",
    )
    parser.add_argument(
        "--no-sample",
        action="store_true",
        help="Disable the live-store sample scan.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON report after the text summary.",
    )
    args = parser.parse_args(argv)

    sample_limit = 0 if args.no_sample else args.sample_limit
    report = run_gate(
        sample_limit=sample_limit,
        sample_seed=args.sample_seed,
        sample_mode=args.sample_mode,
        max_scan_chunks=args.max_scan_chunks,
    )
    _print_report(report)
    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
