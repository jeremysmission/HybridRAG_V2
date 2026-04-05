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

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import lancedb
import numpy as np
import pyarrow as pa

logger = logging.getLogger(__name__)


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

    INGEST_BATCH_SIZE = 1000

    def ingest_chunks(
        self,
        chunks: list[dict],
        vectors: np.ndarray,
        batch_size: int | None = None,
    ) -> int:
        """
        Bulk insert chunks with vectors into the store.

        Inserts in batches (default 1000) to limit peak memory and allow
        progress reporting on large imports.  Vectors can be a memory-mapped
        array — each batch slice is materialised independently.

        Returns number of chunks inserted.
        """
        if len(chunks) == 0:
            return 0

        batch_sz = batch_size or self.INGEST_BATCH_SIZE
        total = len(chunks)

        # Load existing chunk IDs once for dedup (scan, not search)
        existing_ids: set[str] = set()
        if self._table is not None:
            try:
                scanner = self._table.to_lance().scanner(
                    columns=["chunk_id"],
                    batch_size=8192,
                )
                for batch in scanner.to_batches():
                    existing_ids.update(batch.column("chunk_id").to_pylist())
            except Exception:
                # Fallback: slower but functional
                try:
                    existing = (
                        self._table.search()
                        .select(["chunk_id"])
                        .limit(self._table.count_rows())
                        .to_list()
                    )
                    existing_ids = {r["chunk_id"] for r in existing}
                except Exception:
                    pass

        inserted_total = 0

        for start in range(0, total, batch_sz):
            end = min(start + batch_sz, total)
            batch_chunks = chunks[start:end]

            # Materialise this slice of vectors as float32
            batch_vecs = vectors[start:end].astype(np.float32)

            records = []
            for i, chunk in enumerate(batch_chunks):
                cid = chunk["chunk_id"]
                if cid in existing_ids:
                    continue
                records.append({
                    "chunk_id": cid,
                    "text": chunk["text"],
                    "enriched_text": chunk.get("enriched_text") or "",
                    "vector": batch_vecs[i].tolist(),
                    "source_path": chunk["source_path"],
                    "chunk_index": chunk.get("chunk_index", 0),
                    "parse_quality": chunk.get("parse_quality", 1.0),
                })

            if not records:
                continue

            if self._table is None:
                self._table = self.db.create_table(self.TABLE_NAME, data=records)
            else:
                self._table.add(records)

            inserted_total += len(records)

            if total > batch_sz:
                logger.info(
                    "  Ingested %s / %s chunks (%d new this batch)",
                    f"{end:,}", f"{total:,}", len(records),
                )

        return inserted_total

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

    def create_vector_index(self, num_partitions: int | None = None, num_sub_vectors: int | None = None) -> None:
        """Create IVF_PQ vector index for faster search at scale."""
        if self._table is None:
            return
        rows = self.count()
        if rows < 10000:  # Not worth indexing below 10K
            return
        parts = num_partitions or max(1, rows // 4096)
        sub_vecs = num_sub_vectors or max(1, 768 // 8)  # 768-dim / 8
        try:
            self._table.create_index(
                metric="cosine",
                num_partitions=parts,
                num_sub_vectors=sub_vecs,
                replace=True,
            )
        except Exception as e:
            logger.warning("Vector index creation failed: %s", e)

    def optimize(self) -> None:
        """Compact data and clean old versions."""
        if self._table is not None:
            try:
                self._table.optimize()
            except Exception:
                pass

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
