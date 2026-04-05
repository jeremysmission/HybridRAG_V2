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
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


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
        self._conn.commit()

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
        conditions = ["confidence >= ?"]
        params: list = [min_confidence]

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if text_pattern:
            conditions.append("text LIKE ?")
            params.append(text_pattern)
        if source_path:
            conditions.append("source_path LIKE ?")
            params.append(f"%{source_path}%")

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"""SELECT entity_type, text, raw_text, confidence,
                       source_path, context, chunk_id
                FROM entities
                WHERE {where}
                ORDER BY confidence DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()

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
        conditions = ["confidence >= ?"]
        params: list = [min_confidence]

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if text_pattern:
            conditions.append("text LIKE ?")
            params.append(text_pattern)

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"""SELECT text, COUNT(*) as cnt,
                       GROUP_CONCAT(DISTINCT source_path) as sources
                FROM entities
                WHERE {where}
                GROUP BY text
                ORDER BY cnt DESC""",
            params,
        ).fetchall()

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
