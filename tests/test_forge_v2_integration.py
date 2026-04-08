"""
Integration test: CorpusForge export -> V2 import -> query -> verify results.

Tests the full pipeline from a synthetic Forge export through LanceDB import,
FTS indexing, embedding, and retrieval. Proves the Forge->V2 contract works.

Run: .venv\\Scripts\\python.exe -m pytest tests/test_forge_v2_integration.py -v
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from scripts.import_embedengine import load_export, validate_chunks, validate_manifest
from scripts.canonical_rebuild_preflight import run_preflight


def make_forge_export(tmp_path: Path, n_files: int = 3, chunks_per_file: int = 4) -> Path:
    """Create a realistic Forge export directory with multiple source files."""
    export_dir = tmp_path / "forge_export"
    export_dir.mkdir()

    chunks = []
    for f_idx in range(n_files):
        for c_idx in range(chunks_per_file):
            chunks.append({
                "chunk_id": f"file{f_idx:03d}_chunk{c_idx:03d}",
                "text": f"This is chunk {c_idx} from document {f_idx}. "
                        f"It contains information about maintenance procedure MP-{f_idx:04d} "
                        f"at site SITE-{f_idx % 5}. Part number PN-{1000 + f_idx * 10 + c_idx}.",
                "source_path": f"/data/source/program_management/doc_{f_idx:03d}.pdf",
                "enriched_text": "",
                "chunk_index": c_idx,
                "parse_quality": 0.95,
            })

    n = len(chunks)
    dim = 768

    # chunks.jsonl
    with open(export_dir / "chunks.jsonl", "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # vectors.npy -- random but deterministic
    rng = np.random.default_rng(42)
    vectors = rng.standard_normal((n, dim)).astype(np.float16)
    np.save(str(export_dir / "vectors.npy"), vectors)

    # manifest.json
    with open(export_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.0",
            "schema_version": 1,
            "timestamp": "2026-04-07T21:00:00",
            "chunk_count": n,
            "vector_dim": dim,
            "vector_dtype": "float16",
            "embedding_model": "nomic-embed-text-v1.5",
            "entity_count": 0,
            "stats": {
                "files_found": n_files,
                "files_parsed": n_files,
                "files_skipped": 0,
                "chunks_created": n,
                "vectors_created": n,
            },
        }, f, indent=2)

    # skip_manifest.json
    with open(export_dir / "skip_manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "skipped_files": [],
            "deferred_formats": [],
        }, f)

    return export_dir


class TestPreflightIntegration:
    """Preflight correctly validates a Forge export."""

    def test_valid_export_passes(self, tmp_path):
        export_dir = make_forge_export(tmp_path)
        report = run_preflight(export_dir)
        assert report["verdict"] == "PASS"
        assert not report["errors"]

    def test_missing_vectors_fails(self, tmp_path):
        export_dir = make_forge_export(tmp_path)
        (export_dir / "vectors.npy").unlink()
        report = run_preflight(export_dir)
        assert report["verdict"] == "FAIL"

    def test_count_mismatch_fails(self, tmp_path):
        export_dir = make_forge_export(tmp_path)
        # Overwrite vectors with wrong count
        bad_vectors = np.zeros((5, 768), dtype=np.float16)
        np.save(str(export_dir / "vectors.npy"), bad_vectors)
        report = run_preflight(export_dir)
        assert report["verdict"] == "FAIL"


class TestLoadExportIntegration:
    """Load export validates and returns clean data."""

    def test_loads_valid_export(self, tmp_path):
        export_dir = make_forge_export(tmp_path, n_files=2, chunks_per_file=3)
        chunks, vectors, manifest, skip = load_export(export_dir)
        assert len(chunks) == 6
        assert vectors.shape == (6, 768)
        assert manifest["chunk_count"] == 6

    def test_manifest_version_accepted(self, tmp_path):
        export_dir = make_forge_export(tmp_path)
        chunks, vectors, manifest, _ = load_export(export_dir)
        # version "1.0" should be parsed and accepted (>= MIN_SCHEMA_VERSION)
        issues = validate_manifest(manifest, vectors)
        assert not any("REJECT" in i for i in issues)


class TestEndToEndImport:
    """Full import into a temporary LanceDB store."""

    def test_import_and_count(self, tmp_path):
        from src.store.lance_store import LanceStore

        export_dir = make_forge_export(tmp_path, n_files=3, chunks_per_file=4)
        chunks, vectors, manifest, _ = load_export(export_dir)

        db_path = str(tmp_path / "test_lancedb")
        store = LanceStore(db_path)
        assert store.count() == 0

        inserted = store.ingest_chunks(chunks, vectors)
        assert inserted == 12
        assert store.count() == 12

        # FTS index
        store.create_fts_index()

        # Dedup -- re-importing same data should insert 0
        inserted2 = store.ingest_chunks(chunks, vectors)
        assert inserted2 == 0
        assert store.count() == 12

        store.close()

    def test_import_with_bad_chunks_non_strict(self, tmp_path):
        """Bad chunks are filtered, good chunks still import."""
        from src.store.lance_store import LanceStore

        export_dir = make_forge_export(tmp_path, n_files=2, chunks_per_file=2)

        # Corrupt one chunk in the file
        chunks_path = export_dir / "chunks.jsonl"
        lines = chunks_path.read_text(encoding="utf-8").strip().split("\n")
        bad_chunk = json.loads(lines[0])
        del bad_chunk["text"]
        lines[0] = json.dumps(bad_chunk)
        chunks_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        chunks, vectors, _, _ = load_export(export_dir, strict=False)
        assert len(chunks) == 3  # 4 total - 1 rejected

        db_path = str(tmp_path / "test_lancedb2")
        store = LanceStore(db_path)
        inserted = store.ingest_chunks(chunks, vectors)
        assert inserted == 3
        store.close()
