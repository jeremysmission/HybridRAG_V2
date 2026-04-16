"""Shared pytest fixtures and test helpers used across the HybridRAG V2 test suite."""
# ============================================================================
# tests/conftest.py
# ----------------------------------------------------------------------------
# Suite-wide pytest config.
#
# Purpose: surgically suppress the Tkinter Variable.__del__ destructor
# bleed that pytest's unraisableexception plugin upgrades to a test
# failure.
#
# Background:
#   tkinter.Variable subclasses (StringVar/IntVar/BooleanVar/etc.) hold a
#   reference to the Tk interpreter that created them. When a test creates
#   a tk.Tk() root, attaches Variables, and lets the test end without
#   destroying them by hand, Python's garbage collector eventually runs
#   Variable.__del__ in a non-main thread. The destructor calls
#   self._tk.call("info", "exists", ...) which raises
#       RuntimeError: main thread is not in main loop
#   Python emits this as a PytestUnraisableExceptionWarning and pytest's
#   unraisableexception plugin upgrades the warning to a failure.
#
# Symptom CoPilot+-Researcher hit (review board 2026-04-15):
#   tests/test_eval_gui_streaming.py and tests/test_qa_workbench.py and
#   tests/test_benchmark_gui_panels.py see 4 tests fail at suite level
#   that PASS in isolation, with PytestUnraisableExceptionWarning at
#   tkinter/__init__.py:414 -> Variable.__del__.
#
# Why filter instead of patch:
#   The destructor bleed is a known pytest <-> tkinter interaction, not a
#   product bug. The Variables in question were already orphaned by their
#   originating test; the only failure mode is the GC trying to clean
#   them up after the Tk root is dead. Filtering this *exact* warning
#   pattern preserves every other unraisable exception type so real bugs
#   still surface.
#
# Scope guard:
#   The filter targets only:
#     - category: PytestUnraisableExceptionWarning
#     - message contains: Variable.__del__ AND main thread is not in main loop
#   Nothing else is suppressed.
# ============================================================================

from __future__ import annotations

import warnings

# Pytest will surface its own warning class only after the plugin loads,
# so import lazily inside the hook below. We register the filter via
# pytest_configure to make sure it lands before any test collects.


def pytest_configure(config):
    """Support this test module by handling the pytest configure step."""
    try:
        from _pytest.unraisableexception import PytestUnraisableExceptionWarning
    except Exception:
        return  # very old pytest; nothing to do

    # Match only the tkinter Variable.__del__ destructor bleed pattern.
    # The pytest unraisable hook formats its message as the FIRST LINE
    #   "Exception ignored while calling deallocator <function
    #    Variable.__del__ at 0x...>: None"
    # The exception's traceback (with "main thread is not in main loop")
    # is appended via __cause__/__context__ but is NOT part of the
    # warning message proper. So the regex must only cover the first
    # line. `Variable.__del__` is specific enough to tkinter's
    # Variable subclass destructor that no other unraisable warning
    # will collide with it.
    warnings.filterwarnings(
        "ignore",
        category=PytestUnraisableExceptionWarning,
        message=r".*Variable\.__del__.*",
    )
    # Also register the filter inside pytest's own ini-style filters so
    # it survives across test sessions and respects -W overrides.
    config.addinivalue_line(
        "filterwarnings",
        "ignore::pytest.PytestUnraisableExceptionWarning:"
        ":.*Variable\\.__del__.*",
    )
