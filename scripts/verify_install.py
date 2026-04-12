"""
Critical-imports sanity check for HybridRAG V2.

Purpose
-------
Fresh V2 installs on a new workstation can silently end up missing a
critical package or landing on a bad version. The previous failure mode
was a missing ``lance`` package that forced ``iter_chunk_batches`` to
silently fall back to the full-materialize ``load_chunks`` path and
OOM at 10M+ chunks. The Round 3 streaming fix (commit 8a1531b) removed
that silent fallback, but we still need a proactive check so operators
can confirm a fresh install is healthy BEFORE running extraction.

This script imports every hard dependency the extraction + query paths
rely on and prints a clear per-package status line. For ``lancedb`` it
additionally verifies that ``LanceQueryBuilder.to_batches`` is present —
that single method is the streaming API contract the Tier 2 memory fix
depends on. If a lancedb downgrade ever slipped into the wheel cache,
this check would catch it.

Usage
-----
    .venv\\Scripts\\python.exe scripts\\verify_install.py

Exit codes
----------
    0  All critical imports present and healthy
    1  One or more critical imports missing or version-drifted

The installer batch files (INSTALL_CUDA_TORCH_WORKSTATION.bat) call
this script as their final step so a broken install surfaces with a
clear message instead of at runtime during a demo.

Not checked here
----------------
    - pylance: intentionally NOT a dependency. lancedb's own
      SearchBuilder.to_batches replaces it entirely. Adding it back
      to requirements.txt or probing for it would re-introduce the
      false alarm this doc dead-ended on. See
      docs/CRITICAL_PYLANCE_INSTALL_REQUIRED_2026-04-11.md.
    - Optional dev tooling (pytest, black, etc.) — those don't affect
      runtime correctness.
"""

from __future__ import annotations

import importlib
import sys
from typing import Callable


# ---------------------------------------------------------------------------
# Critical import spec
# ---------------------------------------------------------------------------
#
# Each entry is (display_name, import_name, extra_check).
# extra_check is an optional callable that takes the imported module and
# returns None on success or a string describing the failure.
#
# Keep this list in sync with requirements.txt. Order matters only for
# output readability — checks do not depend on each other.

def _check_lancedb_streaming_api(mod) -> str | None:
    """Confirm the LanceQueryBuilder.to_batches contract the Round 3
    Tier 2 memory fix depends on."""
    try:
        from lancedb.query import LanceQueryBuilder
    except ImportError as e:
        return f"lancedb.query.LanceQueryBuilder not importable ({e})"
    if not hasattr(LanceQueryBuilder, "to_batches"):
        return (
            "LanceQueryBuilder.to_batches missing — "
            "streaming chunk iteration will raise. "
            "Upgrade: pip install --upgrade 'lancedb>=0.30.1'"
        )
    return None


CRITICAL_IMPORTS: list[tuple[str, str, Callable | None]] = [
    ("torch", "torch", None),
    ("numpy", "numpy", None),
    ("pyarrow", "pyarrow", None),
    ("lancedb", "lancedb", _check_lancedb_streaming_api),
    ("sentence_transformers", "sentence_transformers", None),
    ("gliner", "gliner", None),
    ("openai", "openai", None),
    ("fastapi", "fastapi", None),
    ("lxml", "lxml", None),
]


def _get_version(mod) -> str:
    for attr in ("__version__", "VERSION", "version"):
        v = getattr(mod, attr, None)
        if v is None:
            continue
        if callable(v):
            try:
                return str(v())
            except Exception:
                continue
        return str(v)
    return "?"


def check_one(display: str, import_name: str, extra_check: Callable | None) -> tuple[bool, str]:
    """Return (ok, status_line) for a single dependency."""
    try:
        mod = importlib.import_module(import_name)
    except ImportError as e:
        return False, f"[MISSING] {display:25s} — {e}"
    except Exception as e:  # pragma: no cover — catches bad installs
        return False, f"[BROKEN]  {display:25s} — {type(e).__name__}: {e}"

    version = _get_version(mod)

    if extra_check is not None:
        extra_result = extra_check(mod)
        if extra_result is not None:
            return False, f"[FAIL]    {display:25s} {version} — {extra_result}"

    return True, f"[OK]      {display:25s} {version}"


def main() -> int:
    print("=" * 60)
    print("  HybridRAG V2 — Critical Install Verification")
    print("=" * 60)
    print()

    all_ok = True
    lines: list[str] = []
    for display, import_name, extra in CRITICAL_IMPORTS:
        ok, line = check_one(display, import_name, extra)
        lines.append(line)
        print(line)
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print(f"  Result: [PASS] {len(CRITICAL_IMPORTS)} critical dependencies OK.")
        print("=" * 60)
        return 0

    missing = [l for l in lines if not l.startswith("[OK]")]
    print(f"  Result: [FAIL] {len(missing)} of {len(CRITICAL_IMPORTS)} checks failed.")
    print()
    print("  Recovery:")
    print("    .venv\\Scripts\\pip.exe install -r requirements.txt")
    print()
    print("  If a specific package needs a version bump (e.g. lancedb for")
    print("  the to_batches streaming API), install it directly:")
    print("    .venv\\Scripts\\pip.exe install --upgrade 'lancedb>=0.30.1'")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
