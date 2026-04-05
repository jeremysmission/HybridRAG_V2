"""
SQLite relationship store — entity-relationship triples for multi-hop queries.

Store 3 in the tri-store architecture. Holds subject-predicate-object triples
extracted from documents, enabling queries like:
  - "Who is the POC for Thule?" → (Thule, POC, SSgt Marcus Webb)
  - "What parts were used at Cedar Ridge?" → (Cedar Ridge, CONSUMED_PART, FM-220)

Designed for 1-3 hop graph traversal via SQL JOINs.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Relationship:
    """A single entity-relationship triple."""

    subject_type: str         # SITE, PERSON, PART, etc.
    subject_text: str         # normalized subject
    predicate: str            # POC_FOR, CONSUMED_AT, REPLACED_BY, etc.
    object_type: str          # entity type of the object
    object_text: str          # normalized object
    confidence: float         # 0.0–1.0
    source_path: str
    chunk_id: str
    context: str = ""         # sentence containing the relationship


@dataclass
class RelationshipResult:
    """Result from a relationship query."""

    subject_type: str
    subject_text: str
    predicate: str
    object_type: str
    object_text: str
    confidence: float
    source_path: str
    context: str


class RelationshipStore:
    """
    SQLite store for entity-relationship triples.

    Supports:
      - Bulk insert with dedup
      - Forward traversal: given subject, find objects
      - Reverse traversal: given object, find subjects
      - Multi-hop: 2-3 hop JOINs for relationship chains
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # GUI queries run on background threads, so the store must allow
        # access from outside the creating thread.
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=memory")
        self._conn.execute("PRAGMA cache_size=-64000")  # 64MB
        self._conn.execute("PRAGMA mmap_size=268435456")  # 256MB
        self._create_tables()

    def _create_tables(self) -> None:
        """Create relationship schema if it doesn't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_type TEXT NOT NULL,
                subject_text TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_text TEXT NOT NULL,
                confidence REAL NOT NULL,
                source_path TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                context TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subject_text, predicate, object_text, chunk_id)
            );

            CREATE INDEX IF NOT EXISTS idx_rel_subject ON relationships(subject_text);
            CREATE INDEX IF NOT EXISTS idx_rel_object ON relationships(object_text);
            CREATE INDEX IF NOT EXISTS idx_rel_predicate ON relationships(predicate);
            CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_path);
            CREATE INDEX IF NOT EXISTS idx_rel_subj_pred ON relationships(subject_text, predicate);
        """)
        self._conn.commit()

    def insert_relationships(self, rels: list[Relationship]) -> int:
        """Bulk insert relationships with dedup. Returns count inserted."""
        if not rels:
            return 0

        for r in rels:
            self._conn.execute(
                """INSERT OR IGNORE INTO relationships
                   (subject_type, subject_text, predicate, object_type,
                    object_text, confidence, source_path, chunk_id, context)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r.subject_type, r.subject_text, r.predicate, r.object_type,
                 r.object_text, r.confidence, r.source_path, r.chunk_id,
                 r.context),
            )
        self._conn.commit()
        return len(rels)

    def find_by_subject(
        self,
        subject_text: str,
        predicate: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[RelationshipResult]:
        """Forward traversal: find relationships where subject matches."""
        conditions = ["subject_text LIKE ? AND confidence >= ?"]
        params: list = [f"%{subject_text}%", min_confidence]

        if predicate:
            conditions.append("predicate = ?")
            params.append(predicate)

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"""SELECT subject_type, subject_text, predicate, object_type,
                       object_text, confidence, source_path, context
                FROM relationships
                WHERE {where}
                ORDER BY confidence DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()

        return [self._row_to_result(r) for r in rows]

    def find_by_object(
        self,
        object_text: str,
        predicate: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[RelationshipResult]:
        """Reverse traversal: find relationships where object matches."""
        conditions = ["object_text LIKE ? AND confidence >= ?"]
        params: list = [f"%{object_text}%", min_confidence]

        if predicate:
            conditions.append("predicate = ?")
            params.append(predicate)

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"""SELECT subject_type, subject_text, predicate, object_type,
                       object_text, confidence, source_path, context
                FROM relationships
                WHERE {where}
                ORDER BY confidence DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()

        return [self._row_to_result(r) for r in rows]

    def find_related(
        self,
        text: str,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[RelationshipResult]:
        """Find all relationships involving an entity (as subject OR object)."""
        rows = self._conn.execute(
            """SELECT subject_type, subject_text, predicate, object_type,
                      object_text, confidence, source_path, context
               FROM relationships
               WHERE (subject_text LIKE ? OR object_text LIKE ?)
                 AND confidence >= ?
               ORDER BY confidence DESC
               LIMIT ?""",
            (f"%{text}%", f"%{text}%", min_confidence, limit),
        ).fetchall()

        return [self._row_to_result(r) for r in rows]

    def multi_hop(
        self,
        start_text: str,
        hops: int = 2,
        min_confidence: float = 0.0,
    ) -> list[list[RelationshipResult]]:
        """
        Multi-hop traversal starting from an entity.

        Returns a list of paths, where each path is a list of relationships.
        Limited to 2-3 hops to avoid runaway queries.
        """
        hops = min(hops, 3)
        paths: list[list[RelationshipResult]] = []

        # Hop 1: direct relationships
        hop1 = self.find_by_subject(start_text, min_confidence=min_confidence)
        for r1 in hop1:
            path = [r1]
            if hops >= 2:
                # Hop 2: follow the object
                hop2 = self.find_by_subject(
                    r1.object_text, min_confidence=min_confidence, limit=10
                )
                for r2 in hop2:
                    path2 = [r1, r2]
                    if hops >= 3:
                        hop3 = self.find_by_subject(
                            r2.object_text, min_confidence=min_confidence, limit=5
                        )
                        for r3 in hop3:
                            paths.append([r1, r2, r3])
                    else:
                        paths.append(path2)
            else:
                paths.append(path)

        return paths

    def count(self) -> int:
        """Total relationships in the store."""
        row = self._conn.execute("SELECT COUNT(*) FROM relationships").fetchone()
        return row[0] if row else 0

    def predicate_summary(self) -> dict[str, int]:
        """Count of relationships by predicate type."""
        rows = self._conn.execute(
            "SELECT predicate, COUNT(*) FROM relationships GROUP BY predicate"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def _row_to_result(self, r: tuple) -> RelationshipResult:
        return RelationshipResult(
            subject_type=r[0], subject_text=r[1], predicate=r[2],
            object_type=r[3], object_text=r[4], confidence=r[5],
            source_path=r[6], context=r[7],
        )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
