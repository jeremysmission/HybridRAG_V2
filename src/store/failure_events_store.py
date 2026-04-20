"""
Failure-events SQLite store — deterministic substrate for aggregation queries.

One row per extracted failure event (or failure-adjacent document). Used by
src/query/aggregation_executor.py to answer grouped-aggregation questions
without LLM counting. Populated by scripts/populate_failure_events.py
from (a) source_metadata.incident_id rows and (b) chunk-text extraction.

Schema is intentionally narrow — part_number, system, site, year are the
four deterministic filter axes. Everything else is provenance.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FailureEvent:
    source_path: str
    source_doc_hash: str = ""
    chunk_id: str = ""
    part_number: str = ""
    system: str = ""
    site_token: str = ""
    event_year: int | None = None
    event_date: str = ""
    incident_id: str = ""
    failure_type: str = ""
    extraction_method: str = ""
    confidence: float = 0.0

    def to_row(self) -> tuple:
        return (
            self.source_path,
            self.source_doc_hash,
            self.chunk_id,
            self.part_number,
            self.system,
            self.site_token,
            int(self.event_year) if self.event_year is not None else None,
            self.event_date,
            self.incident_id,
            self.failure_type,
            self.extraction_method,
            float(self.confidence),
        )


def resolve_failure_events_db_path(data_dir_or_lance_path: str | Path) -> Path:
    """
    Co-locate failure_events.db with other substrate DBs under data/index/.

    Accepts any of:
      - data/index/lancedb  (the LanceDB directory itself)
      - data/index          (the parent substrate dir)
      - data                (the top-level data dir)
    """
    p = Path(data_dir_or_lance_path)
    # If caller passed the lancedb dir itself, step up to its parent (data/index).
    if p.name.lower() in {"lancedb", "lance_db", "lance"}:
        p = p.parent
    # If caller passed the top-level data dir, drop into data/index.
    if p.name.lower() == "data" and not (p / "failure_events.sqlite3").exists():
        p = p / "index"
    # If caller passed a path that doesn't end in "index", co-locate with other
    # substrate DBs by appending "index".
    if p.name.lower() != "index":
        p = p / "index"
    p.mkdir(parents=True, exist_ok=True)
    return p / "failure_events.sqlite3"


class FailureEventsStore:
    """SQLite store keyed by (source_path, chunk_id, part_number) triple."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=memory")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS failure_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                source_doc_hash TEXT NOT NULL DEFAULT '',
                chunk_id TEXT NOT NULL DEFAULT '',
                part_number TEXT NOT NULL DEFAULT '',
                system TEXT NOT NULL DEFAULT '',
                site_token TEXT NOT NULL DEFAULT '',
                event_year INTEGER,
                event_date TEXT NOT NULL DEFAULT '',
                incident_id TEXT NOT NULL DEFAULT '',
                failure_type TEXT NOT NULL DEFAULT '',
                extraction_method TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_fe_part ON failure_events(part_number);
            CREATE INDEX IF NOT EXISTS idx_fe_system ON failure_events(system);
            CREATE INDEX IF NOT EXISTS idx_fe_site ON failure_events(site_token);
            CREATE INDEX IF NOT EXISTS idx_fe_year ON failure_events(event_year);
            CREATE INDEX IF NOT EXISTS idx_fe_sys_year ON failure_events(system, event_year);
            CREATE INDEX IF NOT EXISTS idx_fe_sys_site_year ON failure_events(system, site_token, event_year);
            CREATE INDEX IF NOT EXISTS idx_fe_source ON failure_events(source_path);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_fe_key
                ON failure_events(source_path, chunk_id, part_number);
            """
        )
        self._conn.commit()

    def insert_many(self, events: list[FailureEvent]) -> int:
        if not events:
            return 0
        rows = [e.to_row() for e in events]
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO failure_events (
                source_path, source_doc_hash, chunk_id, part_number, system,
                site_token, event_year, event_date, incident_id, failure_type,
                extraction_method, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return self._conn.total_changes

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM failure_events").fetchone()[0] or 0)

    def distinct_systems(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT system FROM failure_events WHERE system != '' ORDER BY system"
        ).fetchall()
        return [r[0] for r in rows]

    def coverage_summary(self) -> dict[str, int]:
        c = self._conn
        total = int(c.execute("SELECT COUNT(*) FROM failure_events").fetchone()[0] or 0)
        return {
            "total_events": total,
            "with_part_number": int(c.execute("SELECT COUNT(*) FROM failure_events WHERE part_number != ''").fetchone()[0] or 0),
            "with_system":     int(c.execute("SELECT COUNT(*) FROM failure_events WHERE system != ''").fetchone()[0] or 0),
            "with_site":       int(c.execute("SELECT COUNT(*) FROM failure_events WHERE site_token != ''").fetchone()[0] or 0),
            "with_year":       int(c.execute("SELECT COUNT(*) FROM failure_events WHERE event_year IS NOT NULL").fetchone()[0] or 0),
            "distinct_parts":  int(c.execute("SELECT COUNT(DISTINCT part_number) FROM failure_events WHERE part_number != ''").fetchone()[0] or 0),
            "distinct_systems": int(c.execute("SELECT COUNT(DISTINCT system) FROM failure_events WHERE system != ''").fetchone()[0] or 0),
            "distinct_sites":  int(c.execute("SELECT COUNT(DISTINCT site_token) FROM failure_events WHERE site_token != ''").fetchone()[0] or 0),
        }

    def top_n_parts(
        self,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """GROUP BY part_number + COUNT + ORDER BY count DESC + LIMIT N."""
        clauses = ["part_number != ''"]
        params: list[object] = []
        if system:
            clauses.append("system = ?")
            params.append(system)
        if site_token:
            clauses.append("site_token = ?")
            params.append(site_token)
        if year_from is not None:
            clauses.append("event_year >= ?")
            params.append(int(year_from))
        if year_to is not None:
            clauses.append("event_year <= ?")
            params.append(int(year_to))
        where = " AND ".join(clauses)
        sql = f"""
            SELECT
                part_number,
                COUNT(*) AS failure_count,
                COUNT(DISTINCT source_path) AS distinct_docs,
                MIN(event_year) AS first_year,
                MAX(event_year) AS last_year
            FROM failure_events
            WHERE {where}
            GROUP BY part_number
            ORDER BY failure_count DESC, part_number ASC
            LIMIT ?
        """
        params.append(max(1, int(limit)))
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "part_number": r[0],
                "failure_count": int(r[1] or 0),
                "distinct_docs": int(r[2] or 0),
                "first_year": r[3],
                "last_year": r[4],
            }
            for r in rows
        ]

    def top_n_parts_per_year(
        self,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        limit_per_year: int = 5,
    ) -> dict[int, list[dict]]:
        """Per-year top-N ranking. Runs a separate query per year in range."""
        if year_from is None or year_to is None:
            row = self._conn.execute(
                "SELECT MIN(event_year), MAX(event_year) FROM failure_events WHERE event_year IS NOT NULL"
            ).fetchone()
            if not row or row[0] is None:
                return {}
            year_from = year_from if year_from is not None else int(row[0])
            year_to = year_to if year_to is not None else int(row[1])
        out: dict[int, list[dict]] = {}
        for y in range(int(year_from), int(year_to) + 1):
            rows = self.top_n_parts(
                system=system, site_token=site_token,
                year_from=y, year_to=y, limit=limit_per_year,
            )
            if rows:
                out[y] = rows
        return out

    def evidence_for_part(
        self,
        part_number: str,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Return up to N evidence rows for a given aggregated part_number."""
        clauses = ["part_number = ?"]
        params: list[object] = [part_number]
        if system:
            clauses.append("system = ?")
            params.append(system)
        if site_token:
            clauses.append("site_token = ?")
            params.append(site_token)
        if year_from is not None:
            clauses.append("event_year >= ?")
            params.append(int(year_from))
        if year_to is not None:
            clauses.append("event_year <= ?")
            params.append(int(year_to))
        where = " AND ".join(clauses)
        sql = f"""
            SELECT source_path, incident_id, event_year, site_token, extraction_method, confidence
            FROM failure_events
            WHERE {where}
            ORDER BY confidence DESC, event_year DESC
            LIMIT ?
        """
        params.append(max(1, int(limit)))
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "source_path": r[0],
                "incident_id": r[1],
                "event_year": r[2],
                "site_token": r[3],
                "extraction_method": r[4],
                "confidence": float(r[5] or 0.0),
            }
            for r in rows
        ]

    def monthly_failure_history(
        self,
        part_number: str,
        *,
        system: str | None = None,
        site_token: str | None = None,
        trailing_months: int = 24,
    ) -> dict[str, object]:
        """
        Return a zero-filled monthly failure history for the requested part.

        Uses event_date month precision when present and falls back to January
        of event_year when only year precision exists.
        """
        clauses = ["part_number = ?"]
        params: list[object] = [part_number]
        if system:
            clauses.append("system = ?")
            params.append(system)
        if site_token:
            clauses.append("site_token = ?")
            params.append(site_token)
        where = " AND ".join(clauses)
        rows = self._conn.execute(
            f"""
            SELECT event_date, event_year
            FROM failure_events
            WHERE {where}
            """,
            params,
        ).fetchall()

        bucket_counts: dict[date, int] = {}
        for raw_event_date, raw_event_year in rows:
            month_start = _month_start_from_event(raw_event_date, raw_event_year)
            if month_start is None:
                continue
            bucket_counts[month_start] = bucket_counts.get(month_start, 0) + 1

        if not bucket_counts:
            return {
                "month_labels": [],
                "month_counts": [],
                "span_months": 0,
                "window_months": 0,
                "total_failures": 0,
                "first_month": "",
                "last_month": "",
            }

        first_month = min(bucket_counts)
        last_month = max(bucket_counts)
        span_months = _month_diff(first_month, last_month) + 1
        window_months = min(max(1, int(trailing_months)), span_months)
        window_start = _add_months(last_month, -(window_months - 1))
        months = [_add_months(window_start, offset) for offset in range(window_months)]
        month_counts = [int(bucket_counts.get(month_start, 0)) for month_start in months]

        return {
            "month_labels": [m.strftime("%Y-%m") for m in months],
            "month_counts": month_counts,
            "span_months": span_months,
            "window_months": window_months,
            "total_failures": int(sum(month_counts)),
            "first_month": first_month.strftime("%Y-%m"),
            "last_month": last_month.strftime("%Y-%m"),
        }

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            logger.debug("Failed closing failure events store", exc_info=True)


def _month_start_from_event(raw_event_date: object, raw_event_year: object) -> date | None:
    text = str(raw_event_date or "").strip()
    if len(text) >= 7 and text[4] == "-" and text[7:8] in {"", "-"}:
        try:
            return date(int(text[0:4]), int(text[5:7]), 1)
        except ValueError:
            pass
    try:
        year = int(raw_event_year) if raw_event_year is not None else None
    except (TypeError, ValueError):
        year = None
    if year is not None and 1900 <= year <= 2100:
        return date(year, 1, 1)
    return None


def _month_diff(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _add_months(value: date, delta: int) -> date:
    year = value.year + (value.month - 1 + delta) // 12
    month = (value.month - 1 + delta) % 12 + 1
    return date(year, month, 1)
