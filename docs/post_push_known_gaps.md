# Post-Push Known Gaps

## Intentional XFail

- `tests/test_top_k_shadow_lockin.py::test_top_k_does_not_shadow_config`
  - Status: `xfail(strict=True)`
  - Rationale: this is a documented lock-in for the still-open `TOP_K=5` shadowing issue in `scripts/run_production_eval.py` / `src/gui/eval_panels/runner.py`.
  - Current behavior: the provenance guards for the finding pass; the divergence test remains intentionally xfailed until the retrieval knob patch lands in its own lane.
