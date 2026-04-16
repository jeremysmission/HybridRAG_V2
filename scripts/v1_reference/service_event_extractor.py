"""Event-level structured extraction for field reports and incidents."""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from .document_catalog_extractor import (
    ensure_document_catalog_schema,
    rebuild_document_catalog,
)
from .structured_report_utils import (
    clamp_top_n,
    extract_question_filters,
    infer_issue_category,
    normalize_action_type,
    normalize_whitespace,
)

logger = logging.getLogger(__name__)

_FIELD_VALUE_RE = re.compile(
    r"^\s*(?P<label>[A-Za-z][A-Za-z0-9 /#()_-]{1,40}):\s*(?P<value>.*)$",
    re.MULTILINE,
)
_NUMBERED_BLOCK_RE = re.compile(r"(?m)^\s*(?=\d+\.\s+)")
_SERIAL_RE = re.compile(r"\bSN[-: ]?[A-Za-z0-9-]+\b", re.IGNORECASE)
_QTY_RE = re.compile(r"\bqty(?:uantity)?\s*[:=]?\s*(\d+)\b", re.IGNORECASE)

_EVENT_LABELS = {
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


def ensure_service_events_schema(conn: sqlite3.Connection) -> None:
    """Create or upgrade the service_events table."""
    expected_columns = {
        "id",
        "report_family",
        "report_subtype",
        "report_id",
        "report_date_iso",
        "report_year",
        "site_canonical",
        "country_canonical",
        "system_name",
        "issue_category",
        "is_unscheduled",
        "is_power_event",
        "is_lightning_event",
        "part_number",
        "part_description",
        "component_name",
        "action_raw",
        "action_type",
        "qty",
        "failure_mode",
        "corrective_action_raw",
        "installed_part_number",
        "removed_part_number",
        "installed_serial",
        "removed_serial",
        "new_unit_serial",
        "failed_unit_serial",
        "downtime_raw",
        "source_path",
        "chunk_id",
        "chunk_index",
        "created_at",
    }
    existing_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(service_events)").fetchall()
    }
    if existing_columns and not expected_columns.issubset(existing_columns):
        conn.execute("DROP TABLE IF EXISTS service_events")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS service_events (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            report_family          TEXT NOT NULL DEFAULT '',
            report_subtype         TEXT NOT NULL DEFAULT '',
            report_id              TEXT NOT NULL DEFAULT '',
            report_date_iso        TEXT NOT NULL DEFAULT '',
            report_year            INTEGER,
            site_canonical         TEXT NOT NULL DEFAULT '',
            country_canonical      TEXT NOT NULL DEFAULT '',
            system_name            TEXT NOT NULL DEFAULT '',
            issue_category         TEXT NOT NULL DEFAULT '',
            is_unscheduled         INTEGER NOT NULL DEFAULT 0,
            is_power_event         INTEGER NOT NULL DEFAULT 0,
            is_lightning_event     INTEGER NOT NULL DEFAULT 0,
            part_number            TEXT NOT NULL DEFAULT '',
            part_description       TEXT NOT NULL DEFAULT '',
            component_name         TEXT NOT NULL DEFAULT '',
            action_raw             TEXT NOT NULL DEFAULT '',
            action_type            TEXT NOT NULL DEFAULT '',
            qty                    INTEGER,
            failure_mode           TEXT NOT NULL DEFAULT '',
            corrective_action_raw  TEXT NOT NULL DEFAULT '',
            installed_part_number  TEXT NOT NULL DEFAULT '',
            removed_part_number    TEXT NOT NULL DEFAULT '',
            installed_serial       TEXT NOT NULL DEFAULT '',
            removed_serial         TEXT NOT NULL DEFAULT '',
            new_unit_serial        TEXT NOT NULL DEFAULT '',
            failed_unit_serial     TEXT NOT NULL DEFAULT '',
            downtime_raw           TEXT NOT NULL DEFAULT '',
            source_path            TEXT NOT NULL DEFAULT '',
            chunk_id               TEXT NOT NULL DEFAULT '',
            chunk_index            INTEGER NOT NULL DEFAULT 0,
            created_at             TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_events_year "
        "ON service_events(report_year)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_events_site "
        "ON service_events(site_canonical)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_events_country "
        "ON service_events(country_canonical)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_events_subtype "
        "ON service_events(report_subtype)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_events_action "
        "ON service_events(action_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_events_part "
        "ON service_events(part_number)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_events_issue "
        "ON service_events(issue_category)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_service_events_source "
        "ON service_events(source_path)"
    )
    conn.commit()


def _extract_field_map(block_text: str) -> dict[str, str]:
    """Support the service event extractor workflow by handling the extract field map step."""
    fields: dict[str, str] = {}
    for match in _FIELD_VALUE_RE.finditer(str(block_text or "")):
        label = normalize_whitespace(match.group("label")).lower()
        target_field = _EVENT_LABELS.get(label)
        if not target_field:
            continue
        value = normalize_whitespace(match.group("value"))
        if value and not fields.get(target_field):
            fields[target_field] = value
    return fields


def _derive_heading(block_text: str) -> str:
    """Support the service event extractor workflow by handling the derive heading step."""
    first_line = next(
        (line.strip() for line in str(block_text or "").splitlines() if line.strip()),
        "",
    )
    match = re.match(r"^\d+\.\s*(.+)$", first_line)
    if match:
        return normalize_whitespace(match.group(1))
    return ""


def _iter_event_blocks(text: str) -> list[str]:
    """Split a report chunk into likely per-item event blocks."""
    raw = str(text or "")
    segments = [segment.strip() for segment in _NUMBERED_BLOCK_RE.split(raw) if segment.strip()]
    blocks = [
        segment
        for segment in segments
        if any(marker in segment for marker in ("Part#", "Component:", "Action:", "Failure Mode:", "Condition:", "New Unit:", "Failed Unit:", "Removed:"))
    ]
    if blocks:
        return blocks
    if any(marker in raw for marker in ("Part#", "Component:", "Failure Mode:", "Action:", "RESOLUTION:", "CORRECTIVE ACTION")):
        return [raw]
    return []


def _is_power_text(text: str) -> tuple[int, int]:
    """Support the service event extractor workflow by handling the is power text step."""
    normalized = normalize_whitespace(text).lower()
    is_lightning = int("lightning" in normalized)
    is_power = int(
        is_lightning
        or any(token in normalized for token in ("power surge", "power event", "brownout", "power outage", "voltage transient", "strike damage"))
    )
    return is_power, is_lightning


def _extract_serial(value: str) -> str:
    """Support the service event extractor workflow by handling the extract serial step."""
    match = _SERIAL_RE.search(str(value or ""))
    if match:
        return normalize_whitespace(match.group(0))
    return normalize_whitespace(value)


def _coerce_qty(value: str) -> int | None:
    """Support the service event extractor workflow by handling the coerce qty step."""
    match = _QTY_RE.search(str(value or ""))
    if match:
        return int(match.group(1))
    return 1 if normalize_whitespace(value) else None


def _normalize_event_row(
    block_text: str,
    metadata: dict[str, Any],
    *,
    source_path: str,
    chunk_id: str,
    chunk_index: int,
) -> dict[str, Any]:
    """Support the service event extractor workflow by handling the normalize event row step."""
    fields = _extract_field_map(block_text)
    heading = _derive_heading(block_text)
    part_number = normalize_whitespace(fields.get("part_number", ""))
    component_name = normalize_whitespace(fields.get("component_name", ""))
    part_description = normalize_whitespace(
        fields.get("part_description", "") or component_name or heading
    )
    action_raw = normalize_whitespace(fields.get("action_raw", ""))
    failure_mode = normalize_whitespace(fields.get("failure_mode", ""))
    new_unit_serial = _extract_serial(fields.get("new_unit_serial", ""))
    failed_unit_serial = _extract_serial(fields.get("failed_unit_serial", ""))
    installed_serial = _extract_serial(fields.get("installed_serial", ""))
    removed_serial = _extract_serial(fields.get("removed_serial", ""))
    installed_part_number = normalize_whitespace(fields.get("installed_part_number", ""))
    removed_part_number = normalize_whitespace(fields.get("removed_part_number", ""))
    if not installed_part_number and normalize_action_type(
        action_raw,
        new_unit_serial=new_unit_serial,
        removed_serial=removed_serial,
        failed_unit_serial=failed_unit_serial,
        installed_serial=installed_serial,
    ) in {"installed", "replaced"}:
        installed_part_number = part_number
    if not removed_part_number and normalize_action_type(
        action_raw,
        new_unit_serial=new_unit_serial,
        removed_serial=removed_serial,
        failed_unit_serial=failed_unit_serial,
        installed_serial=installed_serial,
    ) in {"removed", "replaced"}:
        removed_part_number = part_number

    action_type = normalize_action_type(
        action_raw,
        new_unit_serial=new_unit_serial,
        removed_serial=removed_serial,
        failed_unit_serial=failed_unit_serial,
        installed_serial=installed_serial,
    )
    is_power_event, is_lightning_event = _is_power_text(
        f"{metadata.get('corrective_action_raw', '')} {block_text}"
    )
    issue_category = infer_issue_category(
        text=block_text,
        failure_mode=failure_mode,
        call_description=str(metadata.get("corrective_action_raw", "") or ""),
    )
    return {
        "report_family": str(metadata.get("report_family", "") or ""),
        "report_subtype": str(metadata.get("report_subtype", "") or ""),
        "report_id": str(metadata.get("report_id", "") or ""),
        "report_date_iso": str(metadata.get("report_date_iso", "") or ""),
        "report_year": metadata.get("report_year"),
        "site_canonical": str(metadata.get("site_canonical", "") or ""),
        "country_canonical": str(metadata.get("country_canonical", "") or ""),
        "system_name": str(metadata.get("system_name", "") or ""),
        "issue_category": issue_category,
        "is_unscheduled": 1 if str(metadata.get("report_subtype", "")).upper() == "RTS" else 0,
        "is_power_event": is_power_event,
        "is_lightning_event": is_lightning_event,
        "part_number": part_number,
        "part_description": part_description,
        "component_name": component_name,
        "action_raw": action_raw,
        "action_type": action_type,
        "qty": _coerce_qty(fields.get("qty", part_number)),
        "failure_mode": failure_mode,
        "corrective_action_raw": str(metadata.get("corrective_action_raw", "") or ""),
        "installed_part_number": installed_part_number,
        "removed_part_number": removed_part_number,
        "installed_serial": installed_serial,
        "removed_serial": removed_serial,
        "new_unit_serial": new_unit_serial,
        "failed_unit_serial": failed_unit_serial,
        "downtime_raw": normalize_whitespace(fields.get("downtime_raw", "")),
        "source_path": source_path,
        "chunk_id": chunk_id,
        "chunk_index": int(chunk_index or 0),
        "created_at": str(metadata.get("created_at", "") or ""),
    }


def extract_events_from_chunk(
    text: str,
    source_path: str,
    chunk_id: str,
    *,
    chunk_index: int = 0,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Extract event rows from one chunk using deterministic parsing only."""
    report_metadata = dict(metadata or {})
    block_events = [
        _normalize_event_row(
            block,
            report_metadata,
            source_path=source_path,
            chunk_id=chunk_id,
            chunk_index=chunk_index,
        )
        for block in _iter_event_blocks(text)
    ]
    usable = [
        event
        for event in block_events
        if event["part_number"]
        or event["component_name"]
        or event["failure_mode"]
        or event["action_raw"]
        or event["new_unit_serial"]
        or event["failed_unit_serial"]
    ]
    if usable:
        return usable

    if int(chunk_index or 0) != 0:
        return []

    fallback_text = normalize_whitespace(text)
    if not fallback_text:
        return []

    is_power_event, is_lightning_event = _is_power_text(fallback_text)
    fallback_issue = infer_issue_category(
        text=fallback_text,
        failure_mode="",
        call_description=str(report_metadata.get("corrective_action_raw", "") or ""),
    )
    return [
        {
            "report_family": str(report_metadata.get("report_family", "") or ""),
            "report_subtype": str(report_metadata.get("report_subtype", "") or ""),
            "report_id": str(report_metadata.get("report_id", "") or ""),
            "report_date_iso": str(report_metadata.get("report_date_iso", "") or ""),
            "report_year": report_metadata.get("report_year"),
            "site_canonical": str(report_metadata.get("site_canonical", "") or ""),
            "country_canonical": str(report_metadata.get("country_canonical", "") or ""),
            "system_name": str(report_metadata.get("system_name", "") or ""),
            "issue_category": fallback_issue,
            "is_unscheduled": 1 if str(report_metadata.get("report_subtype", "")).upper() == "RTS" else 0,
            "is_power_event": is_power_event,
            "is_lightning_event": is_lightning_event,
            "part_number": "",
            "part_description": "",
            "component_name": "",
            "action_raw": str(report_metadata.get("corrective_action_raw", "") or ""),
            "action_type": normalize_action_type(str(report_metadata.get("corrective_action_raw", "") or "")),
            "qty": 1,
            "failure_mode": "",
            "corrective_action_raw": str(report_metadata.get("corrective_action_raw", "") or ""),
            "installed_part_number": "",
            "removed_part_number": "",
            "installed_serial": "",
            "removed_serial": "",
            "new_unit_serial": "",
            "failed_unit_serial": "",
            "downtime_raw": "",
            "source_path": source_path,
            "chunk_id": chunk_id,
            "chunk_index": int(chunk_index or 0),
            "created_at": str(report_metadata.get("created_at", "") or ""),
        }
    ]


def extract_all_service_events(db_path: str) -> int:
    """Rebuild service_events from existing chunks and document catalog rows."""
    conn = sqlite3.connect(db_path, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    ensure_document_catalog_schema(conn)
    ensure_service_events_schema(conn)
    conn.execute("DELETE FROM service_events")

    select_sql = """
        SELECT c.chunk_id, c.source_path, c.chunk_index, c.text,
               d.report_family, d.report_subtype, d.report_id, d.report_date_iso,
               d.report_year, d.site_canonical, d.country_canonical, d.system_name,
               d.corrective_action_raw, d.created_at
        FROM chunks c
        JOIN document_catalog d ON d.source_path = c.source_path
        WHERE d.report_family = 'MSR'
        ORDER BY c.source_path, c.chunk_index
    """
    insert_sql = """
        INSERT INTO service_events (
            report_family, report_subtype, report_id, report_date_iso, report_year,
            site_canonical, country_canonical, system_name, issue_category,
            is_unscheduled, is_power_event, is_lightning_event, part_number,
            part_description, component_name, action_raw, action_type, qty,
            failure_mode, corrective_action_raw, installed_part_number,
            removed_part_number, installed_serial, removed_serial, new_unit_serial,
            failed_unit_serial, downtime_raw, source_path, chunk_id, chunk_index, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    batch: list[tuple[Any, ...]] = []
    inserted = 0
    for row in conn.execute(select_sql):
        metadata = {
            "report_family": row["report_family"],
            "report_subtype": row["report_subtype"],
            "report_id": row["report_id"],
            "report_date_iso": row["report_date_iso"],
            "report_year": row["report_year"],
            "site_canonical": row["site_canonical"],
            "country_canonical": row["country_canonical"],
            "system_name": row["system_name"],
            "corrective_action_raw": row["corrective_action_raw"],
            "created_at": row["created_at"],
        }
        events = extract_events_from_chunk(
            row["text"] or "",
            str(row["source_path"] or ""),
            str(row["chunk_id"] or ""),
            chunk_index=int(row["chunk_index"] or 0),
            metadata=metadata,
        )
        for event in events:
            batch.append(
                (
                    event["report_family"],
                    event["report_subtype"],
                    event["report_id"],
                    event["report_date_iso"],
                    event["report_year"],
                    event["site_canonical"],
                    event["country_canonical"],
                    event["system_name"],
                    event["issue_category"],
                    event["is_unscheduled"],
                    event["is_power_event"],
                    event["is_lightning_event"],
                    event["part_number"],
                    event["part_description"],
                    event["component_name"],
                    event["action_raw"],
                    event["action_type"],
                    event["qty"],
                    event["failure_mode"],
                    event["corrective_action_raw"],
                    event["installed_part_number"],
                    event["removed_part_number"],
                    event["installed_serial"],
                    event["removed_serial"],
                    event["new_unit_serial"],
                    event["failed_unit_serial"],
                    event["downtime_raw"],
                    event["source_path"],
                    event["chunk_id"],
                    event["chunk_index"],
                    event["created_at"],
                )
            )
            if len(batch) >= 1000:
                conn.executemany(insert_sql, batch)
                inserted += len(batch)
                batch.clear()

    if batch:
        conn.executemany(insert_sql, batch)
        inserted += len(batch)

    conn.commit()
    conn.close()
    logger.info("rebuilt_service_events", count=inserted)
    return inserted


def _load_known_terms(conn: sqlite3.Connection) -> tuple[list[str], list[str]]:
    """Load the data needed for the service event extractor workflow."""
    site_rows = conn.execute(
        "SELECT DISTINCT site_canonical FROM service_events WHERE site_canonical != ''"
    ).fetchall()
    country_rows = conn.execute(
        "SELECT DISTINCT country_canonical FROM service_events WHERE country_canonical != ''"
    ).fetchall()
    return (
        [str(row[0]) for row in site_rows],
        [str(row[0]) for row in country_rows],
    )


def _build_event_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    """Assemble the structured object this workflow needs for its next step."""
    clauses = ["report_family = 'MSR'"]
    params: list[Any] = []

    year_start = filters.get("year_start")
    year_end = filters.get("year_end")
    years = list(filters.get("years") or [])
    if year_start is not None and year_end is not None:
        clauses.append("report_year BETWEEN ? AND ?")
        params.extend([int(year_start), int(year_end)])
    elif years:
        placeholders = ", ".join("?" for _ in years)
        clauses.append(f"report_year IN ({placeholders})")
        params.extend(int(year) for year in years)

    subtype_values = list(filters.get("report_subtypes") or [])
    if subtype_values:
        placeholders = ", ".join("?" for _ in subtype_values)
        clauses.append(f"report_subtype IN ({placeholders})")
        params.extend(subtype_values)

    location_values = list(filters.get("site_terms") or [])
    country_values = list(filters.get("country_terms") or [])
    location_clauses: list[str] = []
    if location_values:
        placeholders = ", ".join("?" for _ in location_values)
        location_clauses.append(f"site_canonical IN ({placeholders})")
        params.extend(location_values)
    if country_values:
        placeholders = ", ".join("?" for _ in country_values)
        location_clauses.append(f"country_canonical IN ({placeholders})")
        params.extend(country_values)
    if location_clauses:
        clauses.append("(" + " OR ".join(location_clauses) + ")")

    if "monitoring system" in str(filters.get("normalized_question", "")):
        clauses.append("LOWER(system_name) LIKE '%monitoring system%'")

    return " AND ".join(clauses), params


def can_answer_service_events(question: str) -> bool:
    """Return True when the question should route to service-events SQL."""
    filters = extract_question_filters(question)
    normalized = str(filters.get("normalized_question", ""))
    return bool(
        filters["asks_power"]
        or filters["asks_parts"]
        or filters["wants_ranking"]
        or "failed part" in normalized
        or "issues" in normalized
        or "lightning" in normalized
        or "unscheduled maintenance" in normalized
    )


def is_aggregation_query(question: str) -> bool:
    """Backward-compatible alias for event SQL routing."""
    return can_answer_service_events(question)


def _format_sources(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Turn internal values into human-readable text for the operator."""
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []
    for row in rows:
        source_path = str(row["source_path"] or "")
        if not source_path or source_path in seen:
            continue
        seen.add(source_path)
        sources.append({"path": source_path, "chunks": 1, "avg_relevance": 1.0})
    return sources


def _ensure_service_events_populated(
    db_path: str,
    conn: sqlite3.Connection,
) -> sqlite3.Connection:
    """Backfill service_events from chunks on first structured query."""
    has_rows = conn.execute(
        "SELECT 1 FROM service_events LIMIT 1"
    ).fetchone()
    if has_rows:
        return conn

    has_chunks = conn.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
    if not has_chunks:
        return conn

    conn.close()
    rebuild_document_catalog(db_path)
    extract_all_service_events(db_path)

    refreshed = sqlite3.connect(db_path, timeout=30)
    refreshed.row_factory = sqlite3.Row
    refreshed.execute("PRAGMA busy_timeout=10000")
    ensure_service_events_schema(refreshed)
    return refreshed


def _query_top_failed_parts(
    conn: sqlite3.Connection,
    where_sql: str,
    params: list[Any],
    top_n: int,
) -> dict[str, Any] | None:
    """Run a focused lookup against the underlying stores and return the matching data."""
    rows = conn.execute(
        f"""
        SELECT COALESCE(NULLIF(part_number, ''), NULLIF(installed_part_number, ''), NULLIF(removed_part_number, ''), NULLIF(component_name, '')) AS part_key,
               COUNT(*) AS event_count,
               COUNT(DISTINCT COALESCE(NULLIF(report_id, ''), source_path)) AS report_count
        FROM service_events
        WHERE {where_sql}
          AND COALESCE(NULLIF(part_number, ''), NULLIF(installed_part_number, ''), NULLIF(removed_part_number, ''), NULLIF(component_name, '')) IS NOT NULL
          AND (action_type IN ('replaced', 'removed', 'repaired') OR failure_mode != '' OR issue_category != 'unknown')
        GROUP BY part_key
        ORDER BY event_count DESC, part_key ASC
        LIMIT ?
        """
    , [*params, top_n]).fetchall()
    if not rows:
        return None
    lines = [f"Top {len(rows)} failed part/component keys:"]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"- {index}. {row['part_key']}: {row['event_count']} event row(s) across {row['report_count']} report(s)"
        )
    return {
        "route": "sql_answer",
        "handler": "service_events",
        "answer": "\n".join(lines),
        "sources": [],
    }


def _query_site_issue_ranking(
    conn: sqlite3.Connection,
    where_sql: str,
    params: list[Any],
    top_n: int,
) -> dict[str, Any] | None:
    """Run a focused lookup against the underlying stores and return the matching data."""
    rows = conn.execute(
        f"""
        SELECT site_canonical,
               COUNT(DISTINCT COALESCE(NULLIF(report_id, ''), source_path)) AS report_issue_count
        FROM service_events
        WHERE {where_sql} AND site_canonical != ''
        GROUP BY site_canonical
        ORDER BY report_issue_count DESC, site_canonical ASC
        LIMIT ?
        """
    , [*params, top_n]).fetchall()
    if not rows:
        return None
    lines = [f"Sites ranked by issue-bearing reports ({len(rows)} row(s)):"]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"- {index}. {row['site_canonical']}: {row['report_issue_count']} report(s)"
        )
    return {
        "route": "sql_answer",
        "handler": "service_events",
        "answer": "\n".join(lines),
        "sources": [],
    }


def _query_power_sites(
    conn: sqlite3.Connection,
    where_sql: str,
    params: list[Any],
) -> dict[str, Any] | None:
    """Run a focused lookup against the underlying stores and return the matching data."""
    rows = conn.execute(
        f"""
        SELECT site_canonical,
               COUNT(DISTINCT COALESCE(NULLIF(report_id, ''), source_path)) AS report_count,
               SUM(CASE WHEN is_lightning_event = 1 THEN 1 ELSE 0 END) AS lightning_rows,
               SUM(CASE WHEN is_power_event = 1 THEN 1 ELSE 0 END) AS power_rows
        FROM service_events
        WHERE {where_sql} AND (is_power_event = 1 OR is_lightning_event = 1)
        GROUP BY site_canonical
        ORDER BY report_count DESC, site_canonical ASC
        """
    , params).fetchall()
    if not rows:
        return None
    lines = [f"Sites with power-surge/lightning evidence ({len(rows)} site(s)):"]
    for row in rows:
        lines.append(
            f"- {row['site_canonical']}: {row['report_count']} report(s), "
            f"{row['power_rows']} power-event row(s), {row['lightning_rows']} lightning row(s)"
        )
    return {
        "route": "sql_answer",
        "handler": "service_events",
        "answer": "\n".join(lines),
        "sources": [],
    }


def _query_parts_by_action(
    conn: sqlite3.Connection,
    where_sql: str,
    params: list[Any],
    action_types: list[str],
) -> dict[str, Any] | None:
    """Run a focused lookup against the underlying stores and return the matching data."""
    placeholders = ", ".join("?" for _ in action_types)
    rows = conn.execute(
        f"""
        SELECT report_date_iso, site_canonical, report_subtype, report_id,
               COALESCE(NULLIF(part_number, ''), NULLIF(installed_part_number, ''), NULLIF(removed_part_number, ''), NULLIF(component_name, ''), NULLIF(part_description, '')) AS part_key,
               action_type, action_raw, source_path
        FROM service_events
        WHERE {where_sql}
          AND action_type IN ({placeholders})
          AND COALESCE(NULLIF(part_number, ''), NULLIF(installed_part_number, ''), NULLIF(removed_part_number, ''), NULLIF(component_name, ''), NULLIF(part_description, '')) IS NOT NULL
        ORDER BY report_date_iso DESC, site_canonical ASC, report_id ASC, part_key ASC
        """
    , [*params, *action_types]).fetchall()
    if not rows:
        return None
    lines = [f"Part actions ({len(rows)} row(s)):"]
    for row in rows:
        lines.append(
            f"- {row['report_date_iso']} | {row['site_canonical']} | {row['report_subtype'] or 'unknown'} | "
            f"{row['part_key']} | {row['action_type']} | {row['report_id'] or Path(row['source_path']).name}"
        )
    return {
        "route": "sql_answer",
        "handler": "service_events",
        "answer": "\n".join(lines),
        "sources": _format_sources(rows),
    }


def query_service_events_result(db_path: str, question: str) -> dict[str, Any] | None:
    """Answer event-level ranking/list/count questions via SQL."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    ensure_service_events_schema(conn)
    conn = _ensure_service_events_populated(db_path, conn)

    try:
        known_sites, known_countries = _load_known_terms(conn)
        filters = extract_question_filters(
            question,
            known_sites=known_sites,
            known_countries=known_countries,
        )
        where_sql, params = _build_event_where(filters)
        top_n = clamp_top_n(filters.get("top_n"), default=10)
        normalized = str(filters.get("normalized_question", ""))

        if filters["asks_power"]:
            return _query_power_sites(conn, where_sql, params)

        if filters["asks_parts"] and filters["action_types"]:
            return _query_parts_by_action(conn, where_sql, params, list(filters["action_types"]))

        if "failed part" in normalized or ("highest" in normalized and filters["asks_parts"]):
            return _query_top_failed_parts(conn, where_sql, params, top_n)

        if "which sites" in normalized or "most issues" in normalized or "unscheduled maintenance issues" in normalized:
            return _query_site_issue_ranking(conn, where_sql, params, top_n)

        if filters["wants_ranking"] and filters["asks_parts"]:
            return _query_top_failed_parts(conn, where_sql, params, top_n)

        return None
    finally:
        conn.close()


def query_service_events(db_path: str, question: str) -> str:
    """Backward-compatible wrapper returning a plain text answer."""
    result = query_service_events_result(db_path, question)
    if not result:
        return ""
    return str(result.get("answer", "") or "")
