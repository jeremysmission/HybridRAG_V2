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
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import lancedb
import numpy as np

from src.store.retrieval_metadata_store import (
    RetrievalMetadataStore,
    resolve_retrieval_metadata_db_path,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestIntegrityReport:
    """Structured result of verify_ingest_completeness().

    Populated after an ingest call so callers can surface mismatches as
    loud warnings or operator errors instead of silently trusting the
    post-ingest count.

    Fields
    ------
    attempted:
        ``len(chunks)`` passed to ``ingest_chunks``.
    before_count:
        ``store.count()`` observed before the ingest call.
    after_count:
        ``store.count()`` observed after the ingest call.
    inserted:
        Value returned by ``ingest_chunks`` (new rows it actually added).
    duplicates:
        ``attempted - inserted`` — chunks that were already present and
        got skipped by the dedup filter.
    net_delta:
        ``after_count - before_count`` — the table-level delta the store
        itself reports via ``count_rows()``.
    expected_delta:
        Value of ``inserted``. If ``net_delta != expected_delta`` the
        store did not actually absorb what the ingest function claimed
        to insert — that's the class of silent truncation the laptop
        10M incident exposed (see
        ``docs/LAPTOP_10M_INVESTIGATION_2026-04-11.md``).
    mismatch:
        ``net_delta - expected_delta``. Zero on a healthy ingest.
    manifest_count:
        Optional — the value of ``manifest.chunk_count`` from the
        CorpusForge export. When provided and ``attempted !=
        manifest_count`` the helper also flags the upstream source
        being smaller than the manifest promised.
    issues:
        List of human-readable warning / error strings. Empty list
        means the ingest passed every integrity check.
    """

    attempted: int
    before_count: int
    after_count: int
    inserted: int
    duplicates: int
    net_delta: int
    expected_delta: int
    mismatch: int
    manifest_count: int | None
    issues: list[str]

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict:
        return {
            "attempted": self.attempted,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "inserted": self.inserted,
            "duplicates": self.duplicates,
            "net_delta": self.net_delta,
            "expected_delta": self.expected_delta,
            "mismatch": self.mismatch,
            "manifest_count": self.manifest_count,
            "issues": list(self.issues),
            "ok": self.ok,
        }


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
        self.metadata_store = RetrievalMetadataStore(
            resolve_retrieval_metadata_db_path(self.db_path)
        )
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
            # Try hybrid search (vector + FTS) with LanceDB 0.30+ API
            if query_text.strip():
                try:
                    # Correct API: search(query_type="hybrid").vector(vec).text(text)
                    builder = (
                        self._table.search(query_type="hybrid")
                        .vector(vec)
                        .text(query_text)
                    )
                    builder = self._apply_search_tuning(
                        builder,
                        nprobes=nprobes,
                        refine_factor=refine_factor,
                    )
                    results = builder.limit(top_k).to_list()
                except Exception as e:
                    logger.warning("Hybrid search failed, falling back to vector-only: %s", e)
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
        except Exception as e:
            # Fallback: vector-only search
            logger.warning("Hybrid search outer failure, falling back to vector-only: %s", e)
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
                score=float(r.get("_relevance_score", r.get("_distance", 0.0))),
                chunk_index=r.get("chunk_index", 0),
                parse_quality=r.get("parse_quality", 1.0),
            )
            for r in results
        ]

    def metadata_path_search(
        self,
        path_terms: list[str],
        limit: int = 10,
        allow_tail_fallback: bool = True,
    ) -> list[ChunkResult]:
        """Return chunks whose ``source_path`` matches all supplied path terms.

        This is a narrow metadata-recall helper for path-heavy queries such as
        dated shipment folders and CDRL-coded deliverable lookups. It does not
        replace hybrid search; it supplements it when the evidence indicates the
        answer lives primarily in folder/file naming rather than chunk text.
        """
        if self._table is None or not path_terms:
            return []

        clauses = []
        for term in path_terms:
            normalized = (term or "").strip().lower()
            if not normalized:
                continue
            escaped = re.sub(r"['\\\\]", lambda m: f"\\{m.group(0)}", normalized)
            clauses.append(f"lower(source_path) LIKE '%{escaped}%'")

        if not clauses:
            return []

        where_clause = " AND ".join(clauses)
        desired = max(1, int(limit))
        merged: list[ChunkResult] = []
        seen_sources: set[str] = set()

        def _append_unique(rows: list[dict]) -> bool:
            for r in rows:
                source_path = r.get("source_path", "")
                if not source_path or source_path in seen_sources:
                    continue
                seen_sources.add(source_path)
                merged.append(
                    ChunkResult(
                        chunk_id=r.get("chunk_id", ""),
                        text=r.get("text", ""),
                        enriched_text=r.get("enriched_text") or None,
                        source_path=source_path,
                        score=-1.0,
                        chunk_index=r.get("chunk_index", 0),
                        parse_quality=r.get("parse_quality", 1.0),
                    )
                )
                if len(merged) >= desired:
                    return True
            return False

        try:
            # Prefer first chunks so metadata path recall surfaces distinct files
            # instead of many neighboring chunks from one workbook or PDF.
            head_rows = self._metadata_path_rows(
                f"{where_clause} AND chunk_index = 0",
                limit=max(desired * 4, 16),
            )
            if allow_tail_fallback and not _append_unique(head_rows):
                tail_rows = self._metadata_path_rows(
                    where_clause,
                    limit=max(desired * 8, 32),
                )
                _append_unique(tail_rows)
            else:
                _append_unique(head_rows)
        except Exception as e:
            logger.warning("Metadata path search failed for %s: %s", path_terms, e)
            return []

        return merged[:desired]

    def _metadata_path_rows(self, where_clause: str, limit: int) -> list[dict]:
        """Fetch raw metadata-search rows for a source-path filter."""
        return (
            self._table.search()
            .where(where_clause)
            .select([
                "chunk_id",
                "text",
                "enriched_text",
                "source_path",
                "chunk_index",
                "parse_quality",
            ])
            .limit(limit)
            .to_list()
        )

    def fetch_source_head_chunks(
        self,
        source_paths: list[str],
        limit: int = 10,
    ) -> list[ChunkResult]:
        """Fetch one representative chunk per exact source_path."""
        if self._table is None or not source_paths:
            return []

        desired = max(1, int(limit))
        results: list[ChunkResult] = []
        seen: set[str] = set()

        for source_path in source_paths:
            normalized = str(source_path or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            escaped = self._sql_quote(normalized)
            head_rows = self._metadata_path_rows(
                f"source_path = '{escaped}' AND chunk_index = 0",
                limit=1,
            )
            if not head_rows:
                head_rows = self._metadata_path_rows(
                    f"source_path = '{escaped}'",
                    limit=1,
                )
            for row in head_rows:
                results.append(
                    ChunkResult(
                        chunk_id=row.get("chunk_id", ""),
                        text=row.get("text", ""),
                        enriched_text=row.get("enriched_text") or None,
                        source_path=row.get("source_path", ""),
                        score=-2.0,
                        chunk_index=row.get("chunk_index", 0),
                        parse_quality=row.get("parse_quality", 1.0),
                    )
                )
                break
            if len(results) >= desired:
                break

        return results[:desired]

    def count(self) -> int:
        """Total chunks in the store."""
        if self._table is None:
            return 0
        try:
            return self._table.count_rows()
        except Exception:
            return 0

    def verify_ingest_completeness(
        self,
        attempted: int,
        before_count: int,
        inserted: int,
        manifest_count: int | None = None,
    ) -> IngestIntegrityReport:
        """Check that an ingest actually landed everything it claimed.

        This is the durable safety net added after the laptop 10M
        incident (2026-04-11): the laptop's LanceStore landed at exactly
        10,000,000 chunks despite being asked to ingest 10,435,593, and
        no code path in V2 currently catches that kind of silent
        truncation at ingest time. See
        ``docs/LAPTOP_10M_INVESTIGATION_2026-04-11.md`` for the full
        search and root-cause analysis.

        The check is cheap — a single ``count_rows()`` call — and runs
        in both the CLI (``scripts/import_embedengine.py``) and GUI
        (``scripts/import_extract_gui.py``) import paths so no walk-away
        run can land silently truncated.

        The helper does NOT raise. It returns an
        ``IngestIntegrityReport`` whose ``issues`` list names every
        mismatch it found. Callers are responsible for deciding whether
        to abort or continue — an operator-visible loud WARNING is the
        current policy; a future hard-fail mode may follow once we've
        confirmed there are no false positives in production.

        Integrity rules applied:

          - ``net_delta == expected_delta``
            Table row delta matches the ``inserted`` count the ingest
            function returned. Catches LanceDB fragment rollback,
            version-pointer regression, external process kill after
            an ``add()`` call but before the metadata commit, and disk
            full that silently drops the final commit.

          - ``manifest_count`` vs ``attempted`` (when manifest_count
            is supplied)
            The CorpusForge manifest promised N chunks, but the chunks
            list handed to ingest_chunks had M. That means the export
            file itself was truncated upstream of V2 — not a V2 bug,
            but the operator should know before they trust the store.

          - ``0 <= inserted <= attempted``
            Sanity check on the ingest-return value. A caller that
            reports ``inserted > attempted`` has a counter bug; a
            negative ``inserted`` means the caller handed us a broken
            return value and we should surface it rather than silently
            trusting the arithmetic downstream.
        """
        after_count = self.count()
        net_delta = after_count - before_count
        expected_delta = inserted
        mismatch = net_delta - expected_delta
        duplicates = attempted - inserted

        issues: list[str] = []

        # Rule 1: net_delta == expected_delta
        if mismatch != 0:
            issues.append(
                f"INGEST INTEGRITY: store count delta {net_delta:,} "
                f"does not match ingest-reported inserted {inserted:,} "
                f"(mismatch = {mismatch:+,}). "
                f"This is the class of silent truncation the laptop 10M "
                f"incident exposed — see "
                f"docs/LAPTOP_10M_INVESTIGATION_2026-04-11.md."
            )

        # Rule 2: manifest vs attempted
        if manifest_count is not None and manifest_count != attempted:
            issues.append(
                f"INGEST INTEGRITY: CorpusForge manifest.chunk_count="
                f"{manifest_count:,} but chunks list handed to ingest "
                f"had {attempted:,} entries "
                f"(delta = {attempted - manifest_count:+,}). "
                f"Upstream export may be truncated."
            )

        # Rule 3: 0 <= inserted <= attempted
        if inserted < 0:
            issues.append(
                f"INGEST INTEGRITY: inserted count is negative "
                f"({inserted}) — caller returned an invalid value."
            )
        if inserted > attempted:
            issues.append(
                f"INGEST INTEGRITY: inserted={inserted:,} exceeds "
                f"attempted={attempted:,}. Counter bug in caller."
            )

        return IngestIntegrityReport(
            attempted=attempted,
            before_count=before_count,
            after_count=after_count,
            inserted=inserted,
            duplicates=duplicates,
            net_delta=net_delta,
            expected_delta=expected_delta,
            mismatch=mismatch,
            manifest_count=manifest_count,
            issues=issues,
        )

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

    def has_fts_index(self) -> bool:
        """Whether the table currently exposes any FTS/inverted index metadata."""
        markers = ("fts", "inverted", "text_idx")
        for item in self.list_indices():
            lowered = str(item).lower()
            if any(marker in lowered for marker in markers):
                return True
        return False

    def fts_status(self) -> dict:
        """Best-effort readiness probe for the configured FTS path."""
        status = {
            "path": str(self.db_path),
            "table_present": self._table is not None,
            "index_present": False,
            "state": "missing",
            "probe_term": None,
            "probe_ok": False,
            "ready": False,
            "error": "",
        }
        if self._table is None:
            status["error"] = "chunks table missing"
            return status

        status["index_present"] = self.has_fts_index()
        probe_term = self._fts_probe_term()
        status["probe_term"] = probe_term
        try:
            self._table.search(probe_term, query_type="fts").limit(1).to_list()
            status["probe_ok"] = True
            status["ready"] = True
            status["state"] = "ready"
            return status
        except Exception as e:
            status["error"] = str(e)
            if status["index_present"]:
                status["state"] = "index_present"
            return status

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
        """Close any sidecar state. LanceDB itself is embedded/no-op."""
        try:
            self.metadata_store.close()
        except Exception:
            logger.debug("Failed closing retrieval metadata store", exc_info=True)

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

    def _fts_probe_term(self) -> str:
        """Return a safe token from the table for FTS health probing."""
        fallback = "maintenance"
        if self._table is None:
            return fallback
        try:
            sample_rows = self._table.search().select(["text"]).limit(3).to_list()
            for row in sample_rows:
                text = row.get("text", "")
                for token in re.findall(r"[A-Za-z0-9]{3,}", text):
                    return token.lower()
        except Exception:
            logger.debug("FTS probe-term derivation failed", exc_info=True)
        return fallback

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

    def _sql_quote(self, value: str) -> str:
        """Escape a string for use in a simple Lance where clause."""
        return str(value).replace("\\", "\\\\").replace("'", "''")
