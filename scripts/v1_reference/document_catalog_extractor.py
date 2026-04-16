"""Document-level structured metadata sidecar built from indexed chunks."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .source_quality import ensure_source_quality_schema
from .structured_report_utils import (
    clamp_top_n,
    extract_question_filters,
    extract_report_metadata,
    parse_file_metadata,
)


@dataclass
class DocumentCatalogQueryResult:
    """Structured response for document-level SQL answers or summary scopes."""

    route: str
    handler: str
    answer: str = ""
    matched_source_paths: list[str] | None = None
    matched_documents: list[dict[str, Any]] | None = None
    sources: list[dict[str, Any]] | None = None
    filters: dict[str, Any] | None = None


def ensure_document_catalog_schema(conn: sqlite3.Connection) -> None:
    """Create the additive document_catalog table and indexes."""
    ensure_source_quality_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_catalog (
            source_path              TEXT PRIMARY KEY,
            first_chunk_id           TEXT NOT NULL DEFAULT '',
            file_ext                 TEXT NOT NULL DEFAULT '',
            file_size_bytes          INTEGER,
            file_mtime_ns            INTEGER,
            source_quality_tier      TEXT NOT NULL DEFAULT '',
            document_family          TEXT NOT NULL DEFAULT '',
            report_family            TEXT NOT NULL DEFAULT '',
            report_subtype           TEXT NOT NULL DEFAULT '',
            report_id                TEXT NOT NULL DEFAULT '',
            report_date_raw          TEXT NOT NULL DEFAULT '',
            report_date_iso          TEXT NOT NULL DEFAULT '',
            report_year              INTEGER,
            site_raw                 TEXT NOT NULL DEFAULT '',
            site_canonical           TEXT NOT NULL DEFAULT '',
            country_canonical        TEXT NOT NULL DEFAULT '',
            system_name              TEXT NOT NULL DEFAULT '',
            follow_on_actions_raw    TEXT NOT NULL DEFAULT '',
            corrective_action_raw    TEXT NOT NULL DEFAULT '',
            repair_summary_raw       TEXT NOT NULL DEFAULT '',
            poc_name                 TEXT NOT NULL DEFAULT '',
            poc_title                TEXT NOT NULL DEFAULT '',
            poc_org                  TEXT NOT NULL DEFAULT '',
            poc_phone                TEXT NOT NULL DEFAULT '',
            poc_email                TEXT NOT NULL DEFAULT '',
            poc_address_raw          TEXT NOT NULL DEFAULT '',
            poc_block_raw            TEXT NOT NULL DEFAULT '',
            created_at               TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_catalog_year "
        "ON document_catalog(report_year)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_catalog_site "
        "ON document_catalog(site_canonical)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_catalog_country "
        "ON document_catalog(country_canonical)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_catalog_subtype "
        "ON document_catalog(report_subtype)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_catalog_report_id "
        "ON document_catalog(report_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_catalog_family "
        "ON document_catalog(report_family)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_source_chunk "
        "ON chunks(source_path, chunk_index)"
    )
    conn.commit()


def rebuild_document_catalog(db_path: str) -> int:
    """Rebuild document_catalog from the first indexed chunk of each source."""
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=30000")
    ensure_document_catalog_schema(conn)

    select_sql = """
        SELECT c.source_path, c.chunk_id, c.text, c.created_at, sq.retrieval_tier
        FROM chunks c
        LEFT JOIN source_quality sq ON sq.source_path = c.source_path
        WHERE c.chunk_pk IN (
            SELECT MIN(chunk_pk)
            FROM chunks
            GROUP BY source_path
        )
        ORDER BY c.source_path
    """

    insert_sql = """
        INSERT INTO document_catalog (
            source_path, first_chunk_id, file_ext, file_size_bytes, file_mtime_ns,
            source_quality_tier, document_family, report_family, report_subtype,
            report_id, report_date_raw, report_date_iso, report_year, site_raw,
            site_canonical, country_canonical, system_name, follow_on_actions_raw,
            corrective_action_raw, repair_summary_raw, poc_name, poc_title, poc_org,
            poc_phone, poc_email, poc_address_raw, poc_block_raw, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    conn.execute("DELETE FROM document_catalog")
    cursor = conn.execute(select_sql)
    batch: list[tuple[Any, ...]] = []
    inserted = 0

    for source_path, chunk_id, text, created_at, source_quality_tier in cursor:
        file_ext, file_size_bytes, file_mtime_ns = parse_file_metadata(source_path)
        metadata = extract_report_metadata(
            text or "",
            str(source_path or ""),
            created_at=str(created_at or ""),
            fallback_mtime_ns=file_mtime_ns,
        )
        batch.append(
            (
                str(source_path or ""),
                str(chunk_id or ""),
                file_ext,
                file_size_bytes,
                file_mtime_ns,
                str(source_quality_tier or ""),
                str(metadata.get("document_family", "") or ""),
                str(metadata.get("report_family", "") or ""),
                str(metadata.get("report_subtype", "") or ""),
                str(metadata.get("report_id", "") or ""),
                str(metadata.get("report_date_raw", "") or ""),
                str(metadata.get("report_date_iso", "") or ""),
                metadata.get("report_year"),
                str(metadata.get("site_raw", "") or ""),
                str(metadata.get("site_canonical", "") or ""),
                str(metadata.get("country_canonical", "") or ""),
                str(metadata.get("system_name", "") or ""),
                str(metadata.get("follow_on_actions_raw", "") or ""),
                str(metadata.get("corrective_action_raw", "") or ""),
                str(metadata.get("repair_summary_raw", "") or ""),
                str(metadata.get("poc_name", "") or ""),
                str(metadata.get("poc_title", "") or ""),
                str(metadata.get("poc_org", "") or ""),
                str(metadata.get("poc_phone", "") or ""),
                str(metadata.get("poc_email", "") or ""),
                str(metadata.get("poc_address_raw", "") or ""),
                str(metadata.get("poc_block_raw", "") or ""),
                str(metadata.get("created_at", "") or ""),
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
    return inserted


def can_answer_document_catalog(question: str) -> bool:
    """Return True for document-level list/filter/summary questions."""
    filters = extract_question_filters(question)
    return bool(
        filters["wants_summary"]
        or filters["asks_sites"]
        or filters["asks_poc"]
        or filters["asks_follow_on"]
        or filters["asks_repair"]
        or filters["year_start"] is not None
        or filters["country_terms"]
        or filters["site_terms"]
        or filters["report_subtypes"]
    )


def match_document_catalog_filters(
    question: str,
    *,
    known_sites: list[str] | None = None,
    known_countries: list[str] | None = None,
) -> dict[str, Any]:
    """Parse reusable SQL filters for document-level routes."""
    return extract_question_filters(
        question,
        known_sites=known_sites or (),
        known_countries=known_countries or (),
    )


def _load_known_terms(conn: sqlite3.Connection) -> tuple[list[str], list[str]]:
    """Load the data needed for the document catalog extractor workflow."""
    site_rows = conn.execute(
        "SELECT DISTINCT site_canonical FROM document_catalog "
        "WHERE site_canonical != '' AND report_family = 'MSR'"
    ).fetchall()
    country_rows = conn.execute(
        "SELECT DISTINCT country_canonical FROM document_catalog "
        "WHERE country_canonical != '' AND report_family = 'MSR'"
    ).fetchall()
    return (
        [str(row[0]) for row in site_rows],
        [str(row[0]) for row in country_rows],
    )


def _build_document_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
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

    site_values = list(filters.get("site_terms") or [])
    country_values = list(filters.get("country_terms") or [])
    location_clauses: list[str] = []
    if site_values:
        placeholders = ", ".join("?" for _ in site_values)
        location_clauses.append(f"site_canonical IN ({placeholders})")
        params.extend(site_values)
    if country_values:
        placeholders = ", ".join("?" for _ in country_values)
        location_clauses.append(f"country_canonical IN ({placeholders})")
        params.extend(country_values)
    if location_clauses:
        clauses.append("(" + " OR ".join(location_clauses) + ")")

    if "monitoring system" in str(filters.get("normalized_question", "")):
        clauses.append("LOWER(system_name) LIKE '%monitoring system%'")

    return " AND ".join(clauses), params


def _format_document_sources(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Turn internal values into human-readable text for the operator."""
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        source_path = str(row["source_path"] or "")
        if not source_path or source_path in seen:
            continue
        seen.add(source_path)
        sources.append(
            {
                "path": source_path,
                "chunks": 1,
                "avg_relevance": 1.0,
            }
        )
    return sources


def _ensure_document_catalog_populated(
    db_path: str,
    conn: sqlite3.Connection,
) -> sqlite3.Connection:
    """Backfill document_catalog from chunks on first structured query."""
    has_rows = conn.execute(
        "SELECT 1 FROM document_catalog LIMIT 1"
    ).fetchone()
    if has_rows:
        return conn

    has_chunks = conn.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
    if not has_chunks:
        return conn

    conn.close()
    rebuild_document_catalog(db_path)

    refreshed = sqlite3.connect(db_path, timeout=30)
    refreshed.row_factory = sqlite3.Row
    refreshed.execute("PRAGMA busy_timeout=10000")
    ensure_document_catalog_schema(refreshed)
    return refreshed


def _query_site_list(conn: sqlite3.Connection, where_sql: str, params: list[Any]) -> DocumentCatalogQueryResult | None:
    """Run a focused lookup against the underlying stores and return the matching data."""
    rows = conn.execute(
        f"""
        SELECT site_canonical, country_canonical, COUNT(*) AS doc_count
        FROM document_catalog
        WHERE {where_sql} AND site_canonical != ''
        GROUP BY site_canonical, country_canonical
        ORDER BY site_canonical
        """
    , params).fetchall()
    if not rows:
        return None
    lines = [f"Sites in the indexed report catalog ({len(rows)}):"]
    for row in rows:
        country = f" [{row['country_canonical']}]" if row["country_canonical"] else ""
        lines.append(
            f"- {row['site_canonical']}{country} ({row['doc_count']} report(s))"
        )
    return DocumentCatalogQueryResult(
        route="sql_answer",
        handler="document_catalog",
        answer="\n".join(lines),
        sources=[],
    )


def _query_follow_on_actions(
    conn: sqlite3.Connection,
    where_sql: str,
    params: list[Any],
) -> DocumentCatalogQueryResult | None:
    """Run a focused lookup against the underlying stores and return the matching data."""
    rows = conn.execute(
        f"""
        SELECT report_id, report_date_iso, site_canonical, country_canonical,
               report_subtype, follow_on_actions_raw, source_path
        FROM document_catalog
        WHERE {where_sql} AND follow_on_actions_raw != ''
        ORDER BY report_date_iso DESC, site_canonical ASC, report_id ASC
        """
    , params).fetchall()
    if not rows:
        return None
    lines = [f"Follow-on actions ({len(rows)} report(s)):"]
    for row in rows:
        lines.append(
            f"- {row['report_date_iso']} | {row['site_canonical']} | "
            f"{row['report_subtype'] or 'unknown'} | {row['report_id'] or Path(row['source_path']).name}: "
            f"{row['follow_on_actions_raw']}"
        )
    return DocumentCatalogQueryResult(
        route="sql_answer",
        handler="document_catalog",
        answer="\n".join(lines),
        sources=_format_document_sources(rows),
    )


def _query_point_of_contact(
    conn: sqlite3.Connection,
    where_sql: str,
    params: list[Any],
) -> DocumentCatalogQueryResult | None:
    """Run a focused lookup against the underlying stores and return the matching data."""
    rows = conn.execute(
        f"""
        SELECT report_id, report_date_iso, site_canonical, country_canonical,
               poc_name, poc_title, poc_org, poc_phone, poc_email, source_path
        FROM document_catalog
        WHERE {where_sql}
          AND (
            poc_name != '' OR poc_title != '' OR poc_org != ''
            OR poc_phone != '' OR poc_email != ''
          )
        ORDER BY report_date_iso DESC, site_canonical ASC, report_id ASC
        """
    , params).fetchall()
    if not rows:
        return None
    lines = [f"Point-of-contact details ({len(rows)} report(s)):"]
    for row in rows:
        identity = " / ".join(
            item
            for item in (row["poc_name"], row["poc_title"], row["poc_org"])
            if item
        )
        contact = " / ".join(
            item for item in (row["poc_phone"], row["poc_email"]) if item
        )
        lines.append(
            f"- {row['report_date_iso']} | {row['site_canonical']} | "
            f"{row['report_id'] or Path(row['source_path']).name}: "
            f"{identity or 'POC not named'}"
            + (f" | {contact}" if contact else "")
        )
    return DocumentCatalogQueryResult(
        route="sql_answer",
        handler="document_catalog",
        answer="\n".join(lines),
        sources=_format_document_sources(rows),
    )


def _query_filtered_summary_scope(
    conn: sqlite3.Connection,
    where_sql: str,
    params: list[Any],
    filters: dict[str, Any],
) -> DocumentCatalogQueryResult | None:
    """Run a focused lookup against the underlying stores and return the matching data."""
    limit_docs = clamp_top_n(filters.get("top_n"), default=24, maximum=60)
    rows = conn.execute(
        f"""
        SELECT source_path, report_id, report_date_iso, site_canonical,
               country_canonical, report_subtype, system_name
        FROM document_catalog
        WHERE {where_sql}
        ORDER BY report_date_iso DESC, site_canonical ASC, report_id ASC
        LIMIT ?
        """
    , [*params, limit_docs]).fetchall()
    if not rows:
        return None
    matched_paths = [str(row["source_path"]) for row in rows]
    matched_documents = [
        {
            "source_path": str(row["source_path"]),
            "report_id": str(row["report_id"] or ""),
            "report_date_iso": str(row["report_date_iso"] or ""),
            "site_canonical": str(row["site_canonical"] or ""),
            "country_canonical": str(row["country_canonical"] or ""),
            "report_subtype": str(row["report_subtype"] or ""),
            "system_name": str(row["system_name"] or ""),
        }
        for row in rows
    ]
    return DocumentCatalogQueryResult(
        route="filtered_summary",
        handler="document_catalog",
        matched_source_paths=matched_paths,
        matched_documents=matched_documents,
        sources=_format_document_sources(rows),
        filters=filters,
    )


def query_document_catalog(db_path: str, question: str) -> dict[str, Any] | None:
    """Answer document-level questions or return a filtered summary scope."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    ensure_document_catalog_schema(conn)
    conn = _ensure_document_catalog_populated(db_path, conn)

    try:
        known_sites, known_countries = _load_known_terms(conn)
        filters = match_document_catalog_filters(
            question,
            known_sites=known_sites,
            known_countries=known_countries,
        )
        where_sql, params = _build_document_where(filters)

        if filters["wants_summary"]:
            result = _query_filtered_summary_scope(conn, where_sql, params, filters)
            return result.__dict__ if result else None

        if filters["asks_follow_on"]:
            result = _query_follow_on_actions(conn, where_sql, params)
            return result.__dict__ if result else None

        if filters["asks_poc"]:
            result = _query_point_of_contact(conn, where_sql, params)
            return result.__dict__ if result else None

        if filters["asks_repair"]:
            result = _query_filtered_summary_scope(conn, where_sql, params, filters)
            return result.__dict__ if result else None

        if filters["asks_sites"] and (filters["wants_list"] or filters["wants_count"] or filters["wants_ranking"]):
            result = _query_site_list(conn, where_sql, params)
            return result.__dict__ if result else None

        return None
    finally:
        conn.close()
