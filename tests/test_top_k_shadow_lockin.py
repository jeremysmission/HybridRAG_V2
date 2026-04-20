"""Test module for the top k shadow lockin behavior. The checks here explain what the repository expects to keep working."""
# ============================================================================
# tests/test_top_k_shadow_lockin.py
# ----------------------------------------------------------------------------
# Lock-in for Finding #1 from RETRIEVAL_KNOB_WIRING_AUDIT_ADDENDUM_2026-04-15.md.
#
# Status: documented bug, NOT yet patched in this session.
# Owner of the patch: needs explicit CoPilot+ Max routing because the fix touches
# scripts/run_production_eval.py and src/gui/eval_panels/runner.py, both of
# which are inside reviewer / coder territory and outside the Claudex Coder
# regression-fixture lane scope.
#
# What the bug is, in one sentence:
#   `scripts/run_production_eval.py` defines a module-level constant
#   `TOP_K = 5` and uses it for both the production eval CLI and the GUI eval
#   runner (which imports it as `rpe.TOP_K`), shadowing `config.retrieval.top_k`
#   (which is 10). Every baseline run recorded today therefore used top_k=5,
#   not top_k=10.
#
# Why these tests are valuable today even though the bug is not yet patched:
#   - The DESCRIBE test (xfail with strict=True) records the exact divergence,
#     including the live values, so any future reader running the test suite
#     immediately sees the shadow + the file:line where it lives.
#   - The PROVENANCE test (always-pass) asserts that the addendum file exists
#     on disk and the relevant code lines still match the addendum's claim,
#     so if either side rotates the test will fail and force a re-audit.
#   - When the patch lands (whichever option), simply remove `xfail` from the
#     describe test and it becomes a regression guard for the fix.
# ============================================================================

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDENDUM_PATH = (
    Path(f"C:/Users/{os.environ.get('USERNAME') or Path.home().name}/HYBRIDRAG_LOCAL_ONLY")
    / "RETRIEVAL_KNOB_WIRING_AUDIT_ADDENDUM_2026-04-15.md"
)


def _config_top_k() -> int:
    """Support this test module by handling the config top k step."""
    cfg_path = REPO_ROOT / "config" / "config.yaml"
    with cfg_path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return int(cfg["retrieval"]["top_k"])


def _module_top_k() -> int:
    """Support this test module by handling the module top k step."""
    import scripts.run_production_eval as rpe  # type: ignore

    return int(rpe.TOP_K)


def test_provenance_addendum_exists():
    """The addendum that documents this finding must still be on disk.

    If a sweep moves or deletes it, this test fails and forces a re-audit
    rather than letting the lock-in become orphaned context.
    """
    assert ADDENDUM_PATH.exists(), ADDENDUM_PATH


def test_provenance_module_constant_still_present():
    """run_production_eval still defines the TOP_K module constant."""
    src = (REPO_ROOT / "scripts" / "run_production_eval.py").read_text(
        encoding="utf-8"
    )
    assert "TOP_K =" in src, "TOP_K constant removed; re-audit shadow finding"


def test_provenance_runner_imports_rpe_top_k():
    """eval_panels/runner.py still imports TOP_K from run_production_eval.

    If this import is removed, the shadow may have already been fixed; the
    test forces re-evaluation rather than silently passing.
    """
    runner = (REPO_ROOT / "src" / "gui" / "eval_panels" / "runner.py").read_text(
        encoding="utf-8"
    )
    # The addendum cites this exact import shape.
    assert "TOP_K" in runner, "runner.py no longer references TOP_K; re-audit"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN: production_eval TOP_K constant shadows config.retrieval.top_k. "
        "Patch lane needs explicit CoPilot+ Max routing -- touches "
        "scripts/run_production_eval.py and src/gui/eval_panels/runner.py "
        "(reviewer territory). Documented in "
        "RETRIEVAL_KNOB_WIRING_AUDIT_ADDENDUM_2026-04-15.md Finding #1."
    ),
)
def test_top_k_does_not_shadow_config():
    """Desired-state contract: production eval must honor config.retrieval.top_k.

    Currently fails (xfail strict). When the patch lands, drop xfail and this
    test becomes a regression guard against re-introducing the shadow.
    """
    assert _module_top_k() == _config_top_k(), (
        "production eval TOP_K={} but config retrieval.top_k={}".format(
            _module_top_k(), _config_top_k()
        )
    )
