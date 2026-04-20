"""
Failure-event extractor — populates failure_events.db from source_metadata + chunks.

Two extraction lanes:

  PATH-DERIVED  (fast, runs from retrieval_metadata.sqlite3 alone):
    - system detection via substring match on source_path
    - event_year from path date tokens
    - site_token inherited from source_metadata
    - One event row emitted per source_path when system + year detected

  CHUNK-DERIVED  (heavier, reads chunks.jsonl or LanceDB):
    - part_number regex against chunk text
    - failure-verb regex ("failed", "replaced due to", "fault", "anomaly")
    - One event row per (chunk_id, part_number) match

Path-derived runs first and is idempotent. Chunk-derived is additive.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from src.store.failure_events_store import FailureEvent, FailureEventsStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical system detection (loaded from config/canonical_aliases.yaml)
# ---------------------------------------------------------------------------

def _load_system_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Build system detection patterns from canonical_aliases.yaml."""
    from pathlib import Path
    import yaml as _yaml
    aliases_path = Path(__file__).resolve().parents[2] / "config" / "canonical_aliases.yaml"
    if not aliases_path.exists():
        logger.warning("canonical_aliases.yaml not found at %s — using empty system patterns", aliases_path)
        return ()
    with aliases_path.open("r", encoding="utf-8") as f:
        data = _yaml.safe_load(f) or {}
    patterns = []
    for canonical, info in (data.get("systems") or {}).items():
        all_names = [canonical] + list(info.get("aliases", []))
        for name in all_names:
            patterns.append((canonical, re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)))
    return tuple(patterns)

_SYSTEM_PATTERNS = _load_system_patterns()


def detect_system(text: str) -> str:
    """Return canonical system name or '' if none matches."""
    if not text:
        return ""
    for canonical, pat in _SYSTEM_PATTERNS:
        if pat.search(text):
            return canonical
    return ""


# ---------------------------------------------------------------------------
# Year extraction from path or text
# ---------------------------------------------------------------------------

_YEAR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(20[0-3]\d)[_\-/.]?(?:0[1-9]|1[0-2])\b"),     # 2024_03, 2024-03
    re.compile(r"\b(20[0-3]\d)\b"),                               # bare 2024
    re.compile(r"\bFY[_\-]?(20[0-3]\d)\b", re.IGNORECASE),        # FY2024
    re.compile(r"\bFY[_\-]?(\d{2})\b", re.IGNORECASE),            # FY24 → 20xx
    re.compile(r"\bCY[_\-]?(20[0-3]\d)\b", re.IGNORECASE),        # CY2024
)


def extract_year(text: str) -> int | None:
    """Return first plausible year in text, or None."""
    if not text:
        return None
    for pat in _YEAR_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        raw = m.group(1)
        try:
            year = int(raw)
        except ValueError:
            continue
        if year < 100:
            # FY24 shorthand
            year = 2000 + year if year <= 49 else 1900 + year
        if 2000 <= year <= 2039:
            return year
    return None


# ---------------------------------------------------------------------------
# Part-number extraction (mirrors query_router._extract_part_number patterns)
# ---------------------------------------------------------------------------

_PART_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bSEMS3D-\d+\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{2,4}-\d{3,5}\b"),
    re.compile(r"\b[A-Z]{2,4}\d{3,5}\b"),
    re.compile(r"\bTC\s?\d{2}-\d{2}-\d{2}-\d{3}\b", re.IGNORECASE),
)

# Filter out common false positives (acronyms, version strings, etc.)
_PART_FALSE_POSITIVES = {
    "CY24", "CY25", "CY26", "FY23", "FY24", "FY25", "FY26",
    "Q1-2024", "Q2-2024", "Q3-2024", "Q4-2024",
    "OY1", "OY2", "A001", "A002", "A014", "A027",
    "HTTP-200", "HTTP-404", "HTTP-500",
}

# Prefix-based false-positive filter: tokens that MATCH the part regex but are
# actually incident IDs, form numbers, CDRL codes, etc. — not physical parts.
_PART_FALSE_POSITIVE_PREFIXES: tuple[str, ...] = (
    "IGSI-",   # enterprise incident ticket IDs
    "IGSCC-",  # enterprise change-control IDs
    "AFTO",    # Air Force Technical Order form numbers
    "CDRL-",   # contract data requirements list codes
    "POA-",    # plan of action IDs
    "IAVM-",   # information assurance vulnerability memo
    "ACAS-",   # scan result IDs
    "TCNO-",   # time compliance network order
    "STIG-",   # STIG IDs (security, not part)
    "SCAP-",
)


def _is_part_false_positive(token: str) -> bool:
    if token in _PART_FALSE_POSITIVES:
        return True
    upper = token.upper()
    return any(upper.startswith(p) for p in _PART_FALSE_POSITIVE_PREFIXES)


def extract_part_numbers(text: str, max_parts: int = 5) -> list[str]:
    """Return deduped, normalized list of part numbers found in text."""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for pat in _PART_PATTERNS:
        for m in pat.finditer(text):
            token = m.group(0).upper().replace(" ", "")
            if _is_part_false_positive(token):
                continue
            if token not in seen:
                seen.add(token)
                found.append(token)
            if len(found) >= max_parts:
                return found
    return found


# ---------------------------------------------------------------------------
# Failure-signal detection (from chunk text)
# ---------------------------------------------------------------------------

_FAILURE_VERBS = re.compile(
    r"\b(failed|failure|faulted|faulty|replaced\s+due\s+to|malfunction|"
    r"anomaly|inoperable|inoperative|defective|broken|corrupted|"
    r"rma[\s-]?ed|returned\s+for\s+repair)\b",
    re.IGNORECASE,
)


def has_failure_signal(text: str) -> bool:
    return bool(_FAILURE_VERBS.search(text or ""))


# ---------------------------------------------------------------------------
# Path-derived extractor (fast, runs from retrieval_metadata.sqlite3)
# ---------------------------------------------------------------------------

def extract_path_derived_events(
    retrieval_metadata_db: str | Path,
    *,
    batch_size: int = 5000,
) -> Iterable[FailureEvent]:
    """
    Stream path-derived failure events from source_metadata.

    Emits one event per source_path when:
      - system can be detected from path OR
      - incident_id is present (treat as failure-adjacent)

    If the path (especially the filename) contains a part-number-shaped token,
    emit one event per detected part_number (richer substrate). Otherwise emit
    a single event with part_number=''.
    """
    conn = sqlite3.connect(str(retrieval_metadata_db))
    try:
        sql = """
            SELECT source_path, incident_id, site_token, source_doc_hash
            FROM source_metadata
        """
        cursor = conn.execute(sql)
        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                break
            for source_path, incident_id, site_token, source_doc_hash in batch:
                sp = str(source_path or "")
                sys_name = detect_system(sp)
                year = extract_year(sp)
                inc = str(incident_id or "")
                # Require a resolvable system. Incident-only docs without a
                # system tag can't be rate-queried per-system, and blank-system
                # rows pollute `DISTINCT system` outputs. (QA blocker 3.)
                if not sys_name:
                    continue
                # Extract part numbers from the full path (filename usually carries them).
                parts = extract_part_numbers(sp, max_parts=3)
                if parts:
                    for part in parts:
                        yield FailureEvent(
                            source_path=sp,
                            source_doc_hash=str(source_doc_hash or ""),
                            chunk_id="",
                            part_number=part,
                            system=sys_name,
                            site_token=str(site_token or ""),
                            event_year=year,
                            event_date="",
                            incident_id=inc,
                            failure_type="path_derived_with_part",
                            extraction_method="path_regex_v2",
                            confidence=0.65,
                        )
                else:
                    yield FailureEvent(
                        source_path=sp,
                        source_doc_hash=str(source_doc_hash or ""),
                        chunk_id="",
                        part_number="",
                        system=sys_name,
                        site_token=str(site_token or ""),
                        event_year=year,
                        event_date="",
                        incident_id=inc,
                        failure_type="path_derived_candidate" if inc else "path_derived_system",
                        extraction_method="path_regex_v1",
                        confidence=0.55 if inc else 0.40,
                    )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Chunk-derived extractor (richer, reads chunks)
# ---------------------------------------------------------------------------

def extract_chunk_events_from_iter(
    chunk_iter: Iterable[dict],
    *,
    require_failure_signal: bool = True,
) -> Iterable[FailureEvent]:
    """
    Stream chunk-derived failure events.

    Each input dict is expected to have at least:
      source_path, chunk_id, text  (or 'content'/'chunk_text')
      optionally: site_token, event_year
    """
    for ch in chunk_iter:
        text = str(ch.get("text") or ch.get("content") or ch.get("chunk_text") or "")
        if not text:
            continue
        if require_failure_signal and not has_failure_signal(text):
            continue
        sp = str(ch.get("source_path") or "")
        sys_name = detect_system(text) or detect_system(sp)
        year = extract_year(text) or extract_year(sp)
        site = str(ch.get("site_token") or "").lower()
        incident = str(ch.get("incident_id") or "")
        parts = extract_part_numbers(text)
        if not parts:
            # Emit a doc-level event without part_number (keeps failure-count honest)
            yield FailureEvent(
                source_path=sp,
                source_doc_hash=str(ch.get("source_doc_hash") or ""),
                chunk_id=str(ch.get("chunk_id") or ""),
                part_number="",
                system=sys_name,
                site_token=site,
                event_year=year,
                event_date="",
                incident_id=incident,
                failure_type="chunk_failure_noparts",
                extraction_method="chunk_regex_v1",
                confidence=0.60,
            )
            continue
        for part in parts:
            yield FailureEvent(
                source_path=sp,
                source_doc_hash=str(ch.get("source_doc_hash") or ""),
                chunk_id=str(ch.get("chunk_id") or ""),
                part_number=part,
                system=sys_name,
                site_token=site,
                event_year=year,
                event_date="",
                incident_id=incident,
                failure_type="chunk_failure_with_part",
                extraction_method="chunk_regex_v1",
                confidence=0.75,
            )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def populate_from_path_derived(
    metadata_db: str | Path,
    store: FailureEventsStore,
    *,
    batch_size: int = 5000,
) -> dict[str, int]:
    """
    Bulk-populate failure_events from source_metadata alone.
    Idempotent — uses INSERT OR IGNORE on the unique key.
    """
    events: list[FailureEvent] = []
    inserted_total = 0
    scanned = 0
    for event in extract_path_derived_events(metadata_db, batch_size=batch_size):
        events.append(event)
        scanned += 1
        if len(events) >= batch_size:
            store.insert_many(events)
            inserted_total += len(events)
            events = []
    if events:
        store.insert_many(events)
        inserted_total += len(events)
    return {
        "scanned_candidates": scanned,
        "inserted_attempted": inserted_total,
        "final_count": store.count(),
    }
