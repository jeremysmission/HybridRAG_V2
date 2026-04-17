"""Test module for the stage forge import behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np

from scripts.stage_forge_import import (
    build_canary_export,
    compute_delta,
    run_tier1_extraction,
    select_latest_export,
)


def _write_min_export(export_dir: Path, chunk_count: int = 4, dim: int = 8) -> tuple[list[dict], np.ndarray]:
    """Support this test module by handling the write min export step."""
    export_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    for i in range(chunk_count):
        chunks.append(
            {
                "chunk_id": f"c{i:03d}",
                "text": f"text {i}",
                "source_path": f"/data/doc_{i // 2}.txt",
            }
        )

    vectors = np.arange(chunk_count * dim, dtype=np.float16).reshape(chunk_count, dim)

    with open(export_dir / "chunks.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    np.save(str(export_dir / "vectors.npy"), vectors)
    with open(export_dir / "manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"schema_version": 1, "chunk_count": chunk_count, "vector_dim": dim}, f)
    return chunks, vectors


def test_select_latest_export_uses_deterministic_tie_break(tmp_path: Path):
    """Verify that select latest export uses deterministic tie break behaves the way the team expects."""
    root = tmp_path / "exports"
    a = root / "export_alpha"
    b = root / "export_bravo"
    _write_min_export(a)
    _write_min_export(b)

    fixed_ts = 1_700_000_000
    os.utime(a, (fixed_ts, fixed_ts))
    os.utime(b, (fixed_ts, fixed_ts))

    selected, candidates = select_latest_export(root)
    assert selected == b
    assert candidates[0]["path"] == str(b)
    assert candidates[1]["path"] == str(a)


def test_build_canary_export_writes_subset_and_manifest(tmp_path: Path):
    """Verify that build canary export writes subset and manifest behaves the way the team expects."""
    parent = tmp_path / "export_parent"
    chunks, vectors = _write_min_export(parent, chunk_count=5, dim=6)

    canary_dir = tmp_path / "stage" / "canary_export"
    manifest = {"schema_version": 1, "chunk_count": 5, "vector_dim": 6}
    skip_manifest = {"skipped_files": [], "deferred_formats": []}
    out_dir, canary_chunks, canary_vectors, canary_manifest, _ = build_canary_export(
        parent,
        chunks,
        vectors,
        manifest,
        skip_manifest,
        canary_dir,
        chunk_limit=3,
    )

    assert out_dir == canary_dir
    assert len(canary_chunks) == 3
    assert canary_vectors.shape == (3, 6)
    assert np.array_equal(canary_vectors, vectors[:3])
    assert canary_manifest["canary_mode"] is True
    assert canary_manifest["chunk_count"] == 3
    assert (canary_dir / "chunks.jsonl").exists()
    assert (canary_dir / "vectors.npy").exists()
    assert (canary_dir / "manifest.json").exists()
    assert (canary_dir / "skip_manifest.json").exists()


def test_compute_delta_baseline():
    """Verify that compute delta baseline behaves the way the team expects."""
    current = {
        "export_dir": "C:/exports/export_1",
        "chunk_count": 100,
        "source_file_count": 20,
        "vector_dim": 768,
        "embedding_model": "nomic",
    }
    delta = compute_delta(None, current)
    assert delta["baseline"] is True
    assert delta["current_export_dir"] == "C:/exports/export_1"


def test_compute_delta_detects_count_and_model_changes():
    """Verify that compute delta detects count and model changes behaves the way the team expects."""
    previous = {
        "export_dir": "C:/exports/export_prev",
        "chunk_count": 90,
        "source_file_count": 18,
        "vector_dim": 768,
        "embedding_model": "model_a",
    }
    current = {
        "export_dir": "C:/exports/export_cur",
        "chunk_count": 110,
        "source_file_count": 23,
        "vector_dim": 1024,
        "embedding_model": "model_b",
    }
    delta = compute_delta(previous, current)
    assert delta["baseline"] is False
    assert delta["chunk_count_delta"] == 20
    assert delta["source_files_delta"] == 5
    assert delta["vector_dim_changed"] is True
    assert delta["embedding_model_changed"] is True


def test_run_tier1_extraction_invokes_tiered_extract(monkeypatch):
    """Verify staged import shells into Tier 1 extraction after a successful import."""
    calls: list[dict] = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(
            {
                "cmd": cmd,
                "cwd": cwd,
                "text": text,
                "capture_output": capture_output,
                "check": check,
            }
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("scripts.stage_forge_import.subprocess.run", fake_run)

    result = run_tier1_extraction("config/config.yaml", limit=100)

    assert result["returncode"] == 0
    assert result["stdout"] == "ok"
    assert calls
    assert calls[0]["cmd"][-6:] == ["--tier", "1", "--config", "config/config.yaml", "--limit", "100"]
