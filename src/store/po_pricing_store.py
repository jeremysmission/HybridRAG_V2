"""
PO-pricing SQLite store for deterministic procurement-cost aggregation.

This substrate is intentionally narrow:
  - one row per extracted PO line item or path-derived price signal
  - append-only idempotent inserts
  - parameterized helper queries for cost / spend / lead-time questions
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_nullable_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    return float(text)


def _clean_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return int(float(text))


@dataclass
class POPricingEvent:
    po_number: str
    part_number: str | None = None
    unit_price: float | None = None
    qty: float | None = None
    po_date: str | None = None
    vendor: str = ""
    lead_time_days: int | None = None
    source_path: str = ""
    chunk_id: str = ""
    source_doc_hash: str = ""
    system: str = ""
    site_token: str = ""
    extraction_method: str = ""
    confidence: float = 0.0

    def to_row(self) -> tuple:
        return (
            _clean_text(self.po_number),
            _clean_nullable_text(self.part_number),
            _clean_float(self.unit_price),
            _clean_float(self.qty),
            _clean_nullable_text(self.po_date),
            _clean_text(self.vendor),
            _clean_int(self.lead_time_days),
            _clean_text(self.source_path),
            _clean_text(self.chunk_id),
            _clean_text(self.source_doc_hash),
            _clean_text(self.system).upper(),
            _clean_text(self.site_token).lower(),
            _clean_text(self.extraction_method),
            float(self.confidence or 0.0),
        )


def resolve_po_pricing_db_path(data_dir_or_lance_path: str | Path) -> Path:
    """
    Co-locate the PO-pricing store with the other SQLite sidecars under
    ``data/index/``.
    """
    p = Path(data_dir_or_lance_path)
    if p.name.lower() in {"lancedb", "lance_db", "lance"}:
        p = p.parent
    if p.name.lower() == "data" and not (p / "po_pricing.sqlite3").exists():
        p = p / "index"
    if p.name.lower() != "index":
        p = p / "index"
    p.mkdir(parents=True, exist_ok=True)
    return p / "po_pricing.sqlite3"


class POPricingStore:
    """SQLite store for deterministic PO pricing rows."""

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
            CREATE TABLE IF NOT EXISTS po_pricing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT NOT NULL,
                part_number TEXT,
                unit_price REAL,
                qty REAL,
                po_date TEXT,
                vendor TEXT,
                lead_time_days INTEGER,
                source_path TEXT NOT NULL,
                chunk_id TEXT NOT NULL DEFAULT '',
                source_doc_hash TEXT NOT NULL DEFAULT '',
                system TEXT NOT NULL DEFAULT '',
                site_token TEXT NOT NULL DEFAULT '',
                extraction_method TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_po_pricing_key
                ON po_pricing(source_path, chunk_id, IFNULL(part_number, ''), po_number);
            CREATE INDEX IF NOT EXISTS idx_po_pricing_po ON po_pricing(po_number);
            CREATE INDEX IF NOT EXISTS idx_po_pricing_part ON po_pricing(part_number);
            CREATE INDEX IF NOT EXISTS idx_po_pricing_date ON po_pricing(po_date);
            CREATE INDEX IF NOT EXISTS idx_po_pricing_vendor ON po_pricing(vendor);
            CREATE INDEX IF NOT EXISTS idx_po_pricing_system ON po_pricing(system);
            CREATE INDEX IF NOT EXISTS idx_po_pricing_site ON po_pricing(site_token);
            """
        )
        self._conn.commit()

    def insert_many(self, events: list[POPricingEvent]) -> int:
        if not events:
            return 0
        rows = [event.to_row() for event in events if _clean_text(event.po_number)]
        if not rows:
            return 0
        before = self._conn.total_changes
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO po_pricing (
                po_number,
                part_number,
                unit_price,
                qty,
                po_date,
                vendor,
                lead_time_days,
                source_path,
                chunk_id,
                source_doc_hash,
                system,
                site_token,
                extraction_method,
                confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return self._conn.total_changes - before

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM po_pricing").fetchone()
        return int(row[0] or 0) if row else 0

    def coverage_summary(self) -> dict[str, int]:
        c = self._conn
        return {
            "total_rows": int(c.execute("SELECT COUNT(*) FROM po_pricing").fetchone()[0] or 0),
            "with_part_number": int(c.execute("SELECT COUNT(*) FROM po_pricing WHERE TRIM(COALESCE(part_number, '')) != ''").fetchone()[0] or 0),
            "with_unit_price": int(c.execute("SELECT COUNT(*) FROM po_pricing WHERE unit_price IS NOT NULL").fetchone()[0] or 0),
            "with_qty": int(c.execute("SELECT COUNT(*) FROM po_pricing WHERE qty IS NOT NULL").fetchone()[0] or 0),
            "with_po_date": int(c.execute("SELECT COUNT(*) FROM po_pricing WHERE TRIM(COALESCE(po_date, '')) != ''").fetchone()[0] or 0),
            "with_vendor": int(c.execute("SELECT COUNT(*) FROM po_pricing WHERE vendor != ''").fetchone()[0] or 0),
            "with_lead_time": int(c.execute("SELECT COUNT(*) FROM po_pricing WHERE lead_time_days IS NOT NULL").fetchone()[0] or 0),
            "distinct_parts": int(c.execute("SELECT COUNT(DISTINCT part_number) FROM po_pricing WHERE TRIM(COALESCE(part_number, '')) != ''").fetchone()[0] or 0),
            "distinct_po_numbers": int(c.execute("SELECT COUNT(DISTINCT po_number) FROM po_pricing").fetchone()[0] or 0),
            "distinct_systems": int(c.execute("SELECT COUNT(DISTINCT system) FROM po_pricing WHERE system != ''").fetchone()[0] or 0),
            "distinct_sites": int(c.execute("SELECT COUNT(DISTINCT site_token) FROM po_pricing WHERE site_token != ''").fetchone()[0] or 0),
        }

    def distinct_systems(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT system FROM po_pricing WHERE system != '' ORDER BY system"
        ).fetchall()
        return [str(row[0]) for row in rows]

    def distinct_sites(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT site_token FROM po_pricing WHERE site_token != '' ORDER BY site_token"
        ).fetchall()
        return [str(row[0]) for row in rows]

    def top_n_parts_by_cost(
        self,
        *,
        limit: int = 5,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        part_prefix: str | None = None,
    ) -> list[dict]:
        where, params = self._base_where(
            system=system,
            site_token=site_token,
            year_from=year_from,
            year_to=year_to,
            part_prefix=part_prefix,
        )
        rows = self._conn.execute(
            f"""
            SELECT
                part_number,
                COUNT(*) AS row_count,
                COALESCE(SUM(CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_qty,
                COALESCE(AVG(unit_price), 0.0) AS avg_unit_price,
                COALESCE(MAX(unit_price), 0.0) AS max_unit_price,
                COALESCE(SUM(COALESCE(unit_price, 0.0) * CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_cost
            FROM po_pricing
            WHERE {where}
              AND TRIM(COALESCE(part_number, '')) != ''
              AND unit_price IS NOT NULL
            GROUP BY part_number
            ORDER BY max_unit_price DESC, avg_unit_price DESC, part_number ASC
            LIMIT ?
            """,
            params + [max(1, int(limit))],
        ).fetchall()
        return [
            {
                "part_number": row[0],
                "row_count": int(row[1] or 0),
                "total_qty": float(row[2] or 0.0),
                "avg_unit_price": float(row[3] or 0.0),
                "max_unit_price": float(row[4] or 0.0),
                "total_cost": float(row[5] or 0.0),
            }
            for row in rows
        ]

    def top_n_parts_by_order_count(
        self,
        *,
        limit: int = 5,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        part_prefix: str | None = None,
    ) -> list[dict]:
        where, params = self._base_where(
            system=system,
            site_token=site_token,
            year_from=year_from,
            year_to=year_to,
            part_prefix=part_prefix,
        )
        rows = self._conn.execute(
            f"""
            SELECT
                part_number,
                COUNT(*) AS row_count,
                COALESCE(SUM(CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_qty,
                COALESCE(AVG(unit_price), 0.0) AS avg_unit_price,
                COALESCE(MAX(unit_price), 0.0) AS max_unit_price,
                COALESCE(SUM(COALESCE(unit_price, 0.0) * CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_cost
            FROM po_pricing
            WHERE {where}
              AND TRIM(COALESCE(part_number, '')) != ''
            GROUP BY part_number
            ORDER BY row_count DESC, total_qty DESC, part_number ASC
            LIMIT ?
            """,
            params + [max(1, int(limit))],
        ).fetchall()
        return [
            {
                "part_number": row[0],
                "row_count": int(row[1] or 0),
                "total_qty": float(row[2] or 0.0),
                "avg_unit_price": float(row[3] or 0.0),
                "max_unit_price": float(row[4] or 0.0),
                "total_cost": float(row[5] or 0.0),
            }
            for row in rows
        ]

    def top_n_parts_by_volume(
        self,
        *,
        limit: int = 5,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        part_prefix: str | None = None,
    ) -> list[dict]:
        where, params = self._base_where(
            system=system,
            site_token=site_token,
            year_from=year_from,
            year_to=year_to,
            part_prefix=part_prefix,
        )
        rows = self._conn.execute(
            f"""
            SELECT
                part_number,
                COUNT(*) AS row_count,
                COALESCE(SUM(CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_qty,
                COALESCE(AVG(unit_price), 0.0) AS avg_unit_price,
                COALESCE(MAX(unit_price), 0.0) AS max_unit_price,
                COALESCE(SUM(COALESCE(unit_price, 0.0) * CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_cost
            FROM po_pricing
            WHERE {where}
              AND TRIM(COALESCE(part_number, '')) != ''
            GROUP BY part_number
            ORDER BY total_qty DESC, row_count DESC, part_number ASC
            LIMIT ?
            """,
            params + [max(1, int(limit))],
        ).fetchall()
        return [
            {
                "part_number": row[0],
                "row_count": int(row[1] or 0),
                "total_qty": float(row[2] or 0.0),
                "avg_unit_price": float(row[3] or 0.0),
                "max_unit_price": float(row[4] or 0.0),
                "total_cost": float(row[5] or 0.0),
            }
            for row in rows
        ]

    def total_spend_on_part(
        self,
        part_number: str,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> dict:
        where, params = self._base_where(
            system=system,
            site_token=site_token,
            year_from=year_from,
            year_to=year_to,
            part_number=part_number,
        )
        row = self._conn.execute(
            f"""
            SELECT
                part_number,
                COUNT(*) AS row_count,
                COALESCE(SUM(CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_qty,
                COALESCE(MIN(unit_price), 0.0) AS min_unit_price,
                COALESCE(AVG(unit_price), 0.0) AS avg_unit_price,
                COALESCE(MAX(unit_price), 0.0) AS max_unit_price,
                COALESCE(SUM(COALESCE(unit_price, 0.0) * CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_spend
            FROM po_pricing
            WHERE {where}
              AND TRIM(COALESCE(part_number, '')) != ''
              AND unit_price IS NOT NULL
            GROUP BY part_number
            """,
            params,
        ).fetchone()
        if not row:
            return {
                "part_number": _clean_text(part_number),
                "row_count": 0,
                "total_qty": 0.0,
                "min_unit_price": 0.0,
                "avg_unit_price": 0.0,
                "max_unit_price": 0.0,
                "total_spend": 0.0,
            }
        return {
            "part_number": row[0],
            "row_count": int(row[1] or 0),
            "total_qty": float(row[2] or 0.0),
            "min_unit_price": float(row[3] or 0.0),
            "avg_unit_price": float(row[4] or 0.0),
            "max_unit_price": float(row[5] or 0.0),
            "total_spend": float(row[6] or 0.0),
        }

    def price_summary_for_part(
        self,
        part_number: str,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> dict:
        where, params = self._base_where(
            system=system,
            site_token=site_token,
            year_from=year_from,
            year_to=year_to,
            part_number=part_number,
        )
        row = self._conn.execute(
            f"""
            SELECT
                part_number,
                COUNT(*) AS row_count,
                MAX(po_date) AS last_price_date,
                COALESCE(MIN(unit_price), 0.0) AS min_unit_price,
                COALESCE(AVG(unit_price), 0.0) AS avg_unit_price,
                COALESCE(MAX(unit_price), 0.0) AS max_unit_price
            FROM po_pricing
            WHERE {where}
              AND TRIM(COALESCE(part_number, '')) != ''
              AND unit_price IS NOT NULL
            GROUP BY part_number
            """,
            params,
        ).fetchone()
        if not row:
            return {
                "part_number": _clean_text(part_number),
                "row_count": 0,
                "last_price_date": None,
                "min_unit_price": 0.0,
                "avg_unit_price": 0.0,
                "max_unit_price": 0.0,
            }
        return {
            "part_number": row[0],
            "row_count": int(row[1] or 0),
            "last_price_date": row[2],
            "min_unit_price": float(row[3] or 0.0),
            "avg_unit_price": float(row[4] or 0.0),
            "max_unit_price": float(row[5] or 0.0),
        }

    def longest_lead_time_parts(
        self,
        *,
        limit: int = 5,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        part_prefix: str | None = None,
    ) -> list[dict]:
        where, params = self._base_where(
            system=system,
            site_token=site_token,
            year_from=year_from,
            year_to=year_to,
            part_prefix=part_prefix,
        )
        rows = self._conn.execute(
            f"""
            SELECT
                part_number,
                COUNT(*) AS row_count,
                MAX(lead_time_days) AS max_lead_time_days,
                AVG(lead_time_days) AS avg_lead_time_days,
                COALESCE(SUM(COALESCE(unit_price, 0.0) * CASE WHEN qty IS NULL OR qty <= 0 THEN 1.0 ELSE qty END), 0.0) AS total_cost
            FROM po_pricing
            WHERE {where}
              AND TRIM(COALESCE(part_number, '')) != ''
              AND lead_time_days IS NOT NULL
            GROUP BY part_number
            ORDER BY max_lead_time_days DESC, avg_lead_time_days DESC, part_number ASC
            LIMIT ?
            """,
            params + [max(1, int(limit))],
        ).fetchall()
        return [
            {
                "part_number": row[0],
                "row_count": int(row[1] or 0),
                "max_lead_time_days": int(row[2] or 0),
                "avg_lead_time_days": float(row[3] or 0.0),
                "total_cost": float(row[4] or 0.0),
            }
            for row in rows
        ]

    def evidence_for_part(
        self,
        part_number: str,
        *,
        limit: int = 3,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[dict]:
        where, params = self._base_where(
            system=system,
            site_token=site_token,
            year_from=year_from,
            year_to=year_to,
            part_number=part_number,
        )
        rows = self._conn.execute(
            f"""
            SELECT
                po_number,
                unit_price,
                qty,
                po_date,
                vendor,
                lead_time_days,
                source_path,
                chunk_id,
                system,
                site_token,
                extraction_method,
                confidence
            FROM po_pricing
            WHERE {where}
              AND TRIM(COALESCE(part_number, '')) != ''
            ORDER BY
                COALESCE(po_date, '') DESC,
                COALESCE(unit_price, 0.0) DESC,
                po_number ASC
            LIMIT ?
            """,
            params + [max(1, int(limit))],
        ).fetchall()
        return [
            {
                "po_number": row[0],
                "unit_price": float(row[1] or 0.0),
                "qty": float(row[2] or 0.0),
                "po_date": row[3] or "",
                "vendor": row[4] or "",
                "lead_time_days": row[5],
                "source_path": row[6] or "",
                "chunk_id": row[7] or "",
                "system": row[8] or "",
                "site_token": row[9] or "",
                "extraction_method": row[10] or "",
                "confidence": float(row[11] or 0.0),
            }
            for row in rows
        ]

    def backfill_lead_time_days_from_lifecycle(self, lifecycle_db_path: str | Path) -> int:
        lifecycle_path = Path(lifecycle_db_path)
        if not lifecycle_path.exists():
            return 0
        lifecycle_conn = sqlite3.connect(str(lifecycle_path))
        try:
            rows = lifecycle_conn.execute(
                """
                WITH order_rollup AS (
                    SELECT
                        po_number,
                        IFNULL(part_number, '') AS part_number,
                        MIN(order_date) AS order_date
                    FROM po_orders
                    WHERE IFNULL(order_date, '') != ''
                    GROUP BY po_number, IFNULL(part_number, '')
                ),
                receipt_rollup AS (
                    SELECT
                        po_number,
                        IFNULL(part_number, '') AS part_number,
                        MIN(receive_date) AS receive_date
                    FROM po_receipts
                    WHERE IFNULL(receive_date, '') != ''
                    GROUP BY po_number, IFNULL(part_number, '')
                )
                SELECT
                    o.po_number,
                    o.part_number,
                    CAST(julianday(r.receive_date) - julianday(o.order_date) AS INTEGER) AS lead_time_days
                FROM order_rollup o
                INNER JOIN receipt_rollup r
                    ON r.po_number = o.po_number
                   AND r.part_number = o.part_number
                WHERE julianday(r.receive_date) >= julianday(o.order_date)
                """
            ).fetchall()
        finally:
            lifecycle_conn.close()
        if not rows:
            return 0
        before = self._conn.total_changes
        self._conn.executemany(
            """
            UPDATE po_pricing
            SET lead_time_days = ?
            WHERE po_number = ?
              AND IFNULL(part_number, '') = ?
              AND (lead_time_days IS NULL OR lead_time_days < ?)
            """,
            [(int(row[2]), str(row[0] or ""), str(row[1] or ""), int(row[2])) for row in rows],
        )
        self._conn.commit()
        return self._conn.total_changes - before

    def backfill_po_dates_from_lifecycle(self, lifecycle_db_path: str | Path) -> int:
        lifecycle_path = Path(lifecycle_db_path)
        if not lifecycle_path.exists():
            return 0
        quoted = str(lifecycle_path).replace("'", "''")
        self._conn.execute(f"ATTACH DATABASE '{quoted}' AS po_life")
        try:
            before = self._conn.total_changes
            self._conn.execute(
                """
                WITH exact_part_dates AS (
                    SELECT
                        po_number,
                        IFNULL(part_number, '') AS part_key,
                        MIN(order_date) AS order_date
                    FROM po_life.po_orders
                    WHERE IFNULL(order_date, '') != ''
                    GROUP BY po_number, IFNULL(part_number, '')
                ),
                unique_po_dates AS (
                    SELECT
                        po_number,
                        MIN(order_date) AS order_date
                    FROM po_life.po_orders
                    WHERE IFNULL(order_date, '') != ''
                    GROUP BY po_number
                    HAVING COUNT(DISTINCT order_date) = 1
                )
                UPDATE po_pricing
                SET po_date = COALESCE(
                    (
                        SELECT ep.order_date
                        FROM exact_part_dates ep
                        WHERE ep.po_number = po_pricing.po_number
                          AND ep.part_key = IFNULL(po_pricing.part_number, '')
                        LIMIT 1
                    ),
                    (
                        SELECT up.order_date
                        FROM unique_po_dates up
                        WHERE up.po_number = po_pricing.po_number
                        LIMIT 1
                    )
                )
                WHERE IFNULL(po_date, '') = ''
                  AND (
                      EXISTS (
                          SELECT 1
                          FROM exact_part_dates ep
                          WHERE ep.po_number = po_pricing.po_number
                            AND ep.part_key = IFNULL(po_pricing.part_number, '')
                      )
                      OR EXISTS (
                          SELECT 1
                          FROM unique_po_dates up
                          WHERE up.po_number = po_pricing.po_number
                      )
                  )
                """
            )
            self._conn.commit()
            return self._conn.total_changes - before
        finally:
            self._conn.execute("DETACH DATABASE po_life")

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            logger.debug("Failed closing PO pricing store", exc_info=True)

    def _base_where(
        self,
        *,
        system: str | None = None,
        site_token: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        part_number: str | None = None,
        part_prefix: str | None = None,
    ) -> tuple[str, list[object]]:
        clauses = ["1=1"]
        params: list[object] = []
        if system:
            clauses.append("system = ?")
            params.append(_clean_text(system).upper())
        if site_token:
            clauses.append("site_token = ?")
            params.append(_clean_text(site_token).lower())
        if part_number:
            clauses.append("part_number = ?")
            params.append(_clean_text(part_number).upper())
        if part_prefix:
            clauses.append("part_number LIKE ?")
            params.append(f"{_clean_text(part_prefix).upper()}%")
        if year_from is not None:
            clauses.append("TRIM(COALESCE(po_date, '')) != ''")
            clauses.append("substr(po_date, 1, 4) >= ?")
            params.append(f"{int(year_from):04d}")
        if year_to is not None:
            clauses.append("TRIM(COALESCE(po_date, '')) != ''")
            clauses.append("substr(po_date, 1, 4) <= ?")
            params.append(f"{int(year_to):04d}")
        return " AND ".join(clauses), params
