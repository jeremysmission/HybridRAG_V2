"""
SQLite entity store — quality-gated entities and extracted table rows.

Store 2 in the tri-store architecture. Holds:
  - entities: typed, confidence-scored, linked to chunks/sources
  - extracted_tables: spreadsheet/table rows preserved as structured data

Schema designed for direct lookups ("Who is the POC?") and
aggregation queries ("How many times has part X failed?").
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_FTS_TABLE = "entities_fts"
_SLOW_QUERY_LOG_THRESHOLD_S = 0.250


@dataclass
class Entity:
    """A single extracted entity."""

    entity_type: str          # PERSON, PART, SITE, DATE, PO, ORG, CONTACT
    text: str                 # normalized entity text
    raw_text: str             # original text from document
    confidence: float         # 0.0–1.0 extraction confidence
    chunk_id: str             # link to LanceDB chunk
    source_path: str          # document path
    context: str = ""         # surrounding sentence for provenance


@dataclass
class TableRow:
    """A single extracted table row."""

    source_path: str
    table_id: str             # unique per table within a source
    row_index: int
    headers: str              # JSON-encoded list of column names
    values: str               # JSON-encoded list of cell values
    chunk_id: str = ""


@dataclass
class EntityResult:
    """Result from an entity lookup."""

    entity_type: str
    text: str
    raw_text: str
    confidence: float
    source_path: str
    context: str
    chunk_id: str


@dataclass
class TableResult:
    """Result from a table query."""

    source_path: str
    table_id: str
    row_index: int
    headers: list[str]
    values: list[str]


class EntityStore:
    """
    SQLite store for extracted entities and table rows.

    Supports:
      - Bulk insert with dedup (chunk_id + entity_type + text)
      - Lookup by type, text pattern, source
      - Aggregation (count by type, count by text across sources)
      - Table row storage and retrieval
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # GUI queries run on background threads, so the store must allow
        # access from outside the creating thread.
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=memory")
        self._conn.execute("PRAGMA cache_size=-64000")  # 64MB
        self._conn.execute("PRAGMA mmap_size=268435456")  # 256MB
        self._fts_ready = False
        self._create_tables()

    def _create_tables(self) -> None:
        """Create entity and table schemas if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                text TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                confidence REAL NOT NULL,
                chunk_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                context TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chunk_id, entity_type, text)
            );

            CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
            CREATE INDEX IF NOT EXISTS idx_entities_text ON entities(text);
            CREATE INDEX IF NOT EXISTS idx_entities_source ON entities(source_path);
            CREATE INDEX IF NOT EXISTS idx_entities_chunk ON entities(chunk_id);

            CREATE TABLE IF NOT EXISTS extracted_tables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                table_id TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                headers TEXT NOT NULL,
                values_json TEXT NOT NULL,
                chunk_id TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_path, table_id, row_index)
            );

            CREATE INDEX IF NOT EXISTS idx_tables_source ON extracted_tables(source_path);
            CREATE INDEX IF NOT EXISTS idx_tables_table_id ON extracted_tables(table_id);
        """)
        self._ensure_entity_fts()
        self._conn.commit()

    def _ensure_entity_fts(self) -> None:
        """Create and backfill the optional FTS5 trigram index for ``entities.text``."""
        try:
            self._conn.executescript(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_TABLE} USING fts5(
                    text,
                    content='entities',
                    content_rowid='id',
                    tokenize='trigram'
                );

                CREATE TRIGGER IF NOT EXISTS entities_ai_fts AFTER INSERT ON entities BEGIN
                    INSERT INTO {_FTS_TABLE}(rowid, text)
                    VALUES (new.id, new.text);
                END;

                CREATE TRIGGER IF NOT EXISTS entities_ad_fts AFTER DELETE ON entities BEGIN
                    INSERT INTO {_FTS_TABLE}({_FTS_TABLE}, rowid, text)
                    VALUES('delete', old.id, old.text);
                END;

                CREATE TRIGGER IF NOT EXISTS entities_au_fts AFTER UPDATE ON entities BEGIN
                    INSERT INTO {_FTS_TABLE}({_FTS_TABLE}, rowid, text)
                    VALUES('delete', old.id, old.text);
                    INSERT INTO {_FTS_TABLE}(rowid, text)
                    VALUES (new.id, new.text);
                END;
            """)
            self._conn.execute(f"INSERT INTO {_FTS_TABLE}({_FTS_TABLE}) VALUES('rebuild')")
            self._fts_ready = True
        except sqlite3.OperationalError as exc:
            self._fts_ready = False
            logger.warning("EntityStore FTS5 unavailable; LIKE fallback remains active: %s", exc)

    def _fts_match_query_from_like(self, text_pattern: str | None) -> str | None:
        """Translate simple ``LIKE '%...%'`` patterns into safe FTS5 MATCH text."""
        if not self._fts_ready or not text_pattern:
            return None
        pattern = str(text_pattern)
        if "_" in pattern:
            return None
        match = re.fullmatch(r"%+(.+)%+", pattern)
        if not match:
            return None
        needle = match.group(1).strip()
        if len(needle) < 3:
            return None
        return f"\"{needle.replace('\"', '\"\"')}\""

    def insert_entities(self, entities: list[Entity]) -> int:
        """
        Bulk insert entities with dedup.

        Returns number of entities inserted (skips duplicates).
        """
        if not entities:
            return 0

        inserted = 0
        for e in entities:
            try:
                self._conn.execute(
                    """INSERT OR IGNORE INTO entities
                       (entity_type, text, raw_text, confidence, chunk_id, source_path, context)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (e.entity_type, e.text, e.raw_text, e.confidence,
                     e.chunk_id, e.source_path, e.context),
                )
                inserted += self._conn.total_changes  # approximate
            except sqlite3.IntegrityError:
                pass
        self._conn.commit()
        return inserted

    def insert_table_rows(self, rows: list[TableRow]) -> int:
        """Bulk insert table rows with dedup."""
        if not rows:
            return 0

        for r in rows:
            self._conn.execute(
                """INSERT OR IGNORE INTO extracted_tables
                   (source_path, table_id, row_index, headers, values_json, chunk_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (r.source_path, r.table_id, r.row_index,
                 r.headers, r.values, r.chunk_id),
            )
        self._conn.commit()
        return len(rows)

    def _log_slow_query_plan(
        self,
        *,
        query_name: str,
        sql: str,
        params: list,
        elapsed_s: float,
    ) -> None:
        """Log SQLite query-plan details when an entity lookup is unexpectedly slow."""
        if elapsed_s < _SLOW_QUERY_LOG_THRESHOLD_S:
            return
        try:
            plan_rows = self._conn.execute(
                f"EXPLAIN QUERY PLAN {sql}",
                params,
            ).fetchall()
            plan_summary = [" | ".join(str(part) for part in row) for row in plan_rows]
        except Exception as exc:
            plan_summary = [f"EXPLAIN failed: {exc}"]

        logger.warning(
            "EntityStore slow query: %s took %.3fs | params=%s | plan=%s",
            query_name,
            elapsed_s,
            params,
            plan_summary,
        )

    def lookup_entities(
        self,
        entity_type: str | None = None,
        text_pattern: str | None = None,
        source_path: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[EntityResult]:
        """
        Look up entities by type, text pattern, or source.

        text_pattern uses SQL LIKE — pass '%Torres%' for substring match.
        """
        conditions = ["e.confidence >= ?"]
        params: list = [min_confidence]
        join_sql = ""
        fts_query = self._fts_match_query_from_like(text_pattern)

        if entity_type:
            conditions.append("e.entity_type = ?")
            params.append(entity_type)
        if fts_query:
            join_sql = f"JOIN {_FTS_TABLE} fts ON fts.rowid = e.id"
            conditions.append("fts.text MATCH ?")
            params.append(fts_query)
        elif text_pattern:
            conditions.append("e.text LIKE ?")
            params.append(text_pattern)
        if source_path:
            conditions.append("e.source_path LIKE ?")
            params.append(f"%{source_path}%")

        where = " AND ".join(conditions)
        sql = f"""SELECT e.entity_type, e.text, e.raw_text, e.confidence,
                         e.source_path, e.context, e.chunk_id
                  FROM entities e
                  {join_sql}
                  WHERE {where}
                  ORDER BY e.confidence DESC
                  LIMIT ?"""
        query_params = params + [limit]
        t0 = time.perf_counter()
        rows = self._conn.execute(sql, query_params).fetchall()
        self._log_slow_query_plan(
            query_name="lookup_entities",
            sql=sql,
            params=query_params,
            elapsed_s=time.perf_counter() - t0,
        )

        return [
            EntityResult(
                entity_type=r[0], text=r[1], raw_text=r[2],
                confidence=r[3], source_path=r[4], context=r[5],
                chunk_id=r[6],
            )
            for r in rows
        ]

    def aggregate_entity(
        self,
        entity_type: str | None = None,
        text_pattern: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[dict]:
        """
        Count entity occurrences across documents.

        Returns list of {text, count, sources} dicts.
        """
        conditions = ["e.confidence >= ?"]
        params: list = [min_confidence]
        join_sql = ""
        fts_query = self._fts_match_query_from_like(text_pattern)

        if entity_type:
            conditions.append("e.entity_type = ?")
            params.append(entity_type)
        if fts_query:
            join_sql = f"JOIN {_FTS_TABLE} fts ON fts.rowid = e.id"
            conditions.append("fts.text MATCH ?")
            params.append(fts_query)
        elif text_pattern:
            conditions.append("e.text LIKE ?")
            params.append(text_pattern)

        where = " AND ".join(conditions)
        sql = f"""SELECT e.text, COUNT(*) as cnt,
                         GROUP_CONCAT(DISTINCT e.source_path) as sources
                  FROM entities e
                  {join_sql}
                  WHERE {where}
                  GROUP BY e.text
                  ORDER BY cnt DESC"""
        t0 = time.perf_counter()
        rows = self._conn.execute(sql, params).fetchall()
        self._log_slow_query_plan(
            query_name="aggregate_entity",
            sql=sql,
            params=params,
            elapsed_s=time.perf_counter() - t0,
        )

        return [
            {"text": r[0], "count": r[1], "sources": r[2].split(",") if r[2] else []}
            for r in rows
        ]

    def query_tables(
        self,
        source_pattern: str | None = None,
        header_contains: str | None = None,
        value_contains: str | None = None,
        limit: int = 50,
    ) -> list[TableResult]:
        """
        Query extracted table rows.

        Supports filtering by source, header content, or cell values.
        """
        import json

        conditions = ["1=1"]
        params: list = []

        if source_pattern:
            conditions.append("source_path LIKE ?")
            params.append(f"%{source_pattern}%")
        if header_contains:
            conditions.append("headers LIKE ?")
            params.append(f"%{header_contains}%")
        if value_contains:
            conditions.append("values_json LIKE ?")
            params.append(f"%{value_contains}%")

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"""SELECT source_path, table_id, row_index, headers, values_json
                FROM extracted_tables
                WHERE {where}
                ORDER BY source_path, table_id, row_index
                LIMIT ?""",
            params + [limit],
        ).fetchall()

        results = []
        for r in rows:
            try:
                headers = json.loads(r[3])
                values = json.loads(r[4])
            except json.JSONDecodeError:
                headers = [r[3]]
                values = [r[4]]
            results.append(
                TableResult(
                    source_path=r[0], table_id=r[1], row_index=r[2],
                    headers=headers, values=values,
                )
            )
        return results

    def count_entities(self) -> int:
        """Total entities in the store."""
        row = self._conn.execute("SELECT COUNT(*) FROM entities").fetchone()
        return row[0] if row else 0

    def count_table_rows(self) -> int:
        """Total table rows in the store."""
        row = self._conn.execute("SELECT COUNT(*) FROM extracted_tables").fetchone()
        return row[0] if row else 0

    def entity_type_summary(self) -> dict[str, int]:
        """Count of entities by type."""
        rows = self._conn.execute(
            "SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
