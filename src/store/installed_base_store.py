"""
Installed-base SQLite store — deterministic denominator substrate.

One row per extracted installed-base signal (inventory line, as-built line, or
serial-tracked deployment record). Used with failure_events to compute
failure-rate queries without letting the LLM invent denominators.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class InstalledBaseRecord:
    source_path: str
    source_doc_hash: str = ""
    chunk_id: str = ""
    part_number: str = ""
    serial_number: str = ""
    system: str = ""
    site_token: str = ""
    install_date: str = ""
    snapshot_date: str = ""
    snapshot_year: int | None = None
    quantity_at_site: int | None = None
    extraction_method: str = ""
    confidence: float = 0.0

    def to_row(self) -> tuple:
        return (
            self.source_path,
            self.source_doc_hash,
            self.chunk_id,
            self.part_number,
            self.serial_number,
            self.system,
            self.site_token,
            self.install_date,
            self.snapshot_date,
            int(self.snapshot_year) if self.snapshot_year is not None else None,
            int(self.quantity_at_site) if self.quantity_at_site is not None else None,
            self.extraction_method,
            float(self.confidence),
        )


def resolve_installed_base_db_path(data_dir_or_lance_path: str | Path) -> Path:
    """
    Co-locate installed_base.db with other substrate DBs under data/index/.

    Accepts the same shapes as resolve_failure_events_db_path.
    """
    p = Path(data_dir_or_lance_path)
    if p.name.lower() in {"lancedb", "lance_db", "lance"}:
        p = p.parent
    if p.name.lower() == "data" and not (p / "installed_base.sqlite3").exists():
        p = p / "index"
    if p.name.lower() != "index":
        p = p / "index"
    p.mkdir(parents=True, exist_ok=True)
    return p / "installed_base.sqlite3"


class InstalledBaseStore:
    """SQLite substrate for installed-base / inventory denominator rows."""

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
            CREATE TABLE IF NOT EXISTS installed_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                source_doc_hash TEXT NOT NULL DEFAULT '',
                chunk_id TEXT NOT NULL DEFAULT '',
                part_number TEXT NOT NULL DEFAULT '',
                serial_number TEXT NOT NULL DEFAULT '',
                system TEXT NOT NULL DEFAULT '',
                site_token TEXT NOT NULL DEFAULT '',
                install_date TEXT NOT NULL DEFAULT '',
                snapshot_date TEXT NOT NULL DEFAULT '',
                snapshot_year INTEGER,
                quantity_at_site INTEGER,
                extraction_method TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_ib_part ON installed_base(part_number);
            CREATE INDEX IF NOT EXISTS idx_ib_serial ON installed_base(serial_number);
            CREATE INDEX IF NOT EXISTS idx_ib_system ON installed_base(system);
            CREATE INDEX IF NOT EXISTS idx_ib_site ON installed_base(site_token);
            CREATE INDEX IF NOT EXISTS idx_ib_year ON installed_base(snapshot_year);
            CREATE INDEX IF NOT EXISTS idx_ib_sys_site_year
                ON installed_base(system, site_token, snapshot_year);
            CREATE INDEX IF NOT EXISTS idx_ib_source ON installed_base(source_path);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ib_serial_key
                ON installed_base(system, site_token, serial_number)
                WHERE serial_number != '';
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ib_part_snapshot
                ON installed_base(source_path, chunk_id, part_number, snapshot_date);
            """
        )
        self._conn.commit()

    def insert_many(self, rows: list[InstalledBaseRecord]) -> int:
        if not rows:
            return 0
        before = self._conn.total_changes
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO installed_base (
                source_path, source_doc_hash, chunk_id, part_number,
                serial_number, system, site_token, install_date, snapshot_date,
                snapshot_year, quantity_at_site, extraction_method, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [r.to_row() for r in rows],
        )
        self._conn.commit()
        return self._conn.total_changes - before

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM installed_base").fetchone()[0] or 0)

    def coverage_summary(self) -> dict[str, int]:
        c = self._conn
        total = int(c.execute("SELECT COUNT(*) FROM installed_base").fetchone()[0] or 0)
        return {
            "total_rows": total,
            "with_part_number": int(c.execute("SELECT COUNT(*) FROM installed_base WHERE part_number != ''").fetchone()[0] or 0),
            "with_serial_number": int(c.execute("SELECT COUNT(*) FROM installed_base WHERE serial_number != ''").fetchone()[0] or 0),
            "with_system": int(c.execute("SELECT COUNT(*) FROM installed_base WHERE system != ''").fetchone()[0] or 0),
            "with_site": int(c.execute("SELECT COUNT(*) FROM installed_base WHERE site_token != ''").fetchone()[0] or 0),
            "with_snapshot_year": int(c.execute("SELECT COUNT(*) FROM installed_base WHERE snapshot_year IS NOT NULL").fetchone()[0] or 0),
            "with_quantity": int(c.execute("SELECT COUNT(*) FROM installed_base WHERE quantity_at_site IS NOT NULL AND quantity_at_site > 0").fetchone()[0] or 0),
            "distinct_parts": int(c.execute("SELECT COUNT(DISTINCT part_number) FROM installed_base WHERE part_number != ''").fetchone()[0] or 0),
            "distinct_systems": int(c.execute("SELECT COUNT(DISTINCT system) FROM installed_base WHERE system != ''").fetchone()[0] or 0),
            "distinct_sites": int(c.execute("SELECT COUNT(DISTINCT site_token) FROM installed_base WHERE site_token != ''").fetchone()[0] or 0),
        }

    def latest_quantity_for_part(
        self,
        part_number: str,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year: int | None = None,
    ) -> int | None:
        """
        Return the latest known installed quantity for a part within scope.

        If no site is specified, sums the latest snapshot per site.
        If a serial-tracked record has no quantity, callers should have
        normalized it to quantity_at_site=1 before insertion.
        """
        clauses = [
            "part_number = ?",
            "quantity_at_site IS NOT NULL",
            "quantity_at_site > 0",
        ]
        params: list[object] = [part_number]
        if system:
            clauses.append("system = ?")
            params.append(system)
        if site_token:
            clauses.append("site_token = ?")
            params.append(site_token)
        if year is not None:
            clauses.append("(snapshot_year IS NULL OR snapshot_year <= ?)")
            params.append(int(year))
        sql = f"""
            SELECT system, site_token, quantity_at_site, snapshot_year, snapshot_date, id
            FROM installed_base
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(snapshot_year, 0) DESC,
                     COALESCE(snapshot_date, '') DESC,
                     id DESC
        """
        rows = self._conn.execute(sql, params).fetchall()
        if not rows:
            return None
        seen: set[tuple[str, str]] = set()
        total = 0
        for system_value, site_value, qty, _snapshot_year, _snapshot_date, _row_id in rows:
            key = (str(system_value or ""), str(site_value or ""))
            if key in seen:
                continue
            seen.add(key)
            total += int(qty or 0)
        return total if total > 0 else None

    def latest_total_quantity(
        self,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year: int | None = None,
    ) -> int | None:
        """Return the total installed quantity for the latest snapshot in scope.

        Dedupes by `(part_number, system, site_token)` and keeps the latest row at
        or before `year`. This is the denominator for aggregate site/system rate
        helpers, while `latest_quantity_for_part()` remains the denominator for
        top-N part-rate queries.
        """
        clauses = [
            "part_number != ''",
            "quantity_at_site IS NOT NULL",
            "quantity_at_site > 0",
        ]
        params: list[object] = []
        if system:
            clauses.append("system = ?")
            params.append(system)
        if site_token:
            clauses.append("site_token = ?")
            params.append(site_token)
        if year is not None:
            clauses.append("(snapshot_year IS NULL OR snapshot_year <= ?)")
            params.append(int(year))
        sql = f"""
            SELECT part_number, system, site_token, quantity_at_site, snapshot_year, snapshot_date, id
            FROM installed_base
            WHERE {' AND '.join(clauses)}
            ORDER BY part_number ASC,
                     system ASC,
                     site_token ASC,
                     COALESCE(snapshot_year, 0) DESC,
                     COALESCE(snapshot_date, '') DESC,
                     id DESC
        """
        rows = self._conn.execute(sql, params).fetchall()
        if not rows:
            return None
        seen: set[tuple[str, str, str]] = set()
        total = 0
        for part_number, system_value, site_value, qty, _snapshot_year, _snapshot_date, _row_id in rows:
            key = (
                str(part_number or ""),
                str(system_value or ""),
                str(site_value or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            total += int(qty or 0)
        return total if total > 0 else None

    def distinct_part_numbers(
        self,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year: int | None = None,
    ) -> set[str]:
        """Return the distinct installed-base part numbers in scope."""
        clauses = ["part_number != ''"]
        params: list[object] = []
        if system:
            clauses.append("system = ?")
            params.append(system)
        if site_token:
            clauses.append("site_token = ?")
            params.append(site_token)
        if year is not None:
            clauses.append("(snapshot_year IS NULL OR snapshot_year <= ?)")
            params.append(int(year))
        sql = f"""
            SELECT DISTINCT part_number
            FROM installed_base
            WHERE {' AND '.join(clauses)}
        """
        rows = self._conn.execute(sql, params).fetchall()
        return {str(r[0]) for r in rows if r and r[0]}

    def first_install_dates_per_site(
        self,
        *,
        system: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return earliest known install/snapshot date for each site."""
        clauses = ["site_token != ''"]
        params: list[object] = []
        if system:
            clauses.append("system = ?")
            params.append(system)
        sql = f"""
            SELECT
                site_token,
                MIN(COALESCE(NULLIF(install_date, ''), NULLIF(snapshot_date, ''))) AS first_install_date,
                MIN(COALESCE(snapshot_year, CAST(substr(COALESCE(NULLIF(install_date, ''), NULLIF(snapshot_date, '')), 1, 4) AS INTEGER))) AS first_year,
                COUNT(DISTINCT part_number) AS distinct_parts
            FROM installed_base
            WHERE {' AND '.join(clauses)}
            GROUP BY site_token
            ORDER BY first_install_date ASC, site_token ASC
            LIMIT ?
        """
        rows = self._conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
        out: list[dict] = []
        for site, first_install_date, first_year, distinct_parts in rows:
            derived_year = None
            if first_install_date:
                try:
                    derived_year = int(str(first_install_date)[:4])
                except ValueError:
                    derived_year = None
            out.append(
                {
                    "site_token": str(site or ""),
                    "first_install_date": first_install_date or "",
                    "first_year": derived_year if derived_year is not None else (int(first_year) if first_year is not None else None),
                    "distinct_parts": int(distinct_parts or 0),
                }
            )
        return out

    def installation_churn_per_site(
        self,
        *,
        system: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return snapshot-change summary per site.

        Churn is defined as the number of distinct inventory snapshots minus one.
        This is intentionally snapshot-based rather than inference-heavy.
        """
        clauses = ["site_token != ''"]
        params: list[object] = []
        if system:
            clauses.append("system = ?")
            params.append(system)
        sql = f"""
            SELECT
                site_token,
                COUNT(DISTINCT COALESCE(NULLIF(snapshot_date, ''), printf('%04d-01-01', snapshot_year))) AS snapshot_count,
                MIN(COALESCE(NULLIF(snapshot_date, ''), NULLIF(install_date, ''))) AS first_snapshot_date,
                MAX(COALESCE(NULLIF(snapshot_date, ''), NULLIF(install_date, ''))) AS last_snapshot_date,
                COUNT(DISTINCT part_number) AS distinct_parts
            FROM installed_base
            WHERE {' AND '.join(clauses)}
            GROUP BY site_token
            ORDER BY snapshot_count DESC, site_token ASC
            LIMIT ?
        """
        rows = self._conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
        out: list[dict] = []
        for site, snapshot_count, first_snapshot_date, last_snapshot_date, distinct_parts in rows:
            count = int(snapshot_count or 0)
            out.append(
                {
                    "site_token": str(site or ""),
                    "snapshot_count": count,
                    "churn_points": max(0, count - 1),
                    "first_snapshot_date": first_snapshot_date or "",
                    "last_snapshot_date": last_snapshot_date or "",
                    "distinct_parts": int(distinct_parts or 0),
                }
            )
        return out

    def age_distribution_per_part(
        self,
        *,
        system: str | None = None,
        site_token: str | None = None,
        as_of_year: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return part age summary derived from earliest known install year."""
        as_of_year = int(as_of_year or 2026)
        clauses = ["part_number != ''"]
        params: list[object] = []
        if system:
            clauses.append("system = ?")
            params.append(system)
        if site_token:
            clauses.append("site_token = ?")
            params.append(site_token)
        sql = f"""
            SELECT
                part_number,
                MIN(
                    COALESCE(
                        CAST(substr(NULLIF(install_date, ''), 1, 4) AS INTEGER),
                        CAST(substr(NULLIF(snapshot_date, ''), 1, 4) AS INTEGER),
                        snapshot_year
                    )
                ) AS first_year,
                COUNT(DISTINCT site_token) AS site_count,
                COUNT(*) AS row_count
            FROM installed_base
            WHERE {' AND '.join(clauses)}
            GROUP BY part_number
            HAVING first_year IS NOT NULL
            ORDER BY first_year ASC, part_number ASC
            LIMIT ?
        """
        rows = self._conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
        out: list[dict] = []
        for part_number, first_year, site_count, row_count in rows:
            first_year_int = int(first_year)
            out.append(
                {
                    "part_number": str(part_number or ""),
                    "first_year": first_year_int,
                    "age_years": max(0, as_of_year - first_year_int),
                    "site_count": int(site_count or 0),
                    "row_count": int(row_count or 0),
                }
            )
        return out

    def source_paths_for_site(
        self,
        site_token: str,
        *,
        system: str | None = None,
        limit: int = 3,
    ) -> list[str]:
        clauses = ["site_token = ?", "source_path != ''"]
        params: list[object] = [site_token]
        if system:
            clauses.append("system = ?")
            params.append(system)
        sql = f"""
            SELECT DISTINCT source_path
            FROM installed_base
            WHERE {' AND '.join(clauses)}
            ORDER BY source_path ASC
            LIMIT ?
        """
        rows = self._conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    def source_paths_for_part(
        self,
        part_number: str,
        *,
        system: str | None = None,
        site_token: str | None = None,
        limit: int = 3,
    ) -> list[str]:
        clauses = ["part_number = ?", "source_path != ''"]
        params: list[object] = [part_number]
        if system:
            clauses.append("system = ?")
            params.append(system)
        if site_token:
            clauses.append("site_token = ?")
            params.append(site_token)
        sql = f"""
            SELECT DISTINCT source_path
            FROM installed_base
            WHERE {' AND '.join(clauses)}
            ORDER BY source_path ASC
            LIMIT ?
        """
        rows = self._conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    def close(self) -> None:
        self._conn.close()
