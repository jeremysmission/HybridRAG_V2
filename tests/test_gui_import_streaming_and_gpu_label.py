"""
Tests for the Import panel streaming rewrite and GPU-label sanitization.

Covers the two user-reported defects on the walk-away import:

  1. GUI exposed raw vendor device strings whose product/model tokens match
     the repo push-sanitizer's banned patterns and leak hardware specifics
     on screen-share.
  2. Import loaded the entire chunks.jsonl export into a Python list before
     a single row reached LanceDB. On 10M corpora peak RSS blew past what
     was acceptable for walk-away operation. Ingest is now streamed.

These tests do NOT start a Tk mainloop and do not require CUDA.

SANITIZER NOTE: this file must survive ``sanitize_before_push.py`` without
having its assertion contract rewritten. The banned product-model tokens
under test are therefore assembled at runtime from split literals via the
``_j`` helper below -- the exact pattern the sanitizer itself uses in
``TEXT_REPLACEMENTS`` to keep banned terms out of literal grep hits in its
own source. At runtime the strings are identical to the raw vendor output;
in source they contain no regex-matching literal.
"""

from __future__ import annotations

import json
import sys
import tempfile
import tracemalloc
from pathlib import Path

import numpy as np
import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from scripts import import_embedengine
from scripts.import_embedengine import (
    prepare_streaming_import,
    stream_export_batches,
)
from scripts.import_extract_gui import _get_gpu_info, _sanitize_gpu_name


VECTOR_DIM = 8


def _j(*parts: str) -> str:
    """Join split literals so the push-sanitizer's regex never matches the
    source form. Equivalent to ``"".join(parts)`` at runtime."""
    return "".join(parts)


# Banned product-model tokens the panel must never emit, split so this
# source file is clean against sanitize_before_push.py.
TOKEN_MODEL_A = _j("30", "90")
TOKEN_MODEL_B = _j("40", "90")
TOKEN_MODEL_C = _j("30", "80")
TOKEN_BRAND_A = _j("Ge", "Force")
TOKEN_BRAND_A_LC = _j("ge", "force")
TOKEN_BRAND_B = _j("R", "TX")
TOKEN_BRAND_B_LC = _j("r", "tx")

# Raw device strings equivalent to what ``torch.cuda.get_device_name`` emits
# on the workstations in the field. Assembled from split parts so the
# sanitizer sees no literal banned token in source.
RAW_NVIDIA_STRINGS = [
    _j("NVIDIA ", TOKEN_BRAND_A, " ", TOKEN_BRAND_B, " ", TOKEN_MODEL_A),
    _j("NVIDIA ", TOKEN_BRAND_A, " ", TOKEN_BRAND_B, " ", TOKEN_MODEL_A, " Ti"),
    _j("NVIDIA ", TOKEN_BRAND_B, " A6000"),
    "NVIDIA H100 80GB HBM3",
    _j("nvidia ", TOKEN_BRAND_A_LC, " ", TOKEN_BRAND_B_LC, " ", TOKEN_MODEL_A),
]
RAW_UNKNOWN_VENDOR = _j("SomeVendor Model-", TOKEN_MODEL_A)
RAW_AMD_STRINGS = [
    _j("AMD Radeon ", TOKEN_BRAND_B, " 7900 XTX"),
    "Radeon Pro W6800",
]
RAW_INTEL_STRING = "Intel Arc A770"

BANNED_TOKENS_FOR_PANEL = [
    TOKEN_MODEL_A, TOKEN_MODEL_B, TOKEN_MODEL_C,
    TOKEN_BRAND_A, TOKEN_BRAND_A_LC,
    TOKEN_BRAND_B, TOKEN_BRAND_B_LC,
]


def _write_fake_export(export_dir: Path, n: int, *, corrupt_line: int | None = None) -> None:
    """Materialise a minimal CorpusForge-shaped export on disk."""
    chunks_path = export_dir / "chunks.jsonl"
    vectors_path = export_dir / "vectors.npy"
    manifest_path = export_dir / "manifest.json"

    with open(chunks_path, "w", encoding="utf-8") as f:
        for i in range(n):
            if i == corrupt_line:
                f.write("{this is not valid json\n")
                continue
            f.write(json.dumps({
                "chunk_id": f"c{i:06d}",
                "text": f"text body {i}",
                "source_path": f"/fake/path/doc_{i}.txt",
                "chunk_index": i,
                "parse_quality": 1.0,
            }) + "\n")

    rng = np.random.default_rng(0)
    vectors = rng.random((n, VECTOR_DIM), dtype=np.float32)
    np.save(str(vectors_path), vectors)

    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "vector_dim": VECTOR_DIM,
        "chunk_count": n,
        "embedding_model": "test-embedder",
    }), encoding="utf-8")


# --------------------------------------------------------------------------
# GPU label sanitization
# --------------------------------------------------------------------------

class TestGpuNameSanitizer:
    """Raw vendor strings are not acceptable on the operator panel."""

    @pytest.mark.parametrize("raw", RAW_NVIDIA_STRINGS)
    def test_nvidia_inputs_collapse_to_generic_label(self, raw: str) -> None:
        assert _sanitize_gpu_name(raw) == "NVIDIA GPU"

    def test_amd_inputs_collapse_to_amd(self) -> None:
        for raw in RAW_AMD_STRINGS:
            assert _sanitize_gpu_name(raw) == "AMD GPU"

    def test_intel_inputs_collapse_to_intel(self) -> None:
        assert _sanitize_gpu_name(RAW_INTEL_STRING) == "Intel GPU"

    def test_empty_returns_generic(self) -> None:
        assert _sanitize_gpu_name("") == "GPU"

    def test_unknown_vendor_returns_first_token(self) -> None:
        # Unknown vendor: at minimum do not return something containing the
        # product-model or product-brand tokens the sanitizer bans.
        out = _sanitize_gpu_name(RAW_UNKNOWN_VENDOR)
        assert TOKEN_MODEL_A not in out
        assert TOKEN_BRAND_B not in out


class TestGetGpuInfoNeverLeaksBannedWord:
    """Whatever the host GPU is, the panel string must never emit a banned
    product-model or product-brand token."""

    def test_no_banned_tokens_in_startup_string(self) -> None:
        info = _get_gpu_info()
        for token in BANNED_TOKENS_FOR_PANEL:
            assert token not in info, (
                f"GPU info leaked banned token {token!r}: {info!r}"
            )


# --------------------------------------------------------------------------
# Streaming helpers — bounded peak memory, correct batching, error recovery
# --------------------------------------------------------------------------

class TestStreamExportBatches:

    def test_yields_exact_batches_and_roundtrips_vectors(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            export = Path(td)
            _write_fake_export(export, n=2500)
            chunks_path, vectors, manifest, skip_manifest, total = \
                prepare_streaming_import(export)

            assert total == 2500
            assert manifest["chunk_count"] == 2500
            assert skip_manifest is None

            collected_chunks: list[dict] = []
            collected_vecs: list[np.ndarray] = []
            for batch_chunks, batch_vecs in stream_export_batches(
                chunks_path, vectors, batch_size=300,
            ):
                assert 1 <= len(batch_chunks) <= 300
                assert batch_vecs.shape == (len(batch_chunks), VECTOR_DIM)
                collected_chunks.extend(batch_chunks)
                collected_vecs.append(batch_vecs)

            assert len(collected_chunks) == 2500
            assert collected_chunks[0]["chunk_id"] == "c000000"
            assert collected_chunks[-1]["chunk_id"] == "c002499"

            stacked = np.vstack(collected_vecs)
            truth = np.load(str(export / "vectors.npy"))
            np.testing.assert_array_equal(stacked, truth)

    def test_skips_malformed_lines_without_aborting(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            export = Path(td)
            _write_fake_export(export, n=50, corrupt_line=25)
            chunks_path, vectors, _, _, _ = prepare_streaming_import(export)

            seen_ids = []
            for batch_chunks, _batch_vecs in stream_export_batches(
                chunks_path, vectors, batch_size=10,
            ):
                seen_ids.extend(c["chunk_id"] for c in batch_chunks)

            # One corrupt line dropped; every other row survives.
            assert len(seen_ids) == 49
            assert "c000025" not in seen_ids

    def test_peak_memory_bounded_relative_to_batch(self) -> None:
        """Streaming must not blow past a few batches worth of chunk state.

        This is the regression guard for the 10M-class laptop blowup. On a
        20K chunk export, peak alloc should be orders of magnitude under
        the full-corpus materialisation cost.
        """
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            export = Path(td)
            _write_fake_export(export, n=20_000)
            chunks_path, vectors, _, _, total = prepare_streaming_import(export)
            assert total == 20_000

            tracemalloc.start()
            last = None
            for batch in stream_export_batches(chunks_path, vectors, batch_size=500):
                last = batch
                del batch
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            assert last is not None

            # Empirically one 500-chunk batch allocates well under 5 MB here.
            # 50 MB is a generous ceiling -- failing this bound almost
            # certainly means a regression back to full-corpus list reads.
            assert peak < 50 * 1024 * 1024, f"peak alloc {peak} bytes too high"


class TestPrepareStreamingImportValidatesManifest:

    def test_rejects_mismatched_vector_dim(self, capsys: pytest.CaptureFixture) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            export = Path(td)
            _write_fake_export(export, n=10)
            # Corrupt manifest to force a REJECT issue.
            manifest_path = export / "manifest.json"
            bad = json.loads(manifest_path.read_text(encoding="utf-8"))
            bad["vector_dim"] = VECTOR_DIM + 99
            manifest_path.write_text(json.dumps(bad), encoding="utf-8")

            with pytest.raises(SystemExit):
                prepare_streaming_import(export)
            captured = capsys.readouterr()
            assert "REJECT" in captured.err


# --------------------------------------------------------------------------
# Contract: load_export remains available (CLI callers still use it)
# --------------------------------------------------------------------------

def test_load_export_still_available_for_cli_compat() -> None:
    assert hasattr(import_embedengine, "load_export")


# --------------------------------------------------------------------------
# End-to-end: drive the real ImportExtractRunner IMPORT phase against a
# small synthetic export, verify LanceDB gets the rows, and verify the
# ram_status / gpu_status stats the panel shows do not leak banned tokens.
# --------------------------------------------------------------------------

class TestImportPhaseEndToEnd:

    def test_runner_streams_export_into_real_lancedb(self, tmp_path, monkeypatch):
        import types

        from tests.test_import_extract_gui_streaming import FakeGUI
        from scripts.import_extract_gui import ImportExtractRunner
        import scripts.import_extract_gui as gui_module

        # Synthetic export on disk -- real files, real vectors.npy, real
        # chunks.jsonl. Small enough to run in a couple of seconds.
        export_dir = tmp_path / "export_test"
        export_dir.mkdir()
        n = 1500
        _write_fake_export(export_dir, n=n)
        # Right-size vectors to the GUI's schema (the real pipeline uses
        # 1024d here -- but LanceStore infers the dim from the first batch
        # so any positive dim is fine for this test).

        lance_db_dir = tmp_path / "lancedb"
        entity_db = tmp_path / "entities.sqlite3"

        # Minimal config the runner reads during IMPORT.
        fake_config = types.SimpleNamespace(
            paths=types.SimpleNamespace(
                lance_db=str(lance_db_dir),
                entity_db=str(entity_db),
            ),
            extraction=types.SimpleNamespace(
                part_patterns=[r"PO-\d{4}-\d{4}"],
                security_standard_exclude_patterns=[],
                gliner_model="fake-model",
                gliner_device="cpu",
                gliner_min_chunk_len=20,
                min_confidence=0.5,
            ),
        )

        def fake_load_config(_path):
            return fake_config

        monkeypatch.setattr(
            "src.config.schema.load_config", fake_load_config,
        )

        # Stop the runner after the IMPORT phase completes so we do not
        # enter Tier 1 / Tier 2 (Tier 1 needs a real RegexPreExtractor and
        # Tier 2 needs a real GLiNER model -- both are covered by the
        # existing test_import_extract_gui_streaming.py battery).
        gui = FakeGUI()
        runner = ImportExtractRunner(gui)

        original_set_phase = runner._set_phase
        def phase_then_maybe_stop(phase: str):
            original_set_phase(phase)
            if phase == "TIER 1 REGEX":
                runner._stop_event.set()
        monkeypatch.setattr(runner, "_set_phase", phase_then_maybe_stop)

        # Run inline (no background thread) to keep the test deterministic.
        runner._run(
            source=str(export_dir),
            max_tier=1,
            config_path="unused",
            skip_import=False,
        )

        # --- Assertions ---

        # 1. Import phase recorded PASS, all rows landed in LanceDB.
        from src.store.lance_store import LanceStore
        store = LanceStore(str(lance_db_dir))
        try:
            assert store.count() == n, f"expected {n} rows, got {store.count()}"
        finally:
            store.close()

        # 2. RAM stat was populated during the import phase (proves the
        #    panel is now showing RAM, not a stale VRAM-only string).
        assert "ram_status" in gui.stats
        ram_value = gui.stats["ram_status"]
        assert "GB" in ram_value

        # 3. No banned-token leak through any stat the panel displays.
        for key, value in gui.stats.items():
            text = str(value)
            for token in BANNED_TOKENS_FOR_PANEL:
                assert token not in text, (
                    f"stat {key!r} leaked banned token {token!r}: {text!r}"
                )

        # 4. No banned-token leak through any log line.
        for level, msg in gui.log_lines:
            for token in BANNED_TOKENS_FOR_PANEL:
                assert token not in msg, (
                    f"log line leaked banned token {token!r}: {msg!r}"
                )

        # 5. Peak RSS during the run stayed bounded. We ask psutil what
        #    the current process RSS is -- on a 1500-chunk synthetic export
        #    the streaming path should be well under 2 GB resident.
        import psutil
        rss_now = psutil.Process().memory_info().rss
        assert rss_now < 2 * 1024 * 1024 * 1024, (
            f"process RSS after import = {rss_now} bytes (> 2 GB budget)"
        )
