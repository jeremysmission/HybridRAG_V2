"""
Installed-base extractor — populates installed_base.db from source metadata + chunks.

The extractor mirrors the failure-events pattern:
  PASS 1 (path-derived):
    - find likely installed-base documents from source paths
    - inherit system / site / snapshot year from path and metadata
  PASS 2 (chunk-derived):
    - extract part_number + serial_number + quantity from chunk text
    - enrich with system / site / snapshot year from path/text

This is intentionally conservative: rows are only emitted when they help
deterministic denominator calculations.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from src.extraction.failure_event_extractor import (
    detect_system,
    extract_part_numbers,
    extract_year,
)
from src.store.installed_base_store import InstalledBaseRecord, InstalledBaseStore

logger = logging.getLogger(__name__)

_INSTALLED_BASE_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"site[\s_-]*inventory", re.IGNORECASE),
    re.compile(r"inventory[\s_-]*report", re.IGNORECASE),
    re.compile(r"spares?[\s_-]*inventory", re.IGNORECASE),
    re.compile(r"as[\s_-]*built", re.IGNORECASE),
    re.compile(r"installation[\s_-]*summary", re.IGNORECASE),
    re.compile(r"acceptance[\s_-]*test", re.IGNORECASE),
    re.compile(r"equipment[\s_-]*list", re.IGNORECASE),
    re.compile(r"\bbill[\s_-]*of[\s_-]*materials\b|\bbom\b|\bpbom\b", re.IGNORECASE),
)

_DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(20[0-3]\d)[-_/](0[1-9]|1[0-2])[-_/](0[1-9]|[12]\d|3[01])\b"),
)

_SERIAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bS(?:ERIAL)?[\/\s_-]*N(?:O|UMBER)?[:#\s_-]*([A-Z0-9-]{4,})\b", re.IGNORECASE),
    re.compile(r"\bSERIAL\s+NUMBER[:#\s_-]*([A-Z0-9-]{4,})\b", re.IGNORECASE),
)

_QUANTITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:qty|quantity)(?:\s+(?:installed|at\s+site|on\s+hand|spares?))?[:=\s]+(\d{1,5})\b", re.IGNORECASE),
    re.compile(r"\binstalled[:=\s]+(\d{1,5})\b", re.IGNORECASE),
    re.compile(r"\bon\s+hand[:=\s]+(\d{1,5})\b", re.IGNORECASE),
    re.compile(r"\bspares?[:=\s]+(\d{1,5})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,5})\s*(?:units?|ea)\b", re.IGNORECASE),
)


def is_installed_base_candidate_path(source_path: str) -> bool:
    if not source_path:
        return False
    return any(p.search(source_path) for p in _INSTALLED_BASE_PATH_PATTERNS)


def extract_snapshot_date(text: str) -> str:
    if not text:
        return ""
    for pat in _DATE_PATTERNS:
        match = pat.search(text)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


def extract_serial_numbers(text: str, max_serials: int = 3) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for pat in _SERIAL_PATTERNS:
        for match in pat.finditer(text):
            token = match.group(1).upper()
            if token not in seen:
                seen.add(token)
                found.append(token)
            if len(found) >= max_serials:
                return found
    return found


def extract_quantity_at_site(text: str) -> int | None:
    if not text:
        return None
    for pat in _QUANTITY_PATTERNS:
        match = pat.search(text)
        if not match:
            continue
        value = int(match.group(1))
        if 0 < value < 100000:
            return value
    return None


def extract_installed_base_records_from_text(
    text: str,
    *,
    source_path: str,
    chunk_id: str = "",
    source_doc_hash: str = "",
    system: str = "",
    site_token: str = "",
    snapshot_date: str = "",
    snapshot_year: int | None = None,
) -> list[InstalledBaseRecord]:
    """
    Extract part/serial/quantity rows from chunk text.

    Conservative approach:
      - work line-by-line
      - require a part number
      - require quantity OR serial (serial-only implies quantity 1)
    """
    records: list[InstalledBaseRecord] = []
    seen: set[tuple[str, str, str, int | None]] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = extract_part_numbers(line, max_parts=4)
        if not parts:
            continue
        qty = extract_quantity_at_site(line)
        serials = extract_serial_numbers(line, max_serials=1)
        if qty is None and serials:
            qty = 1
        if qty is None and not serials:
            continue
        for part in parts:
            serial = serials[0] if serials else ""
            key = (chunk_id, part, serial, qty)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                InstalledBaseRecord(
                    source_path=source_path,
                    source_doc_hash=source_doc_hash,
                    chunk_id=chunk_id,
                    part_number=part,
                    serial_number=serial,
                    system=system,
                    site_token=site_token,
                    install_date="",
                    snapshot_date=snapshot_date,
                    snapshot_year=snapshot_year,
                    quantity_at_site=qty,
                    extraction_method="chunk_installed_base_v1",
                    confidence=0.80 if qty is not None else 0.65,
                )
            )
    return records


def extract_path_derived_installed_base(
    retrieval_metadata_db: str | Path,
    *,
    batch_size: int = 5000,
) -> Iterable[InstalledBaseRecord]:
    """
    Stream path-derived installed-base candidates from source_metadata.

    These are document-level substrate hints. They rarely have part/qty, but
    they help establish system/site/year coverage and candidate scope.
    """
    conn = sqlite3.connect(str(retrieval_metadata_db))
    try:
        sql = """
            SELECT source_path, site_token, source_doc_hash
            FROM source_metadata
        """
        cursor = conn.execute(sql)
        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                break
            for source_path, site_token, source_doc_hash in batch:
                sp = str(source_path or "")
                if not is_installed_base_candidate_path(sp):
                    continue
                system = detect_system(sp)
                if not system:
                    continue
                snapshot_date = extract_snapshot_date(sp)
                snapshot_year = extract_year(snapshot_date) or extract_year(sp)
                yield InstalledBaseRecord(
                    source_path=sp,
                    source_doc_hash=str(source_doc_hash or ""),
                    chunk_id="",
                    part_number="",
                    serial_number="",
                    system=system,
                    site_token=str(site_token or ""),
                    install_date="",
                    snapshot_date=snapshot_date,
                    snapshot_year=snapshot_year,
                    quantity_at_site=None,
                    extraction_method="path_installed_base_v1",
                    confidence=0.45,
                )
    finally:
        conn.close()


def extract_chunk_installed_base_from_iter(chunk_iter: Iterable[dict]) -> Iterable[InstalledBaseRecord]:
    """Stream chunk-derived installed-base rows from candidate chunks."""
    for chunk in chunk_iter:
        source_path = str(chunk.get("source_path") or "")
        if not is_installed_base_candidate_path(source_path):
            continue
        text = str(chunk.get("text") or chunk.get("content") or chunk.get("chunk_text") or "")
        if not text:
            continue
        system = detect_system(text) or detect_system(source_path)
        if not system:
            continue
        site_token = str(chunk.get("site_token") or "").lower()
        snapshot_date = extract_snapshot_date(text) or extract_snapshot_date(source_path)
        snapshot_year = extract_year(snapshot_date) or extract_year(text) or extract_year(source_path)
        rows = extract_installed_base_records_from_text(
            text,
            source_path=source_path,
            chunk_id=str(chunk.get("chunk_id") or ""),
            source_doc_hash=str(chunk.get("source_doc_hash") or ""),
            system=system,
            site_token=site_token,
            snapshot_date=snapshot_date,
            snapshot_year=snapshot_year,
        )
        for row in rows:
            yield row


def populate_from_path_derived_installed_base(
    metadata_db: str | Path,
    store: InstalledBaseStore,
    *,
    batch_size: int = 5000,
) -> dict[str, int]:
    rows: list[InstalledBaseRecord] = []
    attempted = 0
    inserted = 0
    for row in extract_path_derived_installed_base(metadata_db, batch_size=batch_size):
        attempted += 1
        rows.append(row)
        if len(rows) >= 2000:
            inserted += store.insert_many(rows)
            rows = []
    if rows:
        inserted += store.insert_many(rows)
    return {
        "path_rows_attempted": attempted,
        "path_rows_inserted": inserted,
    }

