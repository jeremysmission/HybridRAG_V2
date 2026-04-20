"""SQLite substrate for ASV/RTS MSR completion tracking."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.extraction.msr_extractor import MSRVisitRecord


def resolve_msr_db_path(data_dir_or_lance_path: str | Path) -> Path:
    p = Path(data_dir_or_lance_path)
    if p.name.lower() in {"lancedb", "lance_db", "lance"}:
        p = p.parent
    if p.name.lower() == "data" and not (p / "msr_substrate.sqlite3").exists():
        p = p / "index"
    if p.name.lower() != "index":
        p = p / "index"
    p.mkdir(parents=True, exist_ok=True)
    return p / "msr_substrate.sqlite3"


class MSRSubstrateStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def close(self) -> None:
        self._conn.close()

    def _create_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS msr_asv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visit_key TEXT NOT NULL,
                site_token TEXT NOT NULL DEFAULT '',
                system TEXT NOT NULL DEFAULT '',
                visit_year INTEGER,
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                source_path TEXT NOT NULL DEFAULT '',
                extraction_method TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS msr_rts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visit_key TEXT NOT NULL,
                site_token TEXT NOT NULL DEFAULT '',
                system TEXT NOT NULL DEFAULT '',
                visit_year INTEGER,
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                source_path TEXT NOT NULL DEFAULT '',
                extraction_method TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_msr_asv_visit ON msr_asv(visit_key);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_msr_rts_visit ON msr_rts(visit_key);
            CREATE INDEX IF NOT EXISTS idx_msr_asv_site_year ON msr_asv(site_token, visit_year);
            CREATE INDEX IF NOT EXISTS idx_msr_rts_site_year ON msr_rts(site_token, visit_year);
            """
        )
        self._conn.commit()

    def insert_many(self, records: list[MSRVisitRecord]) -> dict[str, int]:
        inserted = {"msr_asv": 0, "msr_rts": 0}
        if not records:
            return inserted
        for table_name, visit_type in (("msr_asv", "ASV"), ("msr_rts", "RTS")):
            table_rows = [
                (
                    r.visit_key,
                    r.site_token,
                    r.system,
                    int(r.visit_year) if r.visit_year is not None else None,
                    r.start_date,
                    r.end_date,
                    r.source_path,
                    r.extraction_method,
                    float(r.confidence),
                )
                for r in records
                if r.visit_type == visit_type
            ]
            before = self._conn.total_changes
            self._conn.executemany(
                f"""
                INSERT OR IGNORE INTO {table_name} (
                    visit_key, site_token, system, visit_year, start_date,
                    end_date, source_path, extraction_method, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                table_rows,
            )
            inserted[table_name] = self._conn.total_changes - before
        self._conn.commit()
        return inserted

    def coverage_summary(self) -> dict[str, int]:
        row = self._conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM msr_asv),
                (SELECT COUNT(*) FROM msr_rts),
                (SELECT COUNT(DISTINCT site_token) FROM (
                    SELECT site_token FROM msr_asv
                    UNION ALL
                    SELECT site_token FROM msr_rts
                ) WHERE site_token != ''),
                (SELECT COUNT(DISTINCT system) FROM (
                    SELECT system FROM msr_asv
                    UNION ALL
                    SELECT system FROM msr_rts
                ) WHERE system != '')
            """
        ).fetchone()
        asv_count, rts_count, distinct_sites, distinct_systems = row or (0, 0, 0, 0)
        return {
            "msr_asv": int(asv_count or 0),
            "msr_rts": int(rts_count or 0),
            "distinct_sites": int(distinct_sites or 0),
            "distinct_systems": int(distinct_systems or 0),
        }

    def completions_per_site_per_year(
        self,
        visit_type: str,
        *,
        system: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[dict]:
        table = "msr_asv" if str(visit_type).upper() == "ASV" else "msr_rts"
        clauses = ["site_token != ''", "visit_year IS NOT NULL"]
        params: list[object] = []
        if system:
            clauses.append("system = ?")
            params.append(system)
        if year_from is not None:
            clauses.append("visit_year >= ?")
            params.append(int(year_from))
        if year_to is not None:
            clauses.append("visit_year <= ?")
            params.append(int(year_to))
        sql = f"""
            SELECT
                site_token,
                visit_year,
                COUNT(*) AS completion_count,
                COUNT(DISTINCT system) AS distinct_systems
            FROM {table}
            WHERE {' AND '.join(clauses)}
            GROUP BY site_token, visit_year
            ORDER BY visit_year ASC, completion_count DESC, site_token ASC
        """
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "site_token": str(site_token or ""),
                "visit_year": int(visit_year),
                "completion_count": int(completion_count or 0),
                "distinct_systems": int(distinct_systems or 0),
            }
            for site_token, visit_year, completion_count, distinct_systems in rows
        ]

    def source_paths_for_site_year(
        self,
        visit_type: str,
        *,
        site_token: str,
        visit_year: int,
        system: str | None = None,
        limit: int = 3,
    ) -> list[str]:
        table = "msr_asv" if str(visit_type).upper() == "ASV" else "msr_rts"
        clauses = [
            "site_token = ?",
            "visit_year = ?",
            "source_path != ''",
        ]
        params: list[object] = [site_token, int(visit_year)]
        if system:
            clauses.append("system = ?")
            params.append(system)
        sql = f"""
            SELECT DISTINCT source_path
            FROM {table}
            WHERE {' AND '.join(clauses)}
            ORDER BY source_path ASC
            LIMIT ?
        """
        rows = self._conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]
