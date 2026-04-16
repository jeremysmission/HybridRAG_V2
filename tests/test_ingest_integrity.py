"""
Tests for LanceStore.verify_ingest_completeness().

The laptop's LanceStore landed at exactly 10,000,000 chunks instead of
the canonical 10,435,593 and no V2 code path caught the 435K gap at
ingest time. These tests lock in the integrity helper that runs after
every ingest in both the CLI and GUI paths so the next silent
truncation surfaces immediately.

Uses real tempdir LanceStore instances (not mocks).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.store.lance_store import LanceStore, IngestIntegrityReport


VECTOR_DIM = 8


def _make_chunks(n: int, prefix: str = "chunk") -> tuple[list[dict], np.ndarray]:
    """Create a small test object so the scenario stays readable."""
    chunks = [
        {
            "chunk_id": f"{prefix}-{i:06d}",
            "text": f"Test chunk body for {prefix} row {i}.",
            "source_path": f"{prefix}/{i}.txt",
            "chunk_index": i,
            "parse_quality": 1.0,
        }
        for i in range(n)
    ]
    rng = np.random.default_rng(seed=17)
    vectors = rng.standard_normal(size=(n, VECTOR_DIM)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
    return chunks, vectors


# ---------------------------------------------------------------------------
# Clean ingest — every rule passes
# ---------------------------------------------------------------------------


class TestCleanIngest:
    """Small helper object used to keep test setup or expected results organized."""
    def test_fresh_store_ingest_passes(self, tmp_path):
        store = LanceStore(str(tmp_path / "lancedb"))
        chunks, vectors = _make_chunks(100)

        before = store.count()
        inserted = store.ingest_chunks(chunks, vectors)
        report = store.verify_ingest_completeness(
            attempted=len(chunks),
            before_count=before,
            inserted=inserted,
        )

        assert report.ok, f"expected clean ingest, got issues: {report.issues}"
        assert report.attempted == 100
        assert report.before_count == 0
        assert report.after_count == 100
        assert report.inserted == 100
        assert report.duplicates == 0
        assert report.net_delta == 100
        assert report.expected_delta == 100
        assert report.mismatch == 0
        assert report.issues == []
        store.close()

    def test_manifest_count_matches(self, tmp_path):
        store = LanceStore(str(tmp_path / "lancedb"))
        chunks, vectors = _make_chunks(42)

        inserted = store.ingest_chunks(chunks, vectors)
        report = store.verify_ingest_completeness(
            attempted=len(chunks),
            before_count=0,
            inserted=inserted,
            manifest_count=42,
        )

        assert report.ok
        assert report.manifest_count == 42
        store.close()

    def test_reingest_is_all_duplicates(self, tmp_path):
        """Second ingest of the same chunks is all duplicates, zero inserts,
        zero net delta — the identity ``inserted + duplicates == attempted``
        still holds and the report is clean."""
        store = LanceStore(str(tmp_path / "lancedb"))
        chunks, vectors = _make_chunks(30)

        # First ingest
        store.ingest_chunks(chunks, vectors)

        # Second ingest of the same chunks
        before2 = store.count()
        inserted2 = store.ingest_chunks(chunks, vectors)
        report = store.verify_ingest_completeness(
            attempted=len(chunks),
            before_count=before2,
            inserted=inserted2,
        )

        assert report.ok, report.issues
        assert report.inserted == 0
        assert report.duplicates == 30
        assert report.net_delta == 0
        store.close()


# ---------------------------------------------------------------------------
# Mismatch detection — the laptop-10M class of bug
# ---------------------------------------------------------------------------


class TestIntegrityMismatch:
    """Small helper object used to keep test setup or expected results organized."""
    def test_flags_net_delta_vs_expected_mismatch(self, tmp_path):
        """Simulate the laptop 10M: caller claims 10,435,593 inserted but
        the store only grew by 10,000,000. The helper must surface it."""
        store = LanceStore(str(tmp_path / "lancedb"))
        chunks, vectors = _make_chunks(50)
        store.ingest_chunks(chunks, vectors)
        # store now has 50 rows

        # Lie about how many were inserted: claim 100, but table only has 50.
        report = store.verify_ingest_completeness(
            attempted=100,
            before_count=0,
            inserted=100,
        )

        assert not report.ok
        assert any("INGEST INTEGRITY" in i for i in report.issues)
        assert any("does not match" in i for i in report.issues)
        assert report.mismatch == -50  # 50 actual - 100 claimed
        store.close()

    def test_flags_manifest_count_mismatch(self, tmp_path):
        """CorpusForge manifest says 10,435,593 but we only handed the
        ingest 10,000,000 chunks — upstream export is truncated."""
        store = LanceStore(str(tmp_path / "lancedb"))
        chunks, vectors = _make_chunks(20)
        inserted = store.ingest_chunks(chunks, vectors)

        report = store.verify_ingest_completeness(
            attempted=20,
            before_count=0,
            inserted=inserted,
            manifest_count=30,  # manifest promised 30, we got 20
        )

        assert not report.ok
        assert any("manifest.chunk_count" in i for i in report.issues)
        assert report.manifest_count == 30
        store.close()

    def test_flags_inserted_exceeds_attempted(self, tmp_path):
        """Rule 3: inserted > attempted is a caller counter bug.

        Cannot happen in practice (ingest_chunks caps at len(chunks))
        but if a future code path returns a mis-computed value, we
        want to surface it at the store boundary rather than trust
        the arithmetic downstream.
        """
        store = LanceStore(str(tmp_path / "lancedb"))
        chunks, vectors = _make_chunks(10)
        store.ingest_chunks(chunks, vectors)

        report = store.verify_ingest_completeness(
            attempted=5,   # claim 5 attempted
            before_count=0,
            inserted=10,   # but 10 inserted — impossible
        )
        assert not report.ok
        assert any("exceeds" in issue.lower() for issue in report.issues)
        store.close()

    def test_flags_negative_inserted(self, tmp_path):
        """Rule 3: negative inserted is an invalid caller value."""
        store = LanceStore(str(tmp_path / "lancedb"))

        report = store.verify_ingest_completeness(
            attempted=10,
            before_count=0,
            inserted=-3,
        )
        assert not report.ok
        assert any("negative" in issue.lower() for issue in report.issues)
        store.close()


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Structured test record that keeps one example easy to understand and reuse."""
    def test_empty_store_zero_attempted_is_clean(self, tmp_path):
        store = LanceStore(str(tmp_path / "lancedb"))
        # Empty store, empty ingest
        report = store.verify_ingest_completeness(
            attempted=0,
            before_count=0,
            inserted=0,
        )
        assert report.ok
        store.close()

    def test_report_is_serializable(self, tmp_path):
        """to_dict() must return something json.dumps-able so it can
        ride along in the import_report JSON artifact."""
        import json

        store = LanceStore(str(tmp_path / "lancedb"))
        chunks, vectors = _make_chunks(5)
        inserted = store.ingest_chunks(chunks, vectors)
        report = store.verify_ingest_completeness(
            attempted=5,
            before_count=0,
            inserted=inserted,
            manifest_count=5,
        )
        payload = report.to_dict()
        json.dumps(payload)  # must not raise
        assert payload["ok"] is True
        assert payload["attempted"] == 5
        assert "issues" in payload
        store.close()

    def test_report_dataclass_fields(self):
        """Lock in the IngestIntegrityReport field set so downstream
        consumers (import_report JSON readers, GUI stats panel) don't
        break when a field is renamed or removed."""
        expected_fields = {
            "attempted",
            "before_count",
            "after_count",
            "inserted",
            "duplicates",
            "net_delta",
            "expected_delta",
            "mismatch",
            "manifest_count",
            "issues",
        }
        actual = {f.name for f in IngestIntegrityReport.__dataclass_fields__.values()}
        assert actual == expected_fields
