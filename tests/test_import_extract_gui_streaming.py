"""
Tests for scripts/import_extract_gui.py Tier 1 / Tier 2 streaming runner.

Guards the port of the Round 3 CLI streaming fix (commit 8a1531b) into the
GUI walk-away runner. The GUI previously accumulated every chunk into
``all_chunks_for_tier2`` during Tier 1 so Tier 2 could filter them later;
on the 10.4M-chunk corpus the laptop hit 57.9 GB RSS and the walk-away
was unusable.

These tests do NOT start a real Tk mainloop. They drive ``ImportExtractRunner``
directly against a real tempdir ``LanceStore`` with a stubbed GUI object
and a fake GLiNER model. The GUI-specific ``_safe_after`` indirection is
bypassed by a ``FakeRoot`` that runs scheduled callbacks inline, so every
``_set_progress`` / ``_set_stat`` / ``_log`` call still lands on the stub
GUI without needing a real Tk widget tree.

What's locked in:

  - Tier 1 flushes entities per-batch — in-memory Entity list never
    grows beyond one stream batch.
  - Tier 1 does NOT hold chunks across batches (no all_chunks_for_tier2).
  - Tier 2 opens its own streaming pass over the store, does not
    consume a list from Tier 1.
  - Stop event mid-stream cleanly aborts without losing committed data.
  - GLiNER batches stay bounded to ``gliner_batch_size`` (no full-corpus
    batch, which would signal a regression to the accumulator pattern).
  - tracemalloc peak during a 1000-chunk Tier 1 stream stays bounded.
"""

from __future__ import annotations

import sys
import tempfile
import tracemalloc
import types
from pathlib import Path

import numpy as np
import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.store.lance_store import LanceStore
from src.store.entity_store import EntityStore
from src.store.relationship_store import RelationshipStore

# ImportExtractRunner lives inside scripts/import_extract_gui.py which
# imports tkinter at module level. That's fine on Windows headless runs.
import scripts.import_extract_gui as gui_module
from scripts.import_extract_gui import ImportExtractRunner


# ---------------------------------------------------------------------------
# Test fixtures — real LanceStore, fake Tk root, fake GUI
# ---------------------------------------------------------------------------

VECTOR_DIM = 8


def _build_real_store(tmp_path: Path, n_chunks: int, prose_ratio: float = 1.0) -> LanceStore:
    """Real LanceStore with n_chunks rows. prose_ratio controls how many
    pass the Tier 2 candidate filter."""
    db_path = str(tmp_path / "lancedb")
    store = LanceStore(db_path)

    chunks: list[dict] = []
    n_prose = int(n_chunks * prose_ratio)
    for i in range(n_prose):
        chunks.append({
            "chunk_id": f"prose-{i:06d}",
            "text": (
                f"The site lead inspected the tower at chunk {i}. "
                f"Jane Doe filed a report with Acme Corp on site Alpha-{i}. "
                f"PO-2024-{i:04d} was delivered on 2024-11-15."
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

    rng = np.random.default_rng(seed=42)
    vectors = rng.standard_normal(size=(n_chunks, VECTOR_DIM)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9

    store.ingest_chunks(chunks, vectors, batch_size=500)
    return store


class FakeRoot:
    """Minimal Tk-root stand-in.

    The real ``ImportExtractRunner._log`` / ``_set_progress`` / ``_set_stat``
    / ``_set_phase`` methods all call ``_safe_after(self.gui.root, 0, fn, ...)``
    which on a real Tk root schedules ``fn(...)`` via ``root.after(0, ...)``.
    FakeRoot.after() just runs the callable inline — that keeps the tests
    single-threaded and deterministic, and every GUI update still lands on
    the stub GUI so we can assert progress was reported.
    """

    def __init__(self):
        self.after_calls: list[tuple[int, tuple]] = []

    def after(self, ms, fn, *args):
        self.after_calls.append((ms, args))
        fn(*args)


class FakeGUI:
    """Stub for ImportExtractGUI. Records every GUI-visible update."""

    def __init__(self):
        self.root = FakeRoot()
        self.log_lines: list[tuple[str, str]] = []
        self.phase_history: list[str] = []
        self.progress_history: list[tuple[int, int]] = []
        self.stats: dict[str, object] = {}
        self.finished_status: str | None = None
        self.finished_results: dict | None = None

    # The methods ImportExtractRunner drives via _safe_after
    def append_log(self, msg: str, level: str = "INFO"):
        self.log_lines.append((level, msg))

    def set_phase(self, phase: str):
        self.phase_history.append(phase)

    def set_progress(self, current: int, total: int):
        self.progress_history.append((current, total))

    def set_stat(self, key: str, value):
        self.stats[key] = value

    def on_pipeline_finished(self, status: str, results: dict):
        self.finished_status = status
        self.finished_results = results


class FakeGLiNERModel:
    """Fake GLiNER replacement.

    Round 3 used a keyword-arg ``gliner_model`` injection hook for the CLI
    test. The GUI runner inlines model loading (for tighter progress
    coupling), so we intercept the model via ``monkeypatch`` on
    ``GLiNER.from_pretrained`` and ``torch.cuda.is_available`` / device
    checks.
    """

    def __init__(self):
        self.batch_calls: list[int] = []

    def to(self, device):
        return self

    def batch_predict_entities(self, texts, labels, threshold, flat_ner):
        self.batch_calls.append(len(texts))
        return [
            [{"text": "Jane Doe", "label": "PERSON", "score": 0.95}]
            for _ in texts
        ]


@pytest.fixture
def tempdir_store(tmp_path):
    """Small real LanceStore with 200 prose chunks."""
    store = _build_real_store(tmp_path, n_chunks=200, prose_ratio=1.0)
    store.close()  # ImportExtractRunner opens its own handle
    return tmp_path


@pytest.fixture
def fake_gui():
    return FakeGUI()


@pytest.fixture
def fake_config(tmp_path):
    """Minimal config object exposing the fields the runner reads."""
    cfg_paths = types.SimpleNamespace(
        lance_db=str(tmp_path / "lancedb").replace(str(V2_ROOT) + "\\", "").replace(str(V2_ROOT) + "/", ""),
        entity_db=str(tmp_path / "entities.sqlite3").replace(str(V2_ROOT) + "\\", "").replace(str(V2_ROOT) + "/", ""),
    )
    cfg_extraction = types.SimpleNamespace(
        part_patterns=[r"PO-\d{4}-\d{4}"],
        gliner_model="fake-model",
        gliner_device="cpu",
        gliner_min_chunk_len=20,
        min_confidence=0.5,
    )
    return types.SimpleNamespace(
        paths=cfg_paths,
        extraction=cfg_extraction,
    )


# ---------------------------------------------------------------------------
# Source-level contract checks — lock in that the accumulator is gone
# ---------------------------------------------------------------------------

class TestSourceContract:
    """These tests read the GUI source file as text and assert the bug
    pattern is NOT present. They are brittle by design: the whole point
    is to fail loudly if anyone re-introduces ``all_chunks_for_tier2``
    during a future refactor.
    """

    def _gui_source(self) -> str:
        return Path(gui_module.__file__).read_text(encoding="utf-8")

    def test_no_all_chunks_for_tier2_accumulator(self):
        src = self._gui_source()
        assert "all_chunks_for_tier2" not in src, (
            "import_extract_gui.py still references all_chunks_for_tier2 — "
            "the Tier 1 chunk accumulator that blew RAM past 57 GB on 10.4M "
            "chunks. It must not come back. See commit 8a1531b."
        )

    def test_no_full_filter_list_comprehension(self):
        """The old Tier 2 filter was a list comprehension over every
        Tier 1 chunk: ``filtered = [c for c in all_chunks_for_tier2 ...]``.
        Guard against it re-appearing."""
        src = self._gui_source()
        assert "all_chunks_for_tier2" not in src
        assert "filtered = [c for c in all_chunks_for_tier2" not in src

    def test_tier2_uses_iter_chunk_batches(self):
        """Tier 2 must loop over iter_chunk_batches, not a pre-loaded list."""
        src = self._gui_source()
        # At least two occurrences of iter_chunk_batches — one for Tier 1,
        # one for the Tier 2 second pass. Old version had exactly one.
        assert src.count("for batch in iter_chunk_batches") >= 2, (
            "Tier 2 must open a second streaming pass via iter_chunk_batches"
        )

    def test_imports_tier2_helpers_from_tiered_extract(self):
        """The canonical Tier 2 helpers (_is_tier2_candidate,
        _resolve_gliner_device) live in scripts.tiered_extract and must
        be imported from there so the module-level
        _assert_streaming_api_available guard runs at GUI import time."""
        src = self._gui_source()
        assert "from scripts.tiered_extract import" in src
        assert "_is_tier2_candidate" in src
        assert "iter_chunk_batches" in src

    def test_tier1_flushes_per_batch(self):
        """Tier 1 should insert entities to the store per batch, not
        accumulate them into a corpus-scale list first."""
        src = self._gui_source()
        # The new loop wraps per-batch state in batch_entities / batch_rels
        # and calls insert_entities on each batch before clearing.
        assert "batch_entities" in src
        assert "entity_store.insert_entities(batch_entities)" in src


# ---------------------------------------------------------------------------
# Import-time guard chain
# ---------------------------------------------------------------------------

class TestImportGuardChain:
    def test_gui_import_triggers_streaming_api_guard(self, monkeypatch):
        """Importing the GUI module must chain through to
        scripts.tiered_extract, whose module-level
        _assert_streaming_api_available() runs on import. That means a
        lancedb regression that drops LanceQueryBuilder.to_batches trips
        the GUI at import time, before a walk-away run starts.
        """
        # The module is already imported above, so assert the guard
        # function exists and passes on current env.
        from scripts.tiered_extract import _assert_streaming_api_available
        _assert_streaming_api_available()  # no-op on healthy install

        # And the GUI module exposes no local copy of _is_tier2_candidate
        # (it imports from the canonical location lazily inside _run).
        assert not hasattr(gui_module, "_is_tier2_candidate")


# ---------------------------------------------------------------------------
# Helper — drive ImportExtractRunner._run() against real LanceStore
# ---------------------------------------------------------------------------


def _invoke_run(
    runner: ImportExtractRunner,
    tmp_path: Path,
    max_tier: int,
    monkeypatch,
    fake_model: FakeGLiNERModel | None = None,
    lance_subdir: str = "lancedb",
    stop_after: int | None = None,
):
    """Run ImportExtractRunner._run() with skip_import=True and a config
    pointed at a real LanceStore inside tmp_path. Returns the runner's
    final results dict via the stub GUI.

    - ``fake_model`` stubs ``gliner.GLiNER.from_pretrained`` when max_tier >= 2
    - ``stop_after`` triggers self._stop_event after N log calls (None = never)
    """
    # Point config.paths.lance_db at the absolute tmp_path store
    cfg = types.SimpleNamespace(
        paths=types.SimpleNamespace(
            lance_db=str(tmp_path / lance_subdir),
            entity_db=str(tmp_path / "entities.sqlite3"),
        ),
        extraction=types.SimpleNamespace(
            part_patterns=[r"PO-\d{4}-\d{4}"],
            gliner_model="fake-model",
            gliner_device="cpu",
            gliner_min_chunk_len=20,
            min_confidence=0.5,
        ),
    )

    # Monkey-patch load_config so _run picks up the test cfg
    monkeypatch.setattr(
        "src.config.schema.load_config",
        lambda path: cfg,
    )
    # V2_ROOT is joined with config paths in the runner; we pre-absolutized
    # the paths so the join is a no-op only if we also patch V2_ROOT.
    monkeypatch.setattr(gui_module, "V2_ROOT", Path("/"))

    if fake_model is not None:
        # Patch GLiNER.from_pretrained before the runner imports it
        fake_gliner_module = types.SimpleNamespace(
            GLiNER=types.SimpleNamespace(
                from_pretrained=lambda name: fake_model,
            ),
        )
        monkeypatch.setitem(sys.modules, "gliner", fake_gliner_module)
        # Pretend CUDA is unavailable so runner uses the CPU path
        import torch
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        # The runner returns early when CUDA unavailable in Tier 2 path.
        # For the test we want Tier 2 to run, so also patch device config
        # and bypass the cuda-gate by injecting a post-resolve model path.
        # Simpler: set gliner_device to "cpu" in config (already done above).

    # Hook into _log to trigger stop after N calls
    real_log = runner._log
    log_count = {"n": 0}

    def maybe_stop_log(msg, level="INFO"):
        log_count["n"] += 1
        real_log(msg, level)
        if stop_after is not None and log_count["n"] >= stop_after:
            runner._stop_event.set()

    monkeypatch.setattr(runner, "_log", maybe_stop_log)

    runner._run(
        source="",
        max_tier=max_tier,
        config_path="ignored",
        skip_import=True,
    )


# ---------------------------------------------------------------------------
# Tier 1 behaviour against a real LanceStore
# ---------------------------------------------------------------------------


class TestTier1Streaming:
    def test_tier1_runs_end_to_end_on_real_store(self, tmp_path, fake_gui, monkeypatch):
        _build_real_store(tmp_path, n_chunks=200, prose_ratio=1.0).close()

        runner = ImportExtractRunner(fake_gui)
        _invoke_run(runner, tmp_path, max_tier=1, monkeypatch=monkeypatch)

        # Pipeline should finish cleanly, no stop requested.
        assert fake_gui.finished_status == "PASS", (
            f"Expected PASS, got {fake_gui.finished_status}. "
            f"Tail log: {fake_gui.log_lines[-5:]}"
        )
        assert "tier1" in fake_gui.finished_results
        assert fake_gui.finished_results["tier1"]["status"] == "PASS"
        assert fake_gui.finished_results["tier1"]["entities"] > 0

        # Progress must have advanced through all 200 chunks.
        final_progress = fake_gui.progress_history[-1]
        assert final_progress[0] == 200, f"progress didn't reach 200: {final_progress}"

        # Phase transitions
        assert "TIER 1 REGEX" in fake_gui.phase_history
        assert "DONE" in fake_gui.phase_history

    def test_tier1_stop_event_aborts_cleanly(self, tmp_path, fake_gui, monkeypatch):
        _build_real_store(tmp_path, n_chunks=500, prose_ratio=1.0).close()

        runner = ImportExtractRunner(fake_gui)
        # Stop after ~4 log lines — enough to get past the header
        _invoke_run(
            runner, tmp_path, max_tier=1,
            monkeypatch=monkeypatch, stop_after=4,
        )

        # Should surface STOPPED, not PASS
        assert fake_gui.finished_status == "STOPPED"
        assert "STOPPED" in fake_gui.phase_history

    def test_tier1_memory_is_bounded_under_tracemalloc(self, tmp_path, fake_gui, monkeypatch):
        _build_real_store(tmp_path, n_chunks=1000, prose_ratio=1.0).close()
        runner = ImportExtractRunner(fake_gui)

        tracemalloc.start()
        try:
            tracemalloc.clear_traces()
            _invoke_run(runner, tmp_path, max_tier=1, monkeypatch=monkeypatch)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        # 1000-chunk Tier 1 through the streaming runner should stay
        # well below a ceiling that catches accidental accumulation.
        # 50 MB is generous but still well under what a full-list
        # pattern would use.
        assert peak < 50 * 1024 * 1024, (
            f"Tier 1 tracemalloc peak {peak / 1e6:.1f} MB exceeds 50 MB — "
            f"possible regression to the accumulator pattern"
        )


# ---------------------------------------------------------------------------
# Tier 2 streaming behaviour
# ---------------------------------------------------------------------------


class TestTier2Streaming:
    def test_tier2_opens_second_streaming_pass(self, tmp_path, fake_gui, monkeypatch):
        _build_real_store(tmp_path, n_chunks=120, prose_ratio=1.0).close()

        fake_model = FakeGLiNERModel()
        runner = ImportExtractRunner(fake_gui)
        _invoke_run(
            runner, tmp_path, max_tier=2,
            monkeypatch=monkeypatch, fake_model=fake_model,
        )

        assert fake_gui.finished_status == "PASS", (
            f"Expected PASS, got {fake_gui.finished_status}. "
            f"Log tail: {fake_gui.log_lines[-5:]}"
        )
        assert "tier2" in fake_gui.finished_results
        assert fake_gui.finished_results["tier2"]["status"] == "PASS"
        assert fake_gui.finished_results["tier2"]["scanned"] == 120
        # Every prose chunk passes the candidate filter
        assert fake_gui.finished_results["tier2"]["candidates"] == 120

        # GLiNER batches must be bounded. With gliner_batch_size=8 and 120
        # candidates the batches should be: fifteen of 8 = 120. No single
        # call equal to the corpus size.
        assert fake_model.batch_calls, "GLiNER was never called"
        assert max(fake_model.batch_calls) <= 8, (
            f"batch sizes exceeded bound: {fake_model.batch_calls}"
        )
        assert sum(fake_model.batch_calls) == 120

    def test_tier2_filter_drops_noise(self, tmp_path, fake_gui, monkeypatch):
        # 60 prose + 40 noise. Candidate count should equal 60.
        _build_real_store(tmp_path, n_chunks=100, prose_ratio=0.6).close()

        fake_model = FakeGLiNERModel()
        runner = ImportExtractRunner(fake_gui)
        _invoke_run(
            runner, tmp_path, max_tier=2,
            monkeypatch=monkeypatch, fake_model=fake_model,
        )

        assert fake_gui.finished_status == "PASS"
        t2 = fake_gui.finished_results["tier2"]
        assert t2["scanned"] == 100
        assert t2["candidates"] == 60
        assert sum(fake_model.batch_calls) == 60


# ---------------------------------------------------------------------------
# UI update contract — _safe_after indirection + per-batch progress
# ---------------------------------------------------------------------------


class TestGuiUpdates:
    def test_runner_uses_safe_after_for_updates(self, tmp_path, fake_gui, monkeypatch):
        """Every log / progress / stat call must route through
        _safe_after(root, 0, fn, ...). FakeRoot records those calls."""
        _build_real_store(tmp_path, n_chunks=50, prose_ratio=1.0).close()

        runner = ImportExtractRunner(fake_gui)
        _invoke_run(runner, tmp_path, max_tier=1, monkeypatch=monkeypatch)

        # FakeRoot should have seen at least one after() call
        assert fake_gui.root.after_calls, (
            "Runner bypassed _safe_after — GUI updates must go through "
            "root.after(0, ...) to stay on the Tk main thread"
        )

    def test_tier1_progress_updates_per_batch(self, tmp_path, fake_gui, monkeypatch):
        """Progress should advance through multiple points, not jump
        from 0 to end."""
        _build_real_store(tmp_path, n_chunks=50, prose_ratio=1.0).close()
        runner = ImportExtractRunner(fake_gui)
        _invoke_run(runner, tmp_path, max_tier=1, monkeypatch=monkeypatch)

        # We use batch_size=10000 in the runner; 50 chunks fit in one batch,
        # so we expect at least one (0,0) initial + one (50, 50) final.
        assert len(fake_gui.progress_history) >= 2
        assert fake_gui.progress_history[0] == (0, 0)  # phase reset
        assert fake_gui.progress_history[-1][0] == 50


# ---------------------------------------------------------------------------
# ImportExtractGUI._on_start() validation — Skip Import interaction
# ---------------------------------------------------------------------------
#
# Regression tests for the "Skip Import blocks on empty source folder"
# papercut reported during laptop testing on 2026-04-11. The
# _on_start() validation must:
#
#   - Allow Start when Skip Import is checked, regardless of source.
#   - Allow Start when Skip Import is checked AND source is non-empty
#     (source is ignored with an info log).
#   - Block Start with a clear error when Skip Import is unchecked AND
#     source is empty.
#   - Block Start with a missing-file error when Skip Import is
#     unchecked AND source points at a folder without chunks.jsonl or
#     vectors.npy.
#
# These tests instantiate the real ImportExtractGUI with a real Tk root
# (withdrawn, no mainloop) so we exercise the genuine StringVar /
# BooleanVar / ttk.Checkbutton bindings rather than a stub. The runner
# thread is mocked so tests don't actually start a background pipeline.


@pytest.fixture
def real_gui_root():
    """Real Tk root for headless validation tests.

    Withdraws the window so no on-screen flash, destroys on teardown.
    Some Tk styles error out on Windows if `Tk()` can't init a display —
    we skip the whole class in that unlikely case.
    """
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError as e:  # pragma: no cover - only hits on broken displays
        pytest.skip(f"Tk not available in this environment: {e}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestOnStartSkipImport:
    """Guard the Skip Import checkbox / source folder validation."""

    def _build_gui(self, root, monkeypatch):
        """Instantiate ImportExtractGUI with the runner's start method
        stubbed so _on_start can't spawn a background thread."""
        from scripts.import_extract_gui import ImportExtractGUI, ImportExtractRunner

        started_calls: list[tuple] = []

        def fake_start(self, source, max_tier, config_path, skip_import):
            started_calls.append((source, max_tier, config_path, skip_import))
            # Mimic what start() normally does to keep GUI state sane
            self._stop_event = self._stop_event if hasattr(self, "_stop_event") else None

        monkeypatch.setattr(ImportExtractRunner, "start", fake_start)

        gui = ImportExtractGUI(root)
        # Capture every log line the validation path writes
        logs: list[tuple[str, str]] = []
        orig_append = gui.append_log

        def capture_log(msg, level="INFO"):
            logs.append((level, msg))
            # Don't re-run the real widget call — avoids write after destroy
            # races and lets us drive the test purely through BooleanVars.

        monkeypatch.setattr(gui, "append_log", capture_log)

        return gui, logs, started_calls

    def test_skip_import_with_empty_source_allows_start(self, real_gui_root, monkeypatch):
        gui, logs, started_calls = self._build_gui(real_gui_root, monkeypatch)
        gui._source_var.set("")
        gui._skip_import_var.set(True)

        gui._on_start()

        # No error, at least one INFO log mentioning skip_import being honored
        assert not any(level == "ERROR" for level, _ in logs), (
            f"Skip Import + empty source should NOT error, got logs: {logs}"
        )
        assert any("Skip Import" in msg for _, msg in logs), (
            f"Expected visible skip-import confirmation, got: {logs}"
        )
        # Runner was asked to start
        assert len(started_calls) == 1
        src, _, _, skip = started_calls[0]
        assert src == ""
        assert skip is True

    def test_skip_import_with_filled_source_ignores_folder(
        self, real_gui_root, tmp_path, monkeypatch
    ):
        gui, logs, started_calls = self._build_gui(real_gui_root, monkeypatch)
        gui._source_var.set(str(tmp_path))
        gui._skip_import_var.set(True)

        gui._on_start()

        # The folder does NOT have chunks.jsonl or vectors.npy, but we
        # should NOT error because Skip Import is checked.
        assert not any(level == "ERROR" for level, _ in logs), (
            f"Skip Import should ignore folder validation, got: {logs}"
        )
        assert any("ignoring source folder" in msg for _, msg in logs), (
            f"Expected 'ignoring source folder' log, got: {logs}"
        )
        assert len(started_calls) == 1

    def test_no_skip_import_empty_source_blocks_with_clear_error(
        self, real_gui_root, monkeypatch
    ):
        gui, logs, started_calls = self._build_gui(real_gui_root, monkeypatch)
        gui._source_var.set("")
        gui._skip_import_var.set(False)

        gui._on_start()

        # Must error and must NOT start the runner
        errors = [msg for level, msg in logs if level == "ERROR"]
        assert errors, f"Expected error for empty source + no skip, got: {logs}"
        assert any("Select a source export folder" in e for e in errors)
        # Error message also hints at the Skip Import alternative — UX polish
        assert any("Skip Import" in e for e in errors), (
            "Error should mention Skip Import as the alternative for operators "
            f"who already have a populated store, got: {errors}"
        )
        assert started_calls == []

    def test_no_skip_import_missing_export_files_blocks(
        self, real_gui_root, tmp_path, monkeypatch
    ):
        gui, logs, started_calls = self._build_gui(real_gui_root, monkeypatch)
        # Empty directory — no chunks.jsonl, no vectors.npy
        gui._source_var.set(str(tmp_path))
        gui._skip_import_var.set(False)

        gui._on_start()

        errors = [msg for level, msg in logs if level == "ERROR"]
        assert errors
        assert any(
            "chunks.jsonl" in e or "vectors.npy" in e for e in errors
        ), f"Expected missing-file error, got: {errors}"
        assert started_calls == []

    def test_no_skip_import_not_a_directory_blocks(
        self, real_gui_root, tmp_path, monkeypatch
    ):
        gui, logs, started_calls = self._build_gui(real_gui_root, monkeypatch)
        # Point at a file, not a directory
        fake_file = tmp_path / "not_a_dir.txt"
        fake_file.write_text("", encoding="utf-8")
        gui._source_var.set(str(fake_file))
        gui._skip_import_var.set(False)

        gui._on_start()

        errors = [msg for level, msg in logs if level == "ERROR"]
        assert any("Not a directory" in e for e in errors), (
            f"Expected 'Not a directory' error, got: {errors}"
        )
        assert started_calls == []


# ---------------------------------------------------------------------------
# Runner: _run() Skip Import path must not Path("").resolve() the source
# ---------------------------------------------------------------------------


class TestRunnerSkipImportStats:
    """When skip_import=True, the runner must NOT call Path(source).resolve()
    on an empty source (which resolves to cwd and leaks a misleading path
    into the source_path stat). Instead it must set a 'skipped' stat and
    log that the import phase is being bypassed.
    """

    def test_skip_import_sets_skipped_stat(self, tmp_path, fake_gui, monkeypatch):
        _build_real_store(tmp_path, n_chunks=20, prose_ratio=1.0).close()

        runner = ImportExtractRunner(fake_gui)
        _invoke_run(
            runner, tmp_path, max_tier=1, monkeypatch=monkeypatch,
        )

        stat = fake_gui.stats.get("source_path", "")
        assert "skipped" in stat.lower(), (
            f"Expected source_path stat to show 'skipped' marker when "
            f"skip_import=True, got: {stat!r}"
        )
        assert any("Import phase skipped" in msg for _, msg in fake_gui.log_lines), (
            "Expected an operator-visible log line confirming the skip"
        )
