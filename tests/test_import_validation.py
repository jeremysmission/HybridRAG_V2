"""
Integration test skeleton: CorpusForge export → V2 import → query → verify.

These tests validate the import_embedengine.py hardening:
- Required field validation (chunk_id, text, source_path)
- Manifest schema version gate
- Vector dimension cross-check
- Strict mode rejection
- Skip manifest reporting

Run: .venv\\Scripts\\python.exe -m pytest tests/test_import_validation.py -v
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_embedengine import (
    REQUIRED_CHUNK_FIELDS,
    validate_chunks,
    validate_manifest,
    load_export,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_export_dir(
    tmp_path: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict | None = None,
    skip_manifest: dict | None = None,
) -> Path:
    """Write a minimal CorpusForge export directory for testing."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # chunks.jsonl
    with open(export_dir / "chunks.jsonl", "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # vectors.npy
    np.save(str(export_dir / "vectors.npy"), vectors)

    # manifest.json
    if manifest is not None:
        with open(export_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

    # skip_manifest.json
    if skip_manifest is not None:
        with open(export_dir / "skip_manifest.json", "w", encoding="utf-8") as f:
            json.dump(skip_manifest, f)

    return export_dir


def make_valid_chunks(n: int = 5, dim: int = 768) -> tuple[list[dict], np.ndarray]:
    """Generate n valid chunk dicts and matching vectors."""
    chunks = [
        {
            "chunk_id": f"chunk_{i:04d}",
            "text": f"Sample text for chunk {i}.",
            "source_path": f"/data/source/doc_{i}.pdf",
            "chunk_index": i,
            "parse_quality": 0.95,
        }
        for i in range(n)
    ]
    vectors = np.random.randn(n, dim).astype(np.float16)
    return chunks, vectors


# ---------------------------------------------------------------------------
# validate_chunks tests
# ---------------------------------------------------------------------------


class TestValidateChunks:
    def test_all_valid(self):
        chunks, _ = make_valid_chunks(3)
        valid, rejected = validate_chunks(chunks)
        assert len(valid) == 3
        assert len(rejected) == 0

    def test_missing_chunk_id(self):
        chunks, _ = make_valid_chunks(2)
        chunks[1].pop("chunk_id")
        valid, rejected = validate_chunks(chunks)
        assert len(valid) == 1
        assert len(rejected) == 1
        assert "chunk_id" in rejected[0]["missing"]

    def test_missing_text(self):
        chunks, _ = make_valid_chunks(2)
        chunks[0]["text"] = ""
        valid, rejected = validate_chunks(chunks)
        assert len(valid) == 1
        assert len(rejected) == 1
        assert "text" in rejected[0]["missing"]

    def test_missing_source_path(self):
        chunks, _ = make_valid_chunks(2)
        del chunks[0]["source_path"]
        valid, rejected = validate_chunks(chunks)
        assert len(valid) == 1
        assert len(rejected) == 1
        assert "source_path" in rejected[0]["missing"]

    def test_multiple_missing_fields(self):
        chunks = [{"chunk_index": 0}]
        valid, rejected = validate_chunks(chunks)
        assert len(valid) == 0
        assert len(rejected) == 1
        assert set(rejected[0]["missing"]) == set(REQUIRED_CHUNK_FIELDS)


# ---------------------------------------------------------------------------
# validate_manifest tests
# ---------------------------------------------------------------------------


class TestValidateManifest:
    def test_valid_manifest(self):
        vectors = np.zeros((10, 768), dtype=np.float16)
        manifest = {"schema_version": 1, "vector_dim": 768, "chunk_count": 10}
        issues = validate_manifest(manifest, vectors)
        assert len(issues) == 0

    def test_schema_version_too_low(self):
        vectors = np.zeros((10, 768), dtype=np.float16)
        manifest = {"schema_version": 0}
        issues = validate_manifest(manifest, vectors)
        assert any("REJECT" in i and "schema_version" in i for i in issues)

    def test_vector_dim_mismatch(self):
        vectors = np.zeros((10, 768), dtype=np.float16)
        manifest = {"vector_dim": 384}
        issues = validate_manifest(manifest, vectors)
        assert any("REJECT" in i and "vector_dim" in i for i in issues)

    def test_chunk_count_warning(self):
        vectors = np.zeros((10, 768), dtype=np.float16)
        manifest = {"chunk_count": 15}
        issues = validate_manifest(manifest, vectors)
        assert any("WARNING" in i for i in issues)

    def test_empty_manifest(self):
        vectors = np.zeros((10, 768), dtype=np.float16)
        issues = validate_manifest({}, vectors)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# load_export integration tests
# ---------------------------------------------------------------------------


class TestLoadExport:
    def test_valid_export(self, tmp_path):
        chunks, vectors = make_valid_chunks(5)
        export_dir = make_export_dir(
            tmp_path, chunks, vectors,
            manifest={"schema_version": 1, "vector_dim": 768, "chunk_count": 5},
        )
        loaded_chunks, loaded_vecs, manifest, skip = load_export(export_dir)
        assert len(loaded_chunks) == 5
        assert loaded_vecs.shape[0] == 5

    def test_rejects_bad_chunks_non_strict(self, tmp_path):
        chunks, vectors = make_valid_chunks(5)
        chunks[2].pop("text")  # corrupt one chunk
        export_dir = make_export_dir(
            tmp_path, chunks, vectors,
            manifest={"schema_version": 1, "vector_dim": 768},
        )
        loaded_chunks, loaded_vecs, _, _ = load_export(export_dir, strict=False)
        assert len(loaded_chunks) == 4
        assert loaded_vecs.shape[0] == 4
        assert (export_dir / "import_rejected_chunks.jsonl").exists()

    def test_strict_mode_aborts(self, tmp_path):
        chunks, vectors = make_valid_chunks(3)
        chunks[0]["chunk_id"] = ""  # empty = falsy
        export_dir = make_export_dir(
            tmp_path, chunks, vectors,
            manifest={"schema_version": 1, "vector_dim": 768},
        )
        with pytest.raises(SystemExit) as exc_info:
            load_export(export_dir, strict=True)
        assert exc_info.value.code == 1

    def test_manifest_rejection_aborts(self, tmp_path):
        chunks, vectors = make_valid_chunks(3)
        export_dir = make_export_dir(
            tmp_path, chunks, vectors,
            manifest={"schema_version": 0},  # below minimum
        )
        with pytest.raises(SystemExit):
            load_export(export_dir)

    def test_skip_manifest_loaded(self, tmp_path):
        chunks, vectors = make_valid_chunks(3)
        skip = {
            "skipped_files": [
                {"path": "/data/drawing.dwg", "reason": "unsupported_format"},
            ],
            "deferred_formats": [
                {"extension": "dwg", "count": 42},
            ],
        }
        export_dir = make_export_dir(
            tmp_path, chunks, vectors,
            manifest={"schema_version": 1, "vector_dim": 768},
            skip_manifest=skip,
        )
        _, _, _, loaded_skip = load_export(export_dir)
        assert loaded_skip is not None
        assert len(loaded_skip["skipped_files"]) == 1
        assert loaded_skip["deferred_formats"][0]["extension"] == "dwg"
