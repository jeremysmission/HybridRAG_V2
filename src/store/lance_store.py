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
import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import lancedb
import numpy as np

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
    VECTOR_INDEX_NAME = "vector_idx"

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_path))
        self._table = None
        self._search_nprobes: int | None = None
        self._search_refine_factor: int | None = None
        self._try_open_table()

    def _try_open_table(self) -> None:
        """Open existing table if it exists."""
        try:
            if hasattr(self.db, "list_tables"):
                result = self.db.list_tables()
                table_names = getattr(result, "tables", result)
            else:
                table_names = self.db.table_names()
            if self.TABLE_NAME in table_names:
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
        nprobes: int | None = None,
        refine_factor: int | None = None,
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
                    builder = self._table.search(vec, query_type="hybrid")
                    builder = self._apply_search_tuning(
                        builder,
                        nprobes=nprobes,
                        refine_factor=refine_factor,
                    )
                    results = builder.text(query_text).limit(top_k).to_list()
                except Exception:
                    # FTS index may not exist yet — fall back to vector only
                    builder = self._table.search(vec)
                    builder = self._apply_search_tuning(
                        builder,
                        nprobes=nprobes,
                        refine_factor=refine_factor,
                    )
                    results = builder.limit(top_k).to_list()
            else:
                builder = self._table.search(vec)
                builder = self._apply_search_tuning(
                    builder,
                    nprobes=nprobes,
                    refine_factor=refine_factor,
                )
                results = builder.limit(top_k).to_list()
        except Exception:
            # Fallback: vector-only search
            try:
                builder = self._table.search(vec)
                builder = self._apply_search_tuning(
                    builder,
                    nprobes=nprobes,
                    refine_factor=refine_factor,
                )
                results = builder.limit(top_k).to_list()
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

    def configure_search(
        self,
        nprobes: int | None = None,
        refine_factor: int | None = None,
    ) -> None:
        """Set default search tuning applied to future vector queries."""
        self._search_nprobes = nprobes
        self._search_refine_factor = refine_factor

    def list_indices(self) -> list[dict]:
        """Return any index metadata exposed by LanceDB."""
        if self._table is None or not hasattr(self._table, "list_indices"):
            return []
        try:
            raw = self._table.list_indices()
            return [item if isinstance(item, dict) else {"value": str(item)} for item in raw]
        except Exception:
            return []

    def has_vector_index(self) -> bool:
        """Whether the table currently has a vector index."""
        return any("vector" in str(item).lower() for item in self.list_indices())

    def vector_index_stats(self) -> dict:
        """Return best-effort stats for the primary vector index."""
        if self._table is None or not hasattr(self._table, "index_stats"):
            return {}
        try:
            stats = self._table.index_stats(self.VECTOR_INDEX_NAME)
        except Exception:
            return {}
        if stats is None:
            return {}
        return {
            "name": self.VECTOR_INDEX_NAME,
            "num_indexed_rows": getattr(stats, "num_indexed_rows", None),
            "num_unindexed_rows": getattr(stats, "num_unindexed_rows", None),
            "index_type": getattr(stats, "index_type", None),
            "distance_type": getattr(stats, "distance_type", None),
            "num_indices": getattr(stats, "num_indices", None),
            "loss": getattr(stats, "loss", None),
        }

    def vector_index_ready(self) -> bool | None:
        """Whether the primary vector index has no unindexed tail."""
        stats = self.vector_index_stats()
        if not stats:
            return None
        unindexed = stats.get("num_unindexed_rows")
        if unindexed is None:
            return None
        return int(unindexed) == 0

    def create_vector_index(
        self,
        num_partitions: int | None = None,
        num_sub_vectors: int | None = None,
        *,
        index_type: str = "IVF_PQ",
        metric: str = "cosine",
        nprobes: int | None = 20,
        refine_factor: int | None = None,
        optimize: bool = True,
    ) -> dict:
        """Create a tuned vector index and optionally compact old fragments."""
        if self._table is None:
            return {"created": False, "reason": "table_missing"}
        rows = self.count()
        if rows < 10000:  # Not worth indexing below 10K
            self.configure_search(nprobes=nprobes, refine_factor=refine_factor)
            return {
                "created": False,
                "reason": "too_small",
                "rows": rows,
                "nprobes": nprobes,
                "refine_factor": refine_factor,
            }

        parts = num_partitions or max(1, int(math.sqrt(rows)))
        vector_dim = self._vector_dim()
        sub_vecs = num_sub_vectors or self._default_num_sub_vectors(vector_dim)
        result = {
            "created": False,
            "rows": rows,
            "index_type": index_type,
            "metric": metric,
            "num_partitions": parts,
            "num_sub_vectors": sub_vecs,
            "nprobes": nprobes,
            "refine_factor": refine_factor,
            "optimized": False,
            "indices": [],
        }

        try:
            self._table.create_index(
                index_type=index_type,
                metric=metric,
                num_partitions=parts,
                num_sub_vectors=sub_vecs,
                name=self.VECTOR_INDEX_NAME,
                replace=True,
            )
            if hasattr(self._table, "wait_for_index"):
                self._table.wait_for_index([self.VECTOR_INDEX_NAME], timeout=timedelta(minutes=10))
            result["created"] = True
            self.configure_search(nprobes=nprobes, refine_factor=refine_factor)
        except Exception as e:
            logger.warning("Vector index creation failed: %s", e)
            result["error"] = str(e)
            return result

        if optimize:
            result["optimized"] = self.optimize()

        result["indices"] = self.list_indices()
        result["index_stats"] = self.vector_index_stats()
        result["index_ready"] = self.vector_index_ready()
        return result

    def optimize(self) -> bool:
        """Compact data fragments and remove stale table versions when possible."""
        if self._table is not None:
            try:
                self._table.optimize(cleanup_older_than=timedelta(seconds=0))
                return True
            except Exception:
                pass
            optimized = False
            try:
                if hasattr(self._table, "compact_files"):
                    self._table.compact_files()
                    optimized = True
            except Exception:
                pass
            try:
                if hasattr(self._table, "cleanup_old_versions"):
                    self._table.cleanup_old_versions(timedelta(seconds=0))
                    optimized = True
            except Exception:
                pass
            return optimized
        return False

    def create_fts_index(self) -> None:
        """Create full-text search index on text column.

        LanceDB 0.30+ requires single-column FTS indexes.
        """
        if self._table is None:
            return
        try:
            self._table.create_fts_index("text", replace=True)
            logger.info("FTS index created on 'text' column")
        except Exception as e:
            logger.warning("FTS index creation failed: %s", e)

    def close(self) -> None:
        """No-op for LanceDB (embedded, no connection to close)."""
        pass

    def _vector_dim(self) -> int:
        """Best-effort vector dimensionality for the current table."""
        if self._table is None:
            return 768
        try:
            vector_field = self._table.schema.field("vector")
            list_size = getattr(vector_field.type, "list_size", None)
            if list_size:
                return int(list_size)
        except Exception:
            pass
        try:
            sample = self._table.search().select(["vector"]).limit(1).to_list()
            if sample and sample[0].get("vector"):
                return len(sample[0]["vector"])
        except Exception:
            pass
        return 768

    def _default_num_sub_vectors(self, vector_dim: int) -> int:
        """Choose a PQ subdivision that cleanly divides the vector dimension."""
        for candidate in (96, 64, 48, 32, 24, 16, 8, 4, 2, 1):
            if vector_dim % candidate == 0:
                return candidate
        return max(1, min(96, vector_dim))

    def _apply_search_tuning(
        self,
        builder,
        *,
        nprobes: int | None,
        refine_factor: int | None,
    ):
        """Apply nprobes/refine settings if the query builder supports them."""
        tuned_nprobes = nprobes if nprobes is not None else self._search_nprobes
        tuned_refine = (
            refine_factor if refine_factor is not None else self._search_refine_factor
        )
        if tuned_nprobes is not None and hasattr(builder, "nprobes"):
            builder = builder.nprobes(tuned_nprobes)
        if tuned_refine is not None and hasattr(builder, "refine_factor"):
            builder = builder.refine_factor(tuned_refine)
        return builder
