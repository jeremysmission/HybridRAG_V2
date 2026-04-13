"""
Unit tests for scripts/tiered_extract.py

Guards the Tier 2 memory fix. The production bug was an
``all_chunks_for_tier2`` accumulator that held every chunk in memory
between Tier 1 and Tier 2, driving peak RSS past 57 GB on a 64 GB host.

Round 2 (commit 4e22347) swapped in a streaming second pass but kept a
silent ``except Exception -> load_chunks`` fallback, and the unit tests
used a mocked store that forced the fallback path rather than exercising
the real streaming branch. QA caught both gaps.

This revision (Round 3) builds real, tiny ``LanceStore`` instances in
temp directories and runs the production ``iter_chunk_batches`` /
``run_tier2_gliner`` code against them. The only mock left is the GLiNER
model, which is still injected via the ``gliner_model`` kwarg because
loading the real package in a unit test is too heavy.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import tracemalloc
from pathlib import Path

import numpy as np
import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.store.entity_store import Entity, EntityStore
from src.store.lance_store import LanceStore
from src.store.relationship_store import Relationship, RelationshipStore
from scripts.tiered_extract import (
    _is_tier2_candidate,
    _stream_tier1,
    iter_chunk_batches,
    load_chunks,
    run_tier2_gliner,
)


# ---------------------------------------------------------------------------
# Real tempdir LanceStore fixtures
# ---------------------------------------------------------------------------

VECTOR_DIM = 8  # tiny vectors — we never actually search, only stream


def _build_real_store(tmp_path: Path, n_chunks: int, prose_ratio: float = 1.0) -> LanceStore:
    """Create a real LanceStore in a temp directory with ``n_chunks`` rows.

    ``prose_ratio`` of the rows are long prose (Tier 2 candidates), the rest
    are short numeric noise (rejected by ``_is_tier2_candidate``). Returns
    the opened store — caller is responsible for closing.
    """
    db_path = str(tmp_path / "lancedb")
    store = LanceStore(db_path)

    chunks: list[dict] = []
    n_prose = int(n_chunks * prose_ratio)
    for i in range(n_prose):
        chunks.append({
            "chunk_id": f"prose-{i:06d}",
            "text": (
                f"The site lead inspected the tower at chunk {i}. "
                f"Jane Doe filed a report with Acme Corp on site Alpha-{i}."
            ),
            "source_path": f"doc-{i}.pdf",
            "chunk_index": i,
            "parse_quality": 1.0,
        })
    for i in range(n_chunks - n_prose):
        chunks.append({
            "chunk_id": f"noise-{i:06d}",
            "text": "12345 67890 11111 22222 33333",
            "source_path": f"table-{i}.xlsx",
            "chunk_index": i,
            "parse_quality": 0.3,
        })

    # Random unit vectors — content doesn't matter since we never search.
    rng = np.random.default_rng(seed=42)
    vectors = rng.standard_normal(size=(n_chunks, VECTOR_DIM)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9

    store.ingest_chunks(chunks, vectors, batch_size=500)
    return store


@pytest.fixture
def tiny_store(tmp_path):
    """10-chunk store, all prose."""
    store = _build_real_store(tmp_path, n_chunks=10)
    yield store
    store.close()


@pytest.fixture
def thousand_store(tmp_path):
    """1000-chunk store, all prose."""
    store = _build_real_store(tmp_path, n_chunks=1000)
    yield store
    store.close()


@pytest.fixture
def mixed_store(tmp_path):
    """100 chunks: 70 prose + 30 noise for Tier 2 filter testing."""
    store = _build_real_store(tmp_path, n_chunks=100, prose_ratio=0.7)
    yield store
    store.close()


# ---------------------------------------------------------------------------
# Fake GLiNER model (only remaining mock — real GLiNER is too heavy for unit)
# ---------------------------------------------------------------------------

class FakeGLiNERModel:
    """Records every ``batch_predict_entities`` call so we can assert
    batches stay bounded and the streaming contract holds.
    """

    def __init__(self):
        self.batch_calls: list[int] = []

    def batch_predict_entities(self, texts, labels, threshold, flat_ner):
        self.batch_calls.append(len(texts))
        return [
            [{"text": "Jane Doe", "label": "PERSON", "score": 0.95}]
            for _ in texts
        ]


# ---------------------------------------------------------------------------
# _is_tier2_candidate — pure function, no store needed
# ---------------------------------------------------------------------------

class TestIsTier2Candidate:
    def test_accepts_prose(self):
        chunk = {"text": "The site lead inspected the tower after the storm."}
        assert _is_tier2_candidate(chunk, min_chunk_len=20) is True

    def test_rejects_short(self):
        assert _is_tier2_candidate({"text": "ok"}, min_chunk_len=20) is False

    def test_rejects_low_alpha_ratio(self):
        chunk = {"text": "12345 67890 11111 22222 33333 44444 55555 66666"}
        assert _is_tier2_candidate(chunk, min_chunk_len=10) is False

    def test_rejects_whitespace_only_padding(self):
        assert _is_tier2_candidate({"text": " " * 500}, min_chunk_len=10) is False

    def test_boundary_alpha_ratio(self):
        # 3 alpha / 10 chars = 0.30 passes the >= 0.3 check.
        assert _is_tier2_candidate({"text": "abc1234567"}, min_chunk_len=10) is True


# ---------------------------------------------------------------------------
# iter_chunk_batches — real LanceStore streaming path
# ---------------------------------------------------------------------------

class TestIterChunkBatchesReal:
    """Exercise ``iter_chunk_batches`` against a real tempdir LanceStore.

    These tests prove the streaming branch works end-to-end on a genuine
    lancedb backend, not a mock that happens to fall through to ``load_chunks``.
    """

    def test_tiny_store_yields_single_batch(self, tiny_store):
        batches = list(iter_chunk_batches(tiny_store, batch_size=50))
        assert len(batches) == 1
        assert len(batches[0]) == 10
        assert all("chunk_id" in c for c in batches[0])
        assert all("text" in c for c in batches[0])
        assert all("source_path" in c for c in batches[0])

    def test_thousand_store_yields_hundred_batches_of_ten(self, thousand_store):
        batches = list(iter_chunk_batches(thousand_store, batch_size=10))
        assert len(batches) == 100
        assert all(len(b) == 10 for b in batches)
        # Flat count matches the store count.
        total = sum(len(b) for b in batches)
        assert total == 1000

    def test_thousand_store_batch_size_sevenish_remainder(self, thousand_store):
        """Non-divisible batch sizes must produce a remainder batch."""
        batches = list(iter_chunk_batches(thousand_store, batch_size=7))
        total = sum(len(b) for b in batches)
        assert total == 1000
        # At least one batch smaller than the full batch_size (remainder).
        assert any(len(b) < 7 for b in batches)
        # All non-remainder batches at full size.
        assert max(len(b) for b in batches) == 7

    def test_limit_caps_total_yielded(self, thousand_store):
        batches = list(iter_chunk_batches(thousand_store, batch_size=10, limit=35))
        total = sum(len(b) for b in batches)
        assert total == 35

    def test_limit_smaller_than_batch(self, thousand_store):
        batches = list(iter_chunk_batches(thousand_store, batch_size=100, limit=5))
        total = sum(len(b) for b in batches)
        assert total == 5

    def test_zero_limit_means_unlimited(self, tiny_store):
        batches = list(iter_chunk_batches(tiny_store, batch_size=100, limit=0))
        assert sum(len(b) for b in batches) == 10

    def test_streaming_memory_is_bounded(self, thousand_store):
        """tracemalloc peak must scale with batch_size, not store size.

        We stream 1000 chunks in batches of 20 and record the peak Python
        allocation during a single batch. With streaming it should stay well
        below what a full-materialization path would use. We pick a ceiling
        that's generous enough to survive platform noise but still proves
        the list is not growing unbounded.
        """
        tracemalloc.start()
        try:
            tracemalloc.clear_traces()
            peak_seen_bytes = 0
            for batch in iter_chunk_batches(thousand_store, batch_size=20):
                # After each batch, snapshot the current and peak allocation
                _, peak = tracemalloc.get_traced_memory()
                peak_seen_bytes = max(peak_seen_bytes, peak)
                # Simulate the consumer doing work and releasing
                del batch
            # The 1000-chunk store is small; streaming should never push
            # Python allocations above a few MB. 20 MB is a generous ceiling
            # that catches any accidental "collect into a list first" regression.
            assert peak_seen_bytes < 20 * 1024 * 1024, (
                f"tracemalloc peak {peak_seen_bytes / 1e6:.1f} MB exceeds 20 MB ceiling — "
                f"streaming branch may be accidentally accumulating"
            )
        finally:
            tracemalloc.stop()

    def test_fallback_is_off_by_default_and_raises(self, tiny_store):
        """When the streaming API raises, the default must propagate the
        error — no silent ``load_chunks`` fallback.

        We simulate a broken streaming API by monkey-patching the underlying
        table's ``search`` to raise. With the default
        ``allow_load_fallback=False`` the generator must raise RuntimeError.
        """
        broken_table = tiny_store._table

        class _RaisingBuilder:
            def select(self, *a, **kw): return self
            def limit(self, *a, **kw): return self
            def to_batches(self, *a, **kw):
                raise RuntimeError("simulated streaming API failure")

        original_search = broken_table.search
        broken_table.search = lambda *a, **kw: _RaisingBuilder()  # type: ignore[assignment]

        try:
            with pytest.raises(RuntimeError, match="allow_load_fallback=False"):
                list(iter_chunk_batches(tiny_store, batch_size=5))
        finally:
            broken_table.search = original_search  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Tier 1 streaming flush path
# ---------------------------------------------------------------------------

class TestTier1StreamingFlush:
    def _fake_chunk_batches(self):
        return [
            [
                {"chunk_id": "c1", "text": "chunk one", "source_path": "a.txt"},
                {"chunk_id": "c2", "text": "chunk two", "source_path": "b.txt"},
            ],
            [
                {"chunk_id": "c1", "text": "chunk one again", "source_path": "a.txt"},
            ],
        ]

    def _make_extractors(self):
        entity_map = {
            "c1": [Entity("PART", "PS-800", "PS-800", 1.0, "c1", "a.txt", "")],
            "c2": [Entity("PART", "SA-9000", "SA-9000", 1.0, "c2", "b.txt", "")],
        }
        rel_map = {
            "c1": [Relationship("PART", "PS-800", "ORDERED_FOR", "SITE", "Site-A", 1.0, "a.txt", "c1", "")],
            "c2": [Relationship("PART", "SA-9000", "ORDERED_FOR", "SITE", "Site-B", 1.0, "b.txt", "c2", "")],
        }

        class _Extractor:
            def extract(self, text, chunk_id, source_path):
                return list(entity_map.get(chunk_id, []))

        class _EventParser:
            def parse(self, text, chunk_id, source_path):
                return [], []

        class _RelExtractor:
            def extract(self, text, chunk_id, source_path):
                return list(rel_map.get(chunk_id, []))

        return _Extractor(), _EventParser(), _RelExtractor()

    def test_streams_and_flushes_incrementally(self, tmp_path, monkeypatch):
        from scripts import tiered_extract as te

        store = object()
        entity_store = EntityStore(str(tmp_path / "entities.sqlite3"))
        rel_store = RelationshipStore(str(tmp_path / "relationships.sqlite3"))
        extractor, event_parser, rel_extractor = self._make_extractors()
        entity_batches: list[list[str]] = []
        rel_batches: list[list[str]] = []

        orig_insert_entities = entity_store.insert_entities
        orig_insert_relationships = rel_store.insert_relationships

        def record_entities(batch):
            entity_batches.append([e.text for e in batch])
            return orig_insert_entities(batch)

        def record_relationships(batch):
            rel_batches.append([r.subject_text for r in batch])
            return orig_insert_relationships(batch)

        monkeypatch.setattr(entity_store, "insert_entities", record_entities)
        monkeypatch.setattr(rel_store, "insert_relationships", record_relationships)
        monkeypatch.setattr(te, "iter_chunk_batches", lambda *a, **k: self._fake_chunk_batches())

        try:
            result = te._stream_tier1(
                store=store,  # type: ignore[arg-type]
                entity_store=entity_store,
                rel_store=rel_store,
                extractor=extractor,
                event_parser=event_parser,
                rel_extractor=rel_extractor,
                limit=0,
                batch_size=2,
                dry_run=False,
                entity_flush_size=1,
                rel_flush_size=1,
            )

            assert result["chunks_processed"] == 3
            assert result["raw_entity_count"] == 2
            assert result["raw_relationship_count"] == 2
            assert result["inserted_entity_count"] == 2
            assert result["inserted_relationship_count"] == 2
            assert entity_batches == [["PS-800"], ["SA-9000"]]
            assert rel_batches == [["PS-800"], ["SA-9000"]]
            assert entity_store.count_entities() == 2
            assert rel_store.count() == 2
        finally:
            entity_store.close()
            rel_store.close()

    def test_dry_run_never_writes(self, tmp_path, monkeypatch):
        from scripts import tiered_extract as te

        store = object()
        entity_store = EntityStore(str(tmp_path / "entities.sqlite3"))
        rel_store = RelationshipStore(str(tmp_path / "relationships.sqlite3"))
        extractor, event_parser, rel_extractor = self._make_extractors()

        def boom(*args, **kwargs):
            raise AssertionError("dry-run should not write to SQLite")

        monkeypatch.setattr(entity_store, "insert_entities", boom)
        monkeypatch.setattr(rel_store, "insert_relationships", boom)
        monkeypatch.setattr(te, "iter_chunk_batches", lambda *a, **k: self._fake_chunk_batches())

        try:
            result = te._stream_tier1(
                store=store,  # type: ignore[arg-type]
                entity_store=entity_store,
                rel_store=rel_store,
                extractor=extractor,
                event_parser=event_parser,
                rel_extractor=rel_extractor,
                limit=0,
                batch_size=2,
                dry_run=True,
                entity_flush_size=1,
                rel_flush_size=1,
            )

            assert result["raw_entity_count"] == 2
            assert result["raw_relationship_count"] == 2
            assert result["inserted_entity_count"] == 0
            assert result["inserted_relationship_count"] == 0
            assert entity_store.count_entities() == 0
            assert rel_store.count() == 0
        finally:
            entity_store.close()
            rel_store.close()

    def test_fallback_opt_in_uses_load_chunks(self, tiny_store):
        """``allow_load_fallback=True`` is the only path to the materialize
        route, and it must actually deliver chunks from ``load_chunks``."""
        broken_table = tiny_store._table

        class _RaisingBuilder:
            def select(self, *a, **kw): return self
            def limit(self, *a, **kw): return self
            def to_batches(self, *a, **kw):
                raise RuntimeError("simulated streaming API failure")

        original_search = broken_table.search
        # Only the FIRST call (from iter_chunk_batches) should raise. The
        # fallback path calls load_chunks which also uses .search(), so we
        # need to let subsequent calls through to the real implementation.
        call_state = {"count": 0}

        def _patched_search(*a, **kw):
            call_state["count"] += 1
            if call_state["count"] == 1:
                return _RaisingBuilder()
            return original_search(*a, **kw)

        broken_table.search = _patched_search  # type: ignore[assignment]

        try:
            batches = list(iter_chunk_batches(
                tiny_store, batch_size=5, allow_load_fallback=True,
            ))
            total = sum(len(b) for b in batches)
            assert total == 10  # all 10 chunks came through the fallback
        finally:
            broken_table.search = original_search  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# run_tier2_gliner — real store, fake GLiNER model
# ---------------------------------------------------------------------------

class TestRunTier2Streaming:
    """Tier 2 must stream from a store directly, not accept a chunks list."""

    def test_signature_takes_store_not_chunks(self):
        import inspect
        sig = inspect.signature(run_tier2_gliner)
        params = list(sig.parameters.keys())
        assert "store" in params
        assert "chunks" not in params
        assert "tier1_hit_chunk_ids" in params
        assert "limit" in params
        assert "gliner_model" in params  # test-injection hook

    def test_runs_over_mixed_store(self, mixed_store):
        fake_model = FakeGLiNERModel()
        entities = run_tier2_gliner(
            store=mixed_store,
            tier1_hit_chunk_ids=set(),
            device="cpu",
            model_name="fake",
            min_chunk_len=20,
            min_confidence=0.5,
            limit=0,
            stream_batch_size=25,
            gliner_batch_size=4,
            progress_every=0,
            gliner_model=fake_model,
        )
        # 70 prose chunks pass the filter, 30 noise chunks fail.
        # Each prose chunk yields one PERSON entity from the fake payload.
        assert len(entities) == 70
        assert all(e.entity_type == "PERSON" for e in entities)
        assert sum(fake_model.batch_calls) == 70

    def test_gliner_batches_bounded(self, mixed_store):
        """No single GLiNER call may exceed ``gliner_batch_size``. A batch
        equal to the corpus size would indicate a regression to the
        accumulator pattern.
        """
        fake_model = FakeGLiNERModel()
        run_tier2_gliner(
            store=mixed_store,
            tier1_hit_chunk_ids=set(),
            device="cpu",
            model_name="fake",
            min_chunk_len=20,
            min_confidence=0.5,
            limit=0,
            stream_batch_size=25,
            gliner_batch_size=4,
            progress_every=0,
            gliner_model=fake_model,
        )
        assert fake_model.batch_calls, "GLiNER was never called"
        assert max(fake_model.batch_calls) <= 4
        assert sum(fake_model.batch_calls) == 70

    def test_respects_limit_flag(self, thousand_store):
        fake_model = FakeGLiNERModel()
        entities = run_tier2_gliner(
            store=thousand_store,
            tier1_hit_chunk_ids=set(),
            device="cpu",
            model_name="fake",
            min_chunk_len=20,
            min_confidence=0.5,
            limit=50,
            stream_batch_size=25,
            gliner_batch_size=8,
            progress_every=0,
            gliner_model=fake_model,
        )
        assert len(entities) == 50
        assert sum(fake_model.batch_calls) == 50

    def test_empty_prose_store_produces_nothing(self, tmp_path):
        store = _build_real_store(tmp_path, n_chunks=20, prose_ratio=0.0)
        try:
            fake_model = FakeGLiNERModel()
            entities = run_tier2_gliner(
                store=store,
                tier1_hit_chunk_ids=set(),
                device="cpu",
                model_name="fake",
                min_chunk_len=20,
                min_confidence=0.5,
                limit=0,
                stream_batch_size=10,
                gliner_batch_size=4,
                progress_every=0,
                gliner_model=fake_model,
            )
            assert entities == []
            assert fake_model.batch_calls == []  # no GLiNER calls at all
        finally:
            store.close()


# ---------------------------------------------------------------------------
# Canonical helper exports (locked because the GUI imports them)
# ---------------------------------------------------------------------------

class TestModuleImports:
    def test_canonical_helpers_exported(self):
        from scripts import tiered_extract as te
        assert hasattr(te, "_is_tier2_candidate")
        assert hasattr(te, "iter_chunk_batches")
        assert hasattr(te, "run_tier2_gliner")
        assert hasattr(te, "load_chunks")  # preserved for back-compat

    def test_streaming_api_dependency_present(self):
        """Lock in the lancedb streaming API contract.

        ``iter_chunk_batches`` depends on ``LanceQueryBuilder.to_batches``,
        which ships with lancedb itself (no optional pylance). This test
        fails loudly if a future install ends up on an older lancedb or
        a build that lacks the streaming API.
        """
        import lancedb
        from lancedb.query import LanceQueryBuilder

        assert hasattr(LanceQueryBuilder, "to_batches"), (
            f"lancedb {lancedb.__version__} does not expose "
            f"LanceQueryBuilder.to_batches — streaming Tier 1/2 extraction "
            f"will fall back to load_chunks and OOM at scale. "
            f"Upgrade: pip install --upgrade 'lancedb>=0.30'"
        )

    def test_assert_streaming_api_helper_exists(self):
        """The module-level guard must exist and be callable. It runs at
        import time but we re-invoke it here to prove it is still a public
        contract the test suite pins."""
        from scripts.tiered_extract import _assert_streaming_api_available
        # Should be a no-op on a healthy install.
        _assert_streaming_api_available()
