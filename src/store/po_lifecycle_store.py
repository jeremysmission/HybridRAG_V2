"""
PO-lifecycle SQLite store for deterministic procurement aggregation.

This substrate keeps the first production slice narrow:
  - `po_orders` rows from purchase-order style sources
  - `po_receipts` rows from received / receipt / packing evidence
  - an `po_outstanding_as_of` view for deterministic as-of reporting

The store mirrors the rest of the aggregation substrates:
parameter-bound SQL only, small helper methods, and append-only idempotent
population keyed on the natural PO lifecycle identifiers.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_ORDER_GROUP_FIELDS = {
    "po_number": "po_number",
    "part_number": "part_number",
    "vendor": "vendor",
    "site": "site",
    "order_date": "order_date",
    "source_path": "source_path",
}

_RECEIPT_GROUP_FIELDS = {
    "po_number": "po_number",
    "part_number": "part_number",
    "receive_date": "receive_date",
    "source_path": "source_path",
}

_OUTSTANDING_GROUP_FIELDS = {
    "po_number": "po_number",
    "part_number": "part_number",
    "vendor": "vendor",
    "site": "site",
    "order_date": "order_date",
}


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_qty(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(value)


@dataclass
class POOrder:
    po_number: str
    part_number: str | None = None
    qty_ordered: float | None = None
    order_date: str | None = None
    vendor: str | None = None
    site: str | None = None
    source_path: str = ""
    source_doc_hash: str = ""

    def to_row(self) -> tuple:
        return (
            str(self.po_number or "").strip(),
            _clean_text(self.part_number),
            _clean_qty(self.qty_ordered),
            _clean_text(self.order_date),
            _clean_text(self.vendor),
            _clean_text(self.site),
            str(self.source_path or "").strip(),
            str(self.source_doc_hash or "").strip(),
        )


@dataclass
class POReceipt:
    po_number: str
    part_number: str | None = None
    qty_received: float | None = None
    receive_date: str | None = None
    source_path: str = ""
    source_doc_hash: str = ""

    def to_row(self) -> tuple:
        return (
            str(self.po_number or "").strip(),
            _clean_text(self.part_number),
            _clean_qty(self.qty_received),
            _clean_text(self.receive_date),
            str(self.source_path or "").strip(),
            str(self.source_doc_hash or "").strip(),
        )


def resolve_po_lifecycle_db_path(data_dir_or_lance_path: str | Path) -> Path:
    """
    Co-locate the PO-lifecycle store with the other substrate DBs under
    `data/index/`.

    Accepts any of:
      - `data/index/lancedb`
      - `data/index`
      - `data`
    """
    p = Path(data_dir_or_lance_path)
    if p.name.lower() in {"lancedb", "lance_db", "lance"}:
        p = p.parent
    if p.name.lower() == "data" and not (p / "po_lifecycle.sqlite3").exists():
        p = p / "index"
    if p.name.lower() != "index":
        p = p / "index"
    p.mkdir(parents=True, exist_ok=True)
    return p / "po_lifecycle.sqlite3"


class POLifecycleStore:
    """SQLite store for deterministic PO order / receipt substrate rows."""

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
            CREATE TABLE IF NOT EXISTS po_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT NOT NULL,
                part_number TEXT,
                qty_ordered REAL,
                order_date TEXT,
                vendor TEXT,
                site TEXT,
                source_path TEXT NOT NULL,
                source_doc_hash TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_po_orders_po ON po_orders(po_number);
            CREATE INDEX IF NOT EXISTS idx_po_orders_part ON po_orders(part_number);
            CREATE INDEX IF NOT EXISTS idx_po_orders_site ON po_orders(site);
            CREATE INDEX IF NOT EXISTS idx_po_orders_vendor ON po_orders(vendor);
            CREATE INDEX IF NOT EXISTS idx_po_orders_date ON po_orders(order_date);

            CREATE TABLE IF NOT EXISTS po_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT NOT NULL,
                part_number TEXT,
                qty_received REAL,
                receive_date TEXT,
                source_path TEXT NOT NULL,
                source_doc_hash TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_po_receipts_po ON po_receipts(po_number);
            CREATE INDEX IF NOT EXISTS idx_po_receipts_part ON po_receipts(part_number);
            CREATE INDEX IF NOT EXISTS idx_po_receipts_date ON po_receipts(receive_date);
            """
        )

        self._ensure_columns("po_orders", {"source_doc_hash": "TEXT NOT NULL DEFAULT ''"})
        self._ensure_columns("po_receipts", {"source_doc_hash": "TEXT NOT NULL DEFAULT ''"})

        # Replace the earlier path-heavy unique keys with the natural PO
        # lifecycle keys requested for the deterministic aggregation slice.
        self._conn.execute("DROP INDEX IF EXISTS uq_po_orders_key")
        self._conn.execute("DROP INDEX IF EXISTS uq_po_receipts_key")
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_po_orders_natural
            ON po_orders(
                po_number,
                IFNULL(part_number, ''),
                IFNULL(order_date, '')
            )
            """
        )
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_po_receipts_natural
            ON po_receipts(
                po_number,
                IFNULL(part_number, ''),
                IFNULL(receive_date, '')
            )
            """
        )
        self._recreate_outstanding_view()
        self._conn.commit()

    def _ensure_columns(self, table_name: str, required: dict[str, str]) -> None:
        existing = {
            str(row[1])
            for row in self._conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_sql in required.items():
            if column_name in existing:
                continue
            self._conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
            )

    def _recreate_outstanding_view(self) -> None:
        self._conn.execute("DROP VIEW IF EXISTS po_outstanding_as_of")
        self._conn.execute(
            """
            CREATE VIEW po_outstanding_as_of AS
            WITH order_rollup AS (
                SELECT
                    po_number,
                    part_number,
                    vendor,
                    site,
                    MIN(CASE WHEN IFNULL(order_date, '') != '' THEN order_date END) AS order_date,
                    SUM(COALESCE(qty_ordered, 0.0)) AS qty_ordered
                FROM po_orders
                GROUP BY po_number, part_number, vendor, site
            ),
            receipt_rollup AS (
                SELECT
                    po_number,
                    part_number,
                    MAX(CASE WHEN IFNULL(receive_date, '') != '' THEN receive_date END) AS receive_date,
                    SUM(COALESCE(qty_received, 0.0)) AS qty_received
                FROM po_receipts
                GROUP BY po_number, part_number
            )
            SELECT
                o.po_number,
                o.part_number,
                o.vendor,
                o.site,
                o.order_date,
                r.receive_date,
                o.qty_ordered AS qty_ordered,
                COALESCE(r.qty_received, 0.0) AS qty_received,
                CASE
                    WHEN COALESCE(o.qty_ordered, 0.0) - COALESCE(r.qty_received, 0.0) > 0.0
                    THEN COALESCE(o.qty_ordered, 0.0) - COALESCE(r.qty_received, 0.0)
                    ELSE 0.0
                END AS qty_outstanding
            FROM order_rollup o
            LEFT JOIN receipt_rollup r
              ON r.po_number = o.po_number
             AND IFNULL(r.part_number, '') = IFNULL(o.part_number, '')
            """
        )

    def insert_orders(self, orders: list[POOrder]) -> int:
        if not orders:
            return 0
        rows = [order.to_row() for order in orders if str(order.po_number or "").strip()]
        if not rows:
            return 0
        before = self._conn.total_changes
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO po_orders (
                po_number,
                part_number,
                qty_ordered,
                order_date,
                vendor,
                site,
                source_path,
                source_doc_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return self._conn.total_changes - before

    def insert_receipts(self, receipts: list[POReceipt]) -> int:
        if not receipts:
            return 0
        rows = [receipt.to_row() for receipt in receipts if str(receipt.po_number or "").strip()]
        if not rows:
            return 0
        before = self._conn.total_changes
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO po_receipts (
                po_number,
                part_number,
                qty_received,
                receive_date,
                source_path,
                source_doc_hash
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return self._conn.total_changes - before

    def count_orders(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM po_orders").fetchone()
        return int(row[0] or 0) if row else 0

    def count_receipts(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM po_receipts").fetchone()
        return int(row[0] or 0) if row else 0

    def count(self) -> int:
        return self.count_orders() + self.count_receipts()

    def coverage_summary(self) -> dict[str, int]:
        c = self._conn
        return {
            "orders": int(c.execute("SELECT COUNT(*) FROM po_orders").fetchone()[0] or 0),
            "receipts": int(c.execute("SELECT COUNT(*) FROM po_receipts").fetchone()[0] or 0),
            "orders_with_part_number": int(
                c.execute(
                    "SELECT COUNT(*) FROM po_orders WHERE IFNULL(part_number, '') != ''"
                ).fetchone()[0]
                or 0
            ),
            "receipts_with_part_number": int(
                c.execute(
                    "SELECT COUNT(*) FROM po_receipts WHERE IFNULL(part_number, '') != ''"
                ).fetchone()[0]
                or 0
            ),
            "orders_with_order_date": int(
                c.execute(
                    "SELECT COUNT(*) FROM po_orders WHERE IFNULL(order_date, '') != ''"
                ).fetchone()[0]
                or 0
            ),
            "receipts_with_receive_date": int(
                c.execute(
                    "SELECT COUNT(*) FROM po_receipts WHERE IFNULL(receive_date, '') != ''"
                ).fetchone()[0]
                or 0
            ),
            "distinct_order_pos": int(
                c.execute("SELECT COUNT(DISTINCT po_number) FROM po_orders").fetchone()[0] or 0
            ),
            "distinct_receipt_pos": int(
                c.execute("SELECT COUNT(DISTINCT po_number) FROM po_receipts").fetchone()[0] or 0
            ),
            "distinct_order_parts": int(
                c.execute(
                    "SELECT COUNT(DISTINCT part_number) FROM po_orders WHERE IFNULL(part_number, '') != ''"
                ).fetchone()[0]
                or 0
            ),
            "distinct_receipt_parts": int(
                c.execute(
                    "SELECT COUNT(DISTINCT part_number) FROM po_receipts WHERE IFNULL(part_number, '') != ''"
                ).fetchone()[0]
                or 0
            ),
        }

    def top_n(
        self,
        *,
        source: str = "orders",
        group_by: str = "part_number",
        po_number: str | None = None,
        part_number: str | None = None,
        vendor: str | None = None,
        site: str | None = None,
        as_of_date: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        limit = max(1, min(100, int(limit)))
        if source == "orders":
            return self._top_n_base(
                table_name="po_orders",
                qty_field="qty_ordered",
                date_field="order_date",
                group_map=_ORDER_GROUP_FIELDS,
                group_by=group_by,
                po_number=po_number,
                part_number=part_number,
                vendor=vendor,
                site=site,
                as_of_date=as_of_date,
                limit=limit,
            )
        if source == "receipts":
            return self._top_n_base(
                table_name="po_receipts",
                qty_field="qty_received",
                date_field="receive_date",
                group_map=_RECEIPT_GROUP_FIELDS,
                group_by=group_by,
                po_number=po_number,
                part_number=part_number,
                vendor=None,
                site=None,
                as_of_date=as_of_date,
                limit=limit,
            )
        if source == "outstanding":
            group_field = _OUTSTANDING_GROUP_FIELDS.get(group_by)
            if not group_field:
                raise ValueError(f"Unsupported group_by for outstanding: {group_by}")
            sql, params = self._outstanding_as_of_sql(
                po_number=po_number,
                part_number=part_number,
                vendor=vendor,
                site=site,
                as_of_date=as_of_date,
            )
            rows = self._conn.execute(
                f"""
                WITH outstanding_rows AS (
                    {sql}
                )
                SELECT
                    {group_field} AS group_value,
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT po_number) AS distinct_po_count,
                    COALESCE(SUM(qty_outstanding), 0.0) AS total_qty
                FROM outstanding_rows
                WHERE qty_outstanding > 0
                  AND IFNULL({group_field}, '') != ''
                GROUP BY {group_field}
                ORDER BY total_qty DESC, group_value ASC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()
            return [self._group_row_to_dict(group_by, row) for row in rows]
        raise ValueError(f"Unsupported source: {source}")

    def count_by(
        self,
        *,
        source: str = "orders",
        group_by: str = "part_number",
        po_number: str | None = None,
        part_number: str | None = None,
        vendor: str | None = None,
        site: str | None = None,
        as_of_date: str | None = None,
    ) -> list[dict]:
        if source == "orders":
            return self._count_by_base(
                table_name="po_orders",
                qty_field="qty_ordered",
                date_field="order_date",
                group_map=_ORDER_GROUP_FIELDS,
                group_by=group_by,
                po_number=po_number,
                part_number=part_number,
                vendor=vendor,
                site=site,
                as_of_date=as_of_date,
            )
        if source == "receipts":
            return self._count_by_base(
                table_name="po_receipts",
                qty_field="qty_received",
                date_field="receive_date",
                group_map=_RECEIPT_GROUP_FIELDS,
                group_by=group_by,
                po_number=po_number,
                part_number=part_number,
                vendor=None,
                site=None,
                as_of_date=as_of_date,
            )
        if source == "outstanding":
            group_field = _OUTSTANDING_GROUP_FIELDS.get(group_by)
            if not group_field:
                raise ValueError(f"Unsupported group_by for outstanding: {group_by}")
            sql, params = self._outstanding_as_of_sql(
                po_number=po_number,
                part_number=part_number,
                vendor=vendor,
                site=site,
                as_of_date=as_of_date,
            )
            rows = self._conn.execute(
                f"""
                WITH outstanding_rows AS (
                    {sql}
                )
                SELECT
                    {group_field} AS group_value,
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT po_number) AS distinct_po_count,
                    COALESCE(SUM(qty_outstanding), 0.0) AS total_qty
                FROM outstanding_rows
                WHERE qty_outstanding > 0
                  AND IFNULL({group_field}, '') != ''
                GROUP BY {group_field}
                ORDER BY group_value ASC
                """,
                params,
            ).fetchall()
            return [self._group_row_to_dict(group_by, row) for row in rows]
        raise ValueError(f"Unsupported source: {source}")

    def count_outstanding_as_of(
        self,
        *,
        part_number: str | None = None,
        po_number: str | None = None,
        vendor: str | None = None,
        site: str | None = None,
        as_of_date: str | None = None,
    ) -> dict[str, float | int]:
        sql, params = self._outstanding_as_of_sql(
            po_number=po_number,
            part_number=part_number,
            vendor=vendor,
            site=site,
            as_of_date=as_of_date,
        )
        row = self._conn.execute(
            f"""
            WITH outstanding_rows AS (
                {sql}
            )
            SELECT
                COUNT(*) AS outstanding_rows,
                COUNT(DISTINCT po_number) AS distinct_po_count,
                COUNT(DISTINCT part_number) AS distinct_part_count,
                COALESCE(SUM(qty_outstanding), 0.0) AS total_qty_outstanding
            FROM outstanding_rows
            WHERE qty_outstanding > 0
            """,
            params,
        ).fetchone()
        return {
            "outstanding_rows": int(row[0] or 0),
            "distinct_po_count": int(row[1] or 0),
            "distinct_part_count": int(row[2] or 0),
            "total_qty_outstanding": float(row[3] or 0.0),
        }

    def lead_time_rows(
        self,
        *,
        po_number: str | None = None,
        part_number: str | None = None,
        vendor: str | None = None,
        site: str | None = None,
        min_days: int | None = None,
        max_days: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        limit = max(1, min(500, int(limit)))
        clauses = [
            "IFNULL(o.order_date, '') != ''",
            "IFNULL(r.receive_date, '') != ''",
        ]
        params: list[object] = []
        if po_number:
            clauses.append("o.po_number = ?")
            params.append(po_number)
        if part_number:
            clauses.append("IFNULL(o.part_number, '') = ?")
            params.append(part_number)
        if vendor:
            clauses.append("IFNULL(o.vendor, '') = ?")
            params.append(vendor)
        if site:
            clauses.append("IFNULL(o.site, '') = ?")
            params.append(site)
        lead_expr = "CAST(julianday(r.receive_date) - julianday(o.order_date) AS INTEGER)"
        if min_days is not None:
            clauses.append(f"{lead_expr} >= ?")
            params.append(int(min_days))
        if max_days is not None:
            clauses.append(f"{lead_expr} <= ?")
            params.append(int(max_days))
        rows = self._conn.execute(
            f"""
            WITH order_rollup AS (
                SELECT
                    po_number,
                    IFNULL(part_number, '') AS part_number,
                    IFNULL(vendor, '') AS vendor,
                    IFNULL(site, '') AS site,
                    MIN(order_date) AS order_date,
                    SUM(COALESCE(qty_ordered, 0.0)) AS qty_ordered
                FROM po_orders
                GROUP BY po_number, IFNULL(part_number, ''), IFNULL(vendor, ''), IFNULL(site, '')
            ),
            receipt_rollup AS (
                SELECT
                    po_number,
                    IFNULL(part_number, '') AS part_number,
                    MIN(receive_date) AS receive_date,
                    SUM(COALESCE(qty_received, 0.0)) AS qty_received
                FROM po_receipts
                GROUP BY po_number, IFNULL(part_number, '')
            )
            SELECT
                o.po_number,
                o.part_number,
                o.vendor,
                o.site,
                o.order_date,
                r.receive_date,
                {lead_expr} AS lead_time_days,
                COALESCE(o.qty_ordered, 0.0) AS qty_ordered,
                COALESCE(r.qty_received, 0.0) AS qty_received
            FROM order_rollup o
            INNER JOIN receipt_rollup r
                ON r.po_number = o.po_number
               AND r.part_number = o.part_number
            WHERE {' AND '.join(clauses)}
            ORDER BY lead_time_days DESC, o.po_number ASC, o.part_number ASC
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
        return [
            {
                "po_number": row[0],
                "part_number": row[1],
                "vendor": row[2],
                "site": row[3],
                "order_date": row[4],
                "receive_date": row[5],
                "lead_time_days": int(row[6] or 0),
                "qty_ordered": float(row[7] or 0.0),
                "qty_received": float(row[8] or 0.0),
            }
            for row in rows
        ]

    def _top_n_base(
        self,
        *,
        table_name: str,
        qty_field: str,
        date_field: str,
        group_map: dict[str, str],
        group_by: str,
        po_number: str | None,
        part_number: str | None,
        vendor: str | None,
        site: str | None,
        as_of_date: str | None,
        limit: int,
    ) -> list[dict]:
        group_field = group_map.get(group_by)
        if not group_field:
            raise ValueError(f"Unsupported group_by for {table_name}: {group_by}")
        where, params = self._base_where(
            table_name=table_name,
            po_number=po_number,
            part_number=part_number,
            vendor=vendor,
            site=site,
            as_of_date=as_of_date,
            date_field=date_field,
        )
        rows = self._conn.execute(
            f"""
            SELECT
                {group_field} AS group_value,
                COUNT(*) AS row_count,
                COUNT(DISTINCT po_number) AS distinct_po_count,
                COALESCE(SUM(COALESCE({qty_field}, 0.0)), 0.0) AS total_qty
            FROM {table_name}
            WHERE {where}
              AND IFNULL({group_field}, '') != ''
            GROUP BY {group_field}
            ORDER BY total_qty DESC, group_value ASC
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
        return [self._group_row_to_dict(group_by, row) for row in rows]

    def _count_by_base(
        self,
        *,
        table_name: str,
        qty_field: str,
        date_field: str,
        group_map: dict[str, str],
        group_by: str,
        po_number: str | None,
        part_number: str | None,
        vendor: str | None,
        site: str | None,
        as_of_date: str | None,
    ) -> list[dict]:
        group_field = group_map.get(group_by)
        if not group_field:
            raise ValueError(f"Unsupported group_by for {table_name}: {group_by}")
        where, params = self._base_where(
            table_name=table_name,
            po_number=po_number,
            part_number=part_number,
            vendor=vendor,
            site=site,
            as_of_date=as_of_date,
            date_field=date_field,
        )
        rows = self._conn.execute(
            f"""
            SELECT
                {group_field} AS group_value,
                COUNT(*) AS row_count,
                COUNT(DISTINCT po_number) AS distinct_po_count,
                COALESCE(SUM(COALESCE({qty_field}, 0.0)), 0.0) AS total_qty
            FROM {table_name}
            WHERE {where}
              AND IFNULL({group_field}, '') != ''
            GROUP BY {group_field}
            ORDER BY group_value ASC
            """,
            params,
        ).fetchall()
        return [self._group_row_to_dict(group_by, row) for row in rows]

    def _base_where(
        self,
        *,
        table_name: str,
        po_number: str | None,
        part_number: str | None,
        vendor: str | None,
        site: str | None,
        as_of_date: str | None,
        date_field: str,
    ) -> tuple[str, list[object]]:
        clauses = ["1=1"]
        params: list[object] = []
        if po_number:
            clauses.append("po_number = ?")
            params.append(po_number)
        if part_number:
            clauses.append("IFNULL(part_number, '') = ?")
            params.append(part_number)
        if vendor and table_name == "po_orders":
            clauses.append("IFNULL(vendor, '') = ?")
            params.append(vendor)
        if site and table_name == "po_orders":
            clauses.append("IFNULL(site, '') = ?")
            params.append(site)
        if as_of_date:
            clauses.append(f"IFNULL({date_field}, '') != ''")
            clauses.append(f"{date_field} <= ?")
            params.append(as_of_date)
        return " AND ".join(clauses), params

    def _outstanding_as_of_sql(
        self,
        *,
        po_number: str | None,
        part_number: str | None,
        vendor: str | None,
        site: str | None,
        as_of_date: str | None,
    ) -> tuple[str, list[object]]:
        order_clauses = ["1=1"]
        order_params: list[object] = []
        receipt_clauses = ["1=1"]
        receipt_params: list[object] = []

        if po_number:
            order_clauses.append("po_number = ?")
            receipt_clauses.append("po_number = ?")
            order_params.append(po_number)
            receipt_params.append(po_number)
        if part_number:
            order_clauses.append("IFNULL(part_number, '') = ?")
            receipt_clauses.append("IFNULL(part_number, '') = ?")
            order_params.append(part_number)
            receipt_params.append(part_number)
        if vendor:
            order_clauses.append("IFNULL(vendor, '') = ?")
            order_params.append(vendor)
        if site:
            order_clauses.append("IFNULL(site, '') = ?")
            order_params.append(site)
        if as_of_date:
            order_clauses.append("IFNULL(order_date, '') != ''")
            order_clauses.append("order_date <= ?")
            order_params.append(as_of_date)
            receipt_clauses.append("IFNULL(receive_date, '') != ''")
            receipt_clauses.append("receive_date <= ?")
            receipt_params.append(as_of_date)

        sql = f"""
            WITH order_rollup AS (
                SELECT
                    po_number,
                    part_number,
                    vendor,
                    site,
                    MIN(CASE WHEN IFNULL(order_date, '') != '' THEN order_date END) AS order_date,
                    SUM(COALESCE(qty_ordered, 0.0)) AS qty_ordered
                FROM po_orders
                WHERE {' AND '.join(order_clauses)}
                GROUP BY po_number, part_number, vendor, site
            ),
            receipt_rollup AS (
                SELECT
                    po_number,
                    part_number,
                    MAX(CASE WHEN IFNULL(receive_date, '') != '' THEN receive_date END) AS receive_date,
                    SUM(COALESCE(qty_received, 0.0)) AS qty_received
                FROM po_receipts
                WHERE {' AND '.join(receipt_clauses)}
                GROUP BY po_number, part_number
            )
            SELECT
                o.po_number,
                o.part_number,
                o.vendor,
                o.site,
                o.order_date,
                r.receive_date,
                o.qty_ordered,
                COALESCE(r.qty_received, 0.0) AS qty_received,
                CASE
                    WHEN COALESCE(o.qty_ordered, 0.0) - COALESCE(r.qty_received, 0.0) > 0.0
                    THEN COALESCE(o.qty_ordered, 0.0) - COALESCE(r.qty_received, 0.0)
                    ELSE 0.0
                END AS qty_outstanding
            FROM order_rollup o
            LEFT JOIN receipt_rollup r
              ON r.po_number = o.po_number
             AND IFNULL(r.part_number, '') = IFNULL(o.part_number, '')
        """
        return sql, order_params + receipt_params

    def _group_row_to_dict(self, group_by: str, row: tuple) -> dict:
        return {
            "group_by": group_by,
            "group_value": row[0],
            "row_count": int(row[1] or 0),
            "distinct_po_count": int(row[2] or 0),
            "total_qty": float(row[3] or 0.0),
        }

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            logger.debug("Failed closing PO lifecycle store", exc_info=True)
