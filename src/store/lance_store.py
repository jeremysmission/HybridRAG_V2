"""
LanceDB store — vector + BM25 hybrid search + metadata filtering.

Single store replaces FAISS + FTS5 + numpy memmap.
LanceDB is an embedded serverless DB using Apache Arrow / Lance columnar format
with Tantivy full-text engine.

Schema:
  chunks table: chunk_id, text, enriched_text, vector[768], source_path,
                chunk_index, parse_quality, doc_type, created_at
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import lancedb
import numpy as np
import pyarrow as pa


@dataclass
class ChunkResult:
    """Single search result from the store."""

    chunk_id: str
    text: str
    enriched_text: str | None
    source_path: str
    score: float
    chunk_index: int = 0
    parse_quality: float = 1.0


class LanceStore:
    """
    Vector + BM25 + metadata search via LanceDB.

    Single store replaces FAISS + SQLite FTS5 + memmap.
    """

    TABLE_NAME = "chunks"

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_path))
        self._table = None
        self._try_open_table()

    def _try_open_table(self) -> None:
        """Open existing table if it exists."""
        try:
            if self.TABLE_NAME in self.db.table_names():
                self._table = self.db.open_table(self.TABLE_NAME)
        except Exception:
            self._table = None

    def ingest_chunks(self, chunks: list[dict], vectors: np.ndarray) -> int:
        """
        Bulk insert chunks with vectors into the store.

        Returns number of chunks inserted.
        """
        if len(chunks) == 0:
            return 0

        # Build records for LanceDB
        vecs_f32 = vectors.astype(np.float32)
        records = []
        for i, chunk in enumerate(chunks):
            records.append({
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "enriched_text": chunk.get("enriched_text") or "",
                "vector": vecs_f32[i].tolist(),
                "source_path": chunk["source_path"],
                "chunk_index": chunk.get("chunk_index", 0),
                "parse_quality": chunk.get("parse_quality", 1.0),
            })

        if self._table is None:
            self._table = self.db.create_table(self.TABLE_NAME, data=records)
        else:
            # Check for existing chunk_ids to avoid duplicates
            existing_ids = set()
            try:
                existing = self._table.search().select(["chunk_id"]).limit(self._table.count_rows()).to_list()
                existing_ids = {r["chunk_id"] for r in existing}
            except Exception:
                pass

            new_records = [r for r in records if r["chunk_id"] not in existing_ids]
            if new_records:
                self._table.add(new_records)
            return len(new_records)

        return len(records)

    def hybrid_search(
        self,
        query_vector: np.ndarray,
        query_text: str = "",
        top_k: int = 10,
    ) -> list[ChunkResult]:
        """
        Run hybrid search: vector kNN + BM25 full-text.

        Uses LanceDB's built-in hybrid search with RRF fusion when both
        vector and text queries are provided.
        """
        if self._table is None:
            return []

        vec = query_vector.astype(np.float32).flatten().tolist()

        try:
            # Try hybrid search (vector + FTS)
            if query_text.strip():
                try:
                    results = (
                        self._table.search(vec, query_type="hybrid")
                        .text(query_text)
                        .limit(top_k)
                        .to_list()
                    )
                except Exception:
                    # FTS index may not exist yet — fall back to vector only
                    results = (
                        self._table.search(vec)
                        .limit(top_k)
                        .to_list()
                    )
            else:
                results = (
                    self._table.search(vec)
                    .limit(top_k)
                    .to_list()
                )
        except Exception as e:
            # Fallback: vector-only search
            try:
                results = (
                    self._table.search(vec)
                    .limit(top_k)
                    .to_list()
                )
            except Exception:
                return []

        return [
            ChunkResult(
                chunk_id=r.get("chunk_id", ""),
                text=r.get("text", ""),
                enriched_text=r.get("enriched_text") or None,
                source_path=r.get("source_path", ""),
                score=float(r.get("_distance", 0.0)),
                chunk_index=r.get("chunk_index", 0),
                parse_quality=r.get("parse_quality", 1.0),
            )
            for r in results
        ]

    def count(self) -> int:
        """Total chunks in the store."""
        if self._table is None:
            return 0
        try:
            return self._table.count_rows()
        except Exception:
            return 0

    def create_fts_index(self) -> None:
        """Create full-text search index on text and enriched_text columns."""
        if self._table is None:
            return
        try:
            self._table.create_fts_index(["text", "enriched_text"], replace=True)
        except Exception:
            pass  # FTS index creation is best-effort

    def close(self) -> None:
        """No-op for LanceDB (embedded, no connection to close)."""
        pass
