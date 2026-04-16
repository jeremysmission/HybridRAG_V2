"""Test module for the context builder reranker init behavior. The checks here explain what the repository expects to keep working."""
# ============================================================================
# tests/test_context_builder_reranker_init.py
# ----------------------------------------------------------------------------
# Lock-in for Finding #2 from RETRIEVAL_KNOB_WIRING_AUDIT_ADDENDUM_2026-04-15.md:
# silent FlashRank construction failure at src/query/context_builder.py.
#
# Before the fix, ContextBuilder.__init__ swallowed any FlashRank construction
# error with `except Exception: pass`, leaving operators with no signal that
# reranking was disabled. The fix:
#   - logs a WARNING with the exception message
#   - exposes a `reranker_active` property so callers / tests can verify state
#
# These tests assert both behaviors AND assert the silent-fail path is gone.
# ============================================================================

from __future__ import annotations

import logging

import pytest

from src.query import context_builder as cb_mod
from src.query.context_builder import ContextBuilder


class _BoomReranker:
    """Small helper object used to keep test setup or expected results organized."""
    def __init__(self, *args, **kwargs):
        raise RuntimeError("flashrank model not on disk")


def test_reranker_construction_failure_logs_warning(monkeypatch, caplog):
    """Verify that reranker construction failure logs warning behaves the way the team expects."""
    monkeypatch.setattr(cb_mod, "FlashReranker", _BoomReranker)

    with caplog.at_level(logging.WARNING, logger="src.query.context_builder"):
        builder = ContextBuilder(top_k=10, reranker_enabled=True)

    assert builder.reranker_active is False
    # The warning must mention the underlying error so operators know what failed.
    assert any(
        "FlashRank" in record.message and "flashrank model not on disk" in record.message
        for record in caplog.records
    ), [r.message for r in caplog.records]


def test_reranker_construction_failure_does_not_raise(monkeypatch):
    """Verify that reranker construction failure does not raise behaves the way the team expects."""
    monkeypatch.setattr(cb_mod, "FlashReranker", _BoomReranker)
    # Construction must not propagate the exception; reranking is best-effort.
    ContextBuilder(top_k=10, reranker_enabled=True)


def test_reranker_disabled_does_not_log(monkeypatch, caplog):
    """Verify that reranker disabled does not log behaves the way the team expects."""
    monkeypatch.setattr(cb_mod, "FlashReranker", _BoomReranker)

    with caplog.at_level(logging.WARNING, logger="src.query.context_builder"):
        builder = ContextBuilder(top_k=10, reranker_enabled=False)

    assert builder.reranker_active is False
    # When disabled by config, we never attempt construction, so no warning.
    assert all("FlashRank" not in r.message for r in caplog.records)


def test_reranker_active_property_when_construction_succeeds(monkeypatch):
    """Verify that reranker active property when construction succeeds behaves the way the team expects."""
    class _OkReranker:
        def __init__(self, *args, **kwargs):
            pass

        def rerank(self, query, results, top_n):
            return results[:top_n]

    monkeypatch.setattr(cb_mod, "FlashReranker", _OkReranker)
    builder = ContextBuilder(top_k=10, reranker_enabled=True)
    assert builder.reranker_active is True


def test_silent_fail_path_is_gone():
    """Source-level guard: bare `except Exception:\\n        pass` must not
    return for the reranker init block. If a future refactor reintroduces it,
    this test fails fast."""
    import inspect

    source = inspect.getsource(ContextBuilder.__init__)
    # The fix replaces `pass` with a logger.warning call.
    assert "logger.warning" in source
    # And the silent-pass form must be gone from this method.
    normalized = "\n".join(line.rstrip() for line in source.splitlines())
    assert "except Exception:\n                pass" not in normalized
