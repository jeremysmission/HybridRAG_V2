"""
Unit tests for scripts/tiered_extract.py

Focus: the streaming contract between Tier 1 and Tier 2. The production
bug we are guarding against was an all_chunks_for_tier2 accumulator that
held the entire corpus in memory between Tier 1 and Tier 2, which drove
peak RAM past 57 GB on a 64 GB laptop during testing.

These tests do NOT require a real LanceDB store or GLiNER. Everything
streams through fake objects that mimic the store / model contract the
production code uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from scripts.tiered_extract import (
    _is_tier2_candidate,
    run_tier2_gliner,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeLanceStore:
    """Minimal stand-in for LanceStore used by iter_chunk_batches.

    iter_chunk_batches reaches for ``store._table.to_lance().scanner(...)``.
    When that raises, it falls back to ``load_chunks(store, limit=...)``.
    We make the scanner path raise so the fallback drives the test —
    the fallback uses ``tbl.search().select(columns).limit(n).to_arrow()``.
    """

    def __init__(self, chunks: list[dict]):
        self._chunks = list(chunks)
        self._table = _FakeTable(self._chunks)
        # count() is called by load_chunks to decide how many rows to pull.
        self._count = len(chunks)

    def count(self) -> int:
        return self._count

    def close(self) -> None:
        pass


class _FakeTable:
    def __init__(self, chunks: list[dict]):
        self._chunks = chunks
        # Counter: how many times search()/to_arrow() has been called.
        # Used to assert Tier 2 actually makes a SECOND pass over the store.
        self.scan_calls = 0

    def to_lance(self):
        # Force the iter_chunk_batches fallback. The real LanceDB scanner
        # path would require a real dataset, which we don't want to set up.
        raise RuntimeError("fake store forces fallback path")

    def search(self):
        return _FakeSearchBuilder(self)


class _FakeSearchBuilder:
    def __init__(self, table: _FakeTable):
        self._table = table
        self._limit = None

    def select(self, columns):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def to_arrow(self):
        self._table.scan_calls += 1
        chunks = self._table._chunks
        if self._limit is not None:
            chunks = chunks[: self._limit]
        return _FakeArrow(chunks)


class _FakeArrow:
    """Minimal pyarrow.Table shim — only the columns load_chunks reads."""

    def __init__(self, chunks: list[dict]):
        self._chunks = chunks
        self.num_rows = len(chunks)

    def column(self, name: str):
        return _FakeArrowColumn([c.get(name, "") for c in self._chunks])


class _FakeArrowColumn:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, i):
        return _FakeArrowCell(self._values[i])


class _FakeArrowCell:
    def __init__(self, v):
        self._v = v

    def __str__(self):
        return str(self._v)


class FakeGLiNERModel:
    """Fake GLiNER model that returns deterministic entities.

    Also records every batch_predict_entities call so the test can
    verify that pending batches are flushed at the expected cadence.
    """

    def __init__(self, per_text_entities=None):
        # Fixed payload per call; real GLiNER returns one list per input text.
        self._payload = per_text_entities or [
            {"text": "Jane Doe", "label": "PERSON", "score": 0.95}
        ]
        self.batch_calls: list[int] = []
        self.texts_seen: list[str] = []

    def batch_predict_entities(self, texts, labels, threshold, flat_ner):
        self.batch_calls.append(len(texts))
        self.texts_seen.extend(texts)
        return [list(self._payload) for _ in texts]


# ---------------------------------------------------------------------------
# _is_tier2_candidate
# ---------------------------------------------------------------------------

class TestIsTier2Candidate:
    def test_accepts_prose(self):
        chunk = {"text": "The site lead inspected the tower after the storm."}
        assert _is_tier2_candidate(chunk, min_chunk_len=20) is True

    def test_rejects_short(self):
        chunk = {"text": "ok"}
        assert _is_tier2_candidate(chunk, min_chunk_len=20) is False

    def test_rejects_low_alpha_ratio(self):
        # Mostly digits and symbols -- GLiNER has nothing to work with.
        chunk = {"text": "12345 67890 11111 22222 33333 44444 55555 66666"}
        assert _is_tier2_candidate(chunk, min_chunk_len=10) is False

    def test_rejects_whitespace_only_padding(self):
        chunk = {"text": " " * 500}
        assert _is_tier2_candidate(chunk, min_chunk_len=10) is False

    def test_boundary_alpha_ratio(self):
        # Exactly 30% alpha -- passes the >= 0.3 check.
        chunk = {"text": "abc1234567"}  # 3 alpha / 10 chars = 0.30
        assert _is_tier2_candidate(chunk, min_chunk_len=10) is True


# ---------------------------------------------------------------------------
# Streaming contract: run_tier2_gliner
# ---------------------------------------------------------------------------

class TestRunTier2Streaming:
    """The point of the redesign: Tier 2 re-streams the store instead of
    accepting a pre-loaded list of chunks. These tests lock that in."""

    def _make_store(self, n_prose: int, n_noise: int) -> FakeLanceStore:
        chunks = []
        for i in range(n_prose):
            chunks.append({
                "chunk_id": f"prose-{i}",
                "text": (
                    f"The site lead inspected the tower at chunk {i}. "
                    f"Jane Doe filed a report."
                ),
                "source_path": f"doc-{i}.pdf",
            })
        for i in range(n_noise):
            chunks.append({
                "chunk_id": f"noise-{i}",
                "text": "12345 " * 8,  # rejected by alpha-ratio filter
                "source_path": f"table-{i}.xlsx",
            })
        return FakeLanceStore(chunks)

    def test_signature_takes_store_not_chunks(self):
        """run_tier2_gliner must accept a store, not a list of chunks.

        The old signature took a `chunks: list[dict]` which was the
        memory bug. Lock in the new signature by calling with keyword args.
        """
        import inspect

        sig = inspect.signature(run_tier2_gliner)
        params = list(sig.parameters.keys())
        assert "store" in params
        assert "chunks" not in params
        assert "tier1_hit_chunk_ids" in params
        assert "limit" in params
        assert "gliner_model" in params  # test-injection hook

    def test_runs_over_streaming_store(self):
        store = self._make_store(n_prose=20, n_noise=10)
        fake_model = FakeGLiNERModel()

        entities = run_tier2_gliner(
            store=store,
            tier1_hit_chunk_ids=set(),
            device="cpu",  # ignored when gliner_model is injected
            model_name="fake",
            min_chunk_len=20,
            min_confidence=0.5,
            limit=0,
            stream_batch_size=5,
            gliner_batch_size=3,
            progress_every=0,
            gliner_model=fake_model,
        )

        # 20 prose chunks all pass the filter, 10 noise chunks all fail it.
        # Each prose chunk yields one PERSON entity (fake payload).
        assert len(entities) == 20
        assert all(e.entity_type == "PERSON" for e in entities)
        assert all(e.text == "Jane Doe" for e in entities)

        # Model was called in batches of up to gliner_batch_size=3.
        # 20 candidates / 3 per batch = 6 full batches of 3 + 1 remainder of 2
        assert sum(fake_model.batch_calls) == 20
        assert max(fake_model.batch_calls) <= 3
        assert any(n == 2 for n in fake_model.batch_calls), (
            f"expected a remainder batch, got {fake_model.batch_calls}"
        )

    def test_makes_a_second_pass_over_store(self):
        """Tier 2 must trigger its own store scan — the whole redesign.

        The store's FakeArrow.scan_calls counter starts at 0 when we build
        it, and Tier 2 calls must drive it above 0. If run_tier2_gliner
        ever goes back to accepting a pre-loaded list, this will fail.
        """
        store = self._make_store(n_prose=5, n_noise=5)
        assert store._table.scan_calls == 0

        fake_model = FakeGLiNERModel()
        run_tier2_gliner(
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

        assert store._table.scan_calls >= 1, (
            "Tier 2 did not re-scan the store — the streaming second-pass "
            "contract is broken"
        )

    def test_respects_limit_flag(self):
        """--limit must cap the Tier 2 scan so we can test on subsets."""
        store = self._make_store(n_prose=50, n_noise=0)
        fake_model = FakeGLiNERModel()

        entities = run_tier2_gliner(
            store=store,
            tier1_hit_chunk_ids=set(),
            device="cpu",
            model_name="fake",
            min_chunk_len=20,
            min_confidence=0.5,
            limit=15,
            stream_batch_size=10,
            gliner_batch_size=8,
            progress_every=0,
            gliner_model=fake_model,
        )

        # Only 15 chunks should have been processed by GLiNER.
        assert len(entities) == 15
        assert sum(fake_model.batch_calls) == 15

    def test_handles_empty_store(self):
        store = FakeLanceStore([])
        fake_model = FakeGLiNERModel()
        entities = run_tier2_gliner(
            store=store,
            tier1_hit_chunk_ids=set(),
            device="cpu",
            model_name="fake",
            min_chunk_len=20,
            min_confidence=0.5,
            limit=0,
            gliner_model=fake_model,
        )
        assert entities == []
        assert fake_model.batch_calls == []

    def test_no_candidates_means_no_gliner_calls(self):
        """A store of only filter-rejected chunks must not call GLiNER."""
        store = self._make_store(n_prose=0, n_noise=25)
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
        assert fake_model.batch_calls == []

    def test_accumulates_only_entities_not_chunks(self):
        """The fake model records batch sizes. If the production code ever
        held the full corpus before calling GLiNER, we'd see a single giant
        batch instead of multiple small ones. Verify batch sizes are bounded.
        """
        store = self._make_store(n_prose=100, n_noise=0)
        fake_model = FakeGLiNERModel()

        run_tier2_gliner(
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

        # Every batch must be <= gliner_batch_size. A batch equal to
        # n_prose would indicate the old accumulator pattern.
        assert all(n <= 4 for n in fake_model.batch_calls), (
            f"batch sizes exceeded gliner_batch_size=4: {fake_model.batch_calls}"
        )
        assert sum(fake_model.batch_calls) == 100


# ---------------------------------------------------------------------------
# Smoke test: the script's main() is still parseable
# ---------------------------------------------------------------------------

class TestModuleImports:
    def test_canonical_helpers_exported(self):
        """The GUI imports _is_tier2_candidate from scripts.tiered_extract.

        Changing the helper location would silently break the GUI, so this
        test pins it to the CLI module as the single source of truth.
        """
        from scripts import tiered_extract as te

        assert hasattr(te, "_is_tier2_candidate")
        assert hasattr(te, "iter_chunk_batches")
        assert hasattr(te, "run_tier2_gliner")
        assert hasattr(te, "load_chunks")  # preserved for backward compat
