"""Tests for Embedder._apply_cpu_reservation() — 3-layer CPU reservation.

Covers QA-3 Pillar 2 (Core Pipeline) and Pillar 5 (Graceful Degradation):
  - Thread cap math across cpu_count values (16, 4, 2, 1, None)
  - Graceful degradation when psutil is missing (mock ImportError)
  - Env var (OMP_NUM_THREADS, MKL_NUM_THREADS) setting and non-clobber
  - Silent failures don't crash the embedder
  - Layer status reporting accuracy (B2 fix verification)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.query.embedder import Embedder


# ---------------------------------------------------------------------------
# Helper — call _apply_cpu_reservation without full Embedder __init__
# ---------------------------------------------------------------------------

def _call_reservation(monkeypatch, cpu_count, psutil_mod=None, torch_mod=None,
                      reserved=2, preset_omp=None, preset_mkl=None):
    """Call Embedder._apply_cpu_reservation with controlled mocks."""
    monkeypatch.setattr(os, "cpu_count", lambda: cpu_count)

    if preset_omp is not None:
        monkeypatch.setenv("OMP_NUM_THREADS", preset_omp)
    else:
        monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    if preset_mkl is not None:
        monkeypatch.setenv("MKL_NUM_THREADS", preset_mkl)
    else:
        monkeypatch.delenv("MKL_NUM_THREADS", raising=False)

    modules = {}
    if psutil_mod is not None:
        modules["psutil"] = psutil_mod
    if torch_mod is not None:
        modules["torch"] = torch_mod

    # Remove cached modules so fresh imports hit our mocks
    for mod_name in ("psutil", "torch"):
        if mod_name not in modules:
            # Make import raise ImportError
            modules[mod_name] = None

    # patch sys.modules so `import psutil` / `import torch` resolve to our mocks
    # None value causes ImportError on import
    with patch.dict("sys.modules", modules):
        return Embedder._apply_cpu_reservation(reserved)


def _make_psutil(affinity_side_effect=None, nice_side_effect=None):
    """Build a fake psutil module with controllable Process()."""
    fake = MagicMock()
    proc = MagicMock()
    if affinity_side_effect:
        proc.cpu_affinity.side_effect = affinity_side_effect
    if nice_side_effect:
        proc.nice.side_effect = nice_side_effect
    fake.Process.return_value = proc
    fake.BELOW_NORMAL_PRIORITY_CLASS = 16384
    return fake, proc


# ---------------------------------------------------------------------------
# Thread cap math (Layer 3) — various cpu_count values
# ---------------------------------------------------------------------------

class TestThreadCapMath:
    """Small helper object used to keep test setup or expected results organized."""

    @pytest.mark.parametrize("cpu_count, expected_threads", [
        (16, 14),
        (4, 2),
        (2, 1),
        (1, 1),
        (None, 1),
    ])
    def test_thread_cap_values(self, monkeypatch, cpu_count, expected_threads):
        fake_psutil, _ = _make_psutil()
        fake_torch = MagicMock()

        status = _call_reservation(monkeypatch, cpu_count,
                                   psutil_mod=fake_psutil, torch_mod=fake_torch)

        fake_torch.set_num_threads.assert_called_once_with(expected_threads)
        assert os.environ.get("OMP_NUM_THREADS") == str(expected_threads)
        assert os.environ.get("MKL_NUM_THREADS") == str(expected_threads)


# ---------------------------------------------------------------------------
# Graceful degradation — psutil missing
# ---------------------------------------------------------------------------

class TestPsutilMissing:

    """Small helper object used to keep test setup or expected results organized."""
    def test_affinity_and_priority_skip_without_psutil(self, monkeypatch):
        fake_torch = MagicMock()

        # psutil_mod=None → sys.modules["psutil"] = None → ImportError
        status = _call_reservation(monkeypatch, 8,
                                   psutil_mod=None, torch_mod=fake_torch)

        assert "psutil missing" in status["affinity"]
        assert "psutil missing" in status["priority"]
        assert status["thread_cap"] == "OK"
        fake_torch.set_num_threads.assert_called_once_with(6)


# ---------------------------------------------------------------------------
# Env vars
# ---------------------------------------------------------------------------

class TestEnvVars:

    """Small helper object used to keep test setup or expected results organized."""
    def test_env_vars_set_to_thread_cap(self, monkeypatch):
        fake_psutil, _ = _make_psutil()
        fake_torch = MagicMock()

        _call_reservation(monkeypatch, 16,
                          psutil_mod=fake_psutil, torch_mod=fake_torch)

        assert os.environ["OMP_NUM_THREADS"] == "14"
        assert os.environ["MKL_NUM_THREADS"] == "14"

    def test_env_vars_not_overwritten_if_already_set(self, monkeypatch):
        fake_psutil, _ = _make_psutil()
        fake_torch = MagicMock()

        _call_reservation(monkeypatch, 16,
                          psutil_mod=fake_psutil, torch_mod=fake_torch,
                          preset_omp="4", preset_mkl="4")

        assert os.environ["OMP_NUM_THREADS"] == "4"
        assert os.environ["MKL_NUM_THREADS"] == "4"


# ---------------------------------------------------------------------------
# Silent failures don't crash
# ---------------------------------------------------------------------------

class TestSilentFailures:

    """Small helper object used to keep test setup or expected results organized."""
    def test_affinity_oserror_does_not_crash(self, monkeypatch):
        fake_psutil, proc = _make_psutil(
            affinity_side_effect=OSError("Permission denied"))
        fake_torch = MagicMock()

        status = _call_reservation(monkeypatch, 8,
                                   psutil_mod=fake_psutil, torch_mod=fake_torch)

        assert "FAILED" in status["affinity"]
        assert status["priority"] == "OK"
        assert status["thread_cap"] == "OK"

    def test_torch_missing_does_not_crash(self, monkeypatch):
        fake_psutil, _ = _make_psutil()

        # torch_mod=None → ImportError on `import torch`
        status = _call_reservation(monkeypatch, 4,
                                   psutil_mod=fake_psutil, torch_mod=None)

        assert "no torch" in status["thread_cap"]
        assert status["affinity"] == "OK"
        assert status["priority"] == "OK"

    def test_all_layers_fail_gracefully(self, monkeypatch):
        """Even if every layer fails, the method returns without raising."""
        fake_psutil, proc = _make_psutil(
            affinity_side_effect=OSError("denied"),
            nice_side_effect=PermissionError("denied"))
        fake_torch = MagicMock()
        fake_torch.set_num_threads.side_effect = RuntimeError("broken")

        status = _call_reservation(monkeypatch, 8,
                                   psutil_mod=fake_psutil, torch_mod=fake_torch)

        assert "FAILED" in status["affinity"]
        assert "FAILED" in status["priority"]
        assert "FAILED" in status["thread_cap"]


# ---------------------------------------------------------------------------
# Layer status reporting accuracy (QA-3 B2 fix)
# ---------------------------------------------------------------------------

class TestLayerStatusReporting:

    """Small helper object used to keep test setup or expected results organized."""
    def test_all_layers_ok_on_full_system(self, monkeypatch):
        fake_psutil, _ = _make_psutil()
        fake_torch = MagicMock()

        status = _call_reservation(monkeypatch, 16,
                                   psutil_mod=fake_psutil, torch_mod=fake_torch)

        assert status["affinity"] == "OK"
        assert status["priority"] == "OK"
        assert status["thread_cap"] == "OK"

    def test_2core_skips_affinity(self, monkeypatch):
        fake_psutil, _ = _make_psutil()
        fake_torch = MagicMock()

        status = _call_reservation(monkeypatch, 2,
                                   psutil_mod=fake_psutil, torch_mod=fake_torch)

        assert "not enough cores" in status["affinity"]
        assert status["priority"] == "OK"
        fake_torch.set_num_threads.assert_called_once_with(1)
