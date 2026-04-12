"""
Regression test for HybridRAG V2 critical install dependencies.

Mirrors ``scripts/verify_install.py`` — if the verify script would fail,
this test should fail too. That way a broken install can be caught by
``pytest`` in CI or a local run, not only by a manual verify invocation.

The test asserts:

  1. Every critical import in ``CRITICAL_IMPORTS`` is importable.
  2. ``lancedb.LanceQueryBuilder.to_batches`` exists — this is the
     streaming API contract the Tier 2 memory fix (commit 8a1531b)
     depends on. A lancedb downgrade that removes it would silently
     break extraction at scale; this test makes it loud.
  3. ``scripts.verify_install`` itself is importable and exposes the
     contract functions that the installer batch file relies on.

Deliberately NOT checked: pylance. It is not a dependency. See
``docs/CRITICAL_PYLANCE_INSTALL_REQUIRED_2026-04-11.md`` for the
history — the build-in ``SearchBuilder.to_batches`` API replaces it.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from scripts.verify_install import (  # noqa: E402
    CRITICAL_IMPORTS,
    check_one,
    main as verify_main,
)


# ---------------------------------------------------------------------------
# Per-package import checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "display,import_name",
    [(d, n) for d, n, _ in CRITICAL_IMPORTS],
    ids=[d for d, _, _ in CRITICAL_IMPORTS],
)
def test_critical_import(display, import_name):
    """Every critical package must import cleanly."""
    mod = importlib.import_module(import_name)
    assert mod is not None
    # Not asserting a specific version — requirements.txt is the source
    # of truth there. We just need the module to exist.


# ---------------------------------------------------------------------------
# lancedb streaming API contract — the key guard for Tier 2 memory fix
# ---------------------------------------------------------------------------


def test_lancedb_streaming_api_contract():
    """``LanceQueryBuilder.to_batches`` must be present and callable.

    The Round 3 fix in scripts/tiered_extract.py:iter_chunk_batches uses
    ``tbl.search().select(...).limit(...).to_batches(batch_size)`` as
    the bounded-memory streaming path. If a future lancedb version drops
    this method, extraction will raise RuntimeError by the module-level
    ``_assert_streaming_api_available`` guard — but we want to catch it
    in CI before it ships.
    """
    import lancedb
    from lancedb.query import LanceQueryBuilder

    assert hasattr(LanceQueryBuilder, "to_batches"), (
        f"lancedb {lancedb.__version__} does not expose "
        f"LanceQueryBuilder.to_batches. Upgrade required: "
        f"pip install --upgrade 'lancedb>=0.30.1'"
    )


def test_verify_install_reports_all_ok(capsys):
    """End-to-end: scripts/verify_install.py returns 0 on a healthy venv.

    This also asserts the script's printed contract — each dependency
    emits either ``[OK]`` or a failure marker, and the final result
    line names the count.
    """
    exit_code = verify_main()
    captured = capsys.readouterr()
    assert exit_code == 0, f"verify_install failed:\n{captured.out}"
    # Every critical import should have an [OK] line.
    for display, _, _ in CRITICAL_IMPORTS:
        assert f"[OK]" in captured.out and display in captured.out, (
            f"Missing [OK] line for {display} in verify_install output"
        )


def test_check_one_helper_shape():
    """The per-package helper returns (bool, str) and the OK line format
    matches what the installer batch file greps for."""
    ok, line = check_one("numpy", "numpy", None)
    assert ok is True
    assert line.startswith("[OK]")
    assert "numpy" in line


def test_check_one_handles_missing():
    """A clearly-missing module returns a MISSING line and ok=False."""
    ok, line = check_one(
        "definitely_not_a_real_module",
        "definitely_not_a_real_module_xyzzy_12345",
        None,
    )
    assert ok is False
    assert "[MISSING]" in line


# ---------------------------------------------------------------------------
# Spec pin — order + membership matters for the installer's step output
# ---------------------------------------------------------------------------


def test_critical_imports_spec_membership():
    """Pin the list of critical dependencies so drift is caught.

    If a new required dep is added (e.g., a new LLM client), append it
    to both ``CRITICAL_IMPORTS`` in verify_install.py AND update this
    test. Dropping a dep requires removing it here too.
    """
    names = {d for d, _, _ in CRITICAL_IMPORTS}
    expected = {
        "torch",
        "numpy",
        "pyarrow",
        "lancedb",
        "sentence_transformers",
        "gliner",
        "openai",
        "fastapi",
        "lxml",
    }
    assert names == expected, (
        f"CRITICAL_IMPORTS drifted. Expected {expected}, got {names}"
    )
    # Pylance deliberately NOT in the expected set. If anyone adds it,
    # this test fails and the SUPERSEDED doc should be reread first.
    assert "lance" not in names
    assert "pylance" not in names
