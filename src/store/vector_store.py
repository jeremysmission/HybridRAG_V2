"""
Vector store — FAISS + SQLite FTS5 fallback while LanceDB waiver is pending.

Provides the same interface the query pipeline expects from LanceDB:
  - ingest_chunks(): bulk insert chunks with vectors and metadata
  - hybrid_search(): vector kNN + BM25 full-text + metadata filtering
  - count(): total chunks in store

When LanceDB waiver is approved, this module will be replaced by lance_store.py
with the same public API.

Storage:
  - FAISS index file (vectors, float16 → float32 for FAISS)
  - SQLite database (chunk text, metadata, FTS5 full-text index)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np


@dataclass
class ChunkResult:
    """Single search result from the vector store."""

    chunk_id: str
    text: str
    enriched_text: str | None
    source_path: str
    score: float
    chunk_index: int = 0
    parse_quality: float = 1.0


class VectorStore:
    """
    FAISS + SQLite FTS5 hybrid store.

    Fallback implementation until LanceDB waiver is approved.
    Same public API that lance_store.py will provide.
    """

    def __init__(self, db_dir: str):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)

        self._faiss_path = self.db_dir / "vectors.faiss"
        self._sqlite_path = self.db_dir / "chunks.sqlite3"

        self._index: faiss.IndexFlatIP | None = None
        self._dim = 0
        self._id_map: list[str] = []  # positional index → chunk_id

        self._conn = sqlite3.connect(str(self._sqlite_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._load_faiss()

    def _init_schema(self) -> None:
        """Create SQLite tables and FTS5 virtual table."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id     TEXT PRIMARY KEY,
                text         TEXT NOT NULL,
                enriched_text TEXT,
                source_path  TEXT NOT NULL,
                chunk_index  INTEGER DEFAULT 0,
                parse_quality REAL DEFAULT 1.0,
                faiss_idx    INTEGER
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                text,
                enriched_text,
                content='chunks',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, text, enriched_text)
                VALUES (new.rowid, new.text, new.enriched_text);
            END;
        """)
        self._conn.commit()

    def _load_faiss(self) -> None:
        """Load existing FAISS index from disk if available."""
        if self._faiss_path.exists():
            self._index = faiss.read_index(str(self._faiss_path))
            self._dim = self._index.d
            # Rebuild id_map from SQLite
            rows = self._conn.execute(
                "SELECT chunk_id FROM chunks ORDER BY faiss_idx"
            ).fetchall()
            self._id_map = [r["chunk_id"] for r in rows]

    def ingest_chunks(self, chunks: list[dict], vectors: np.ndarray) -> int:
        """
        Bulk insert chunks with vectors into the store.

        Returns the number of chunks inserted.
        """
        if len(chunks) == 0:
            return 0

        # Initialize FAISS index on first ingest
        dim = vectors.shape[1]
        if self._index is None:
            self._index = faiss.IndexFlatIP(dim)
            self._dim = dim

        # Convert to float32 for FAISS (it doesn't support float16)
        vecs_f32 = vectors.astype(np.float32)
        # Normalize for cosine similarity via inner product
        faiss.normalize_L2(vecs_f32)

        start_idx = self._index.ntotal
        inserted = 0

        for i, chunk in enumerate(chunks):
            chunk_id = chunk["chunk_id"]

            # Skip if already exists (deterministic IDs = crash-safe)
            existing = self._conn.execute(
                "SELECT 1 FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if existing:
                continue

            faiss_idx = start_idx + inserted

            self._conn.execute(
                """INSERT INTO chunks (chunk_id, text, enriched_text, source_path,
                   chunk_index, parse_quality, faiss_idx)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk_id,
                    chunk["text"],
                    chunk.get("enriched_text"),
                    chunk["source_path"],
                    chunk.get("chunk_index", 0),
                    chunk.get("parse_quality", 1.0),
                    faiss_idx,
                ),
            )
            self._id_map.append(chunk_id)
            self._index.add(vecs_f32[i:i+1])
            inserted += 1

        self._conn.commit()
        faiss.write_index(self._index, str(self._faiss_path))
        return inserted

    def hybrid_search(
        self,
        query_vector: np.ndarray,
        query_text: str = "",
        top_k: int = 10,
    ) -> list[ChunkResult]:
        """
        Hybrid search: vector kNN + BM25 full-text, fused by RRF.

        Falls back to vector-only if no query_text or FTS5 returns nothing.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        # Vector search
        vec = query_vector.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)
        # Search more candidates than top_k for fusion
        n_candidates = min(top_k * 3, self._index.ntotal)
        scores, indices = self._index.search(vec, n_candidates)

        vector_results = {}
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < 0 or idx >= len(self._id_map):
                continue
            cid = self._id_map[idx]
            vector_results[cid] = {"score": float(score), "rank": rank}

        # BM25 full-text search via FTS5
        fts_results = {}
        if query_text.strip():
            # Escape FTS5 special chars
            safe_query = query_text.replace('"', '""')
            try:
                rows = self._conn.execute(
                    """SELECT c.chunk_id, rank
                       FROM chunks_fts f
                       JOIN chunks c ON c.rowid = f.rowid
                       WHERE chunks_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (f'"{safe_query}"', n_candidates),
                ).fetchall()
                for rank, row in enumerate(rows):
                    fts_results[row["chunk_id"]] = {"rank": rank}
            except sqlite3.OperationalError:
                pass  # FTS5 query parse error — fall back to vector only

        # RRF fusion (k=60 is standard)
        k = 60
        all_ids = set(vector_results.keys()) | set(fts_results.keys())
        fused = {}
        for cid in all_ids:
            rrf_score = 0.0
            if cid in vector_results:
                rrf_score += 1.0 / (k + vector_results[cid]["rank"])
            if cid in fts_results:
                rrf_score += 1.0 / (k + fts_results[cid]["rank"])
            fused[cid] = rrf_score

        # Sort by fused score, take top_k
        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # Fetch full chunk data
        results = []
        for cid, score in ranked:
            row = self._conn.execute(
                "SELECT * FROM chunks WHERE chunk_id = ?", (cid,)
            ).fetchone()
            if row:
                results.append(ChunkResult(
                    chunk_id=row["chunk_id"],
                    text=row["text"],
                    enriched_text=row["enriched_text"],
                    source_path=row["source_path"],
                    score=score,
                    chunk_index=row["chunk_index"],
                    parse_quality=row["parse_quality"],
                ))
        return results

    def count(self) -> int:
        """Total chunks in the store."""
        if self._index is None:
            return 0
        return self._index.ntotal

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()
