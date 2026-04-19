# RAGAS Execution Plan — 2026-04-12

Scope: clean-store retrieval-side RAGAS execution lane only.

## Supported Now

`scripts/run_ragas_eval.py` is designed to support the current corpus safely without editing the live 400-query JSON.

Current supported metric lane:

- Retrieval-side non-LLM context metrics on queries that already have `reference_contexts`
- Readiness analysis for the full corpus, including explicit skip reasons for ineligible rows
- Execution intentionally uses the local hybrid retrieval path only; it does not call the router, `LLMClient`, or structured retrieval stores

Current required fields for retrieval-side execution:

- `query_id` or `id`
- `user_input` or `query`
- `reference_contexts`

Current required fields for full Phase 2C readiness / broader answer-based metrics:

- `reference`
- Generated `response` from the app path
- Evaluator dependencies beyond the current non-LLM retrieval lane

## What The Runner Does

1. Loads `tests/golden_eval/production_queries_400_2026-04-12.json`
2. Reports:
   - queries eligible now for retrieval-side RAGAS
   - queries blocked on missing Phase 2C enrichment
   - skip counts by reason
3. If `ragas` is installed, attempts retrieval-side non-LLM metrics on the eligible subset
4. If `ragas` is missing, exits cleanly after reporting the blocker

Current helper for live backfill targeting:

- `python scripts/report_phase2c_backfill_targets.py`
- This reports the current live counts and recommended Phase 2C targets so the backfill guidance does not go stale when the 400-query corpus changes

## Still Blocked On Phase 2C

Queries without `reference_contexts` are not ready for retrieval-side context precision / recall.

Queries without `reference` are also not ready for answer-based metrics such as faithfulness or answer correctness, even after the retrieval lane is wired.

## Local Dependency Notes

As probed on 2026-04-12 late evening in the project venv:

- `ragas` is not installed
- `rapidfuzz` is not installed

Official RAGAS references used for the runner design:

- Evaluation sample / `SingleTurnSample`: https://docs.ragas.io/en/stable/concepts/components/eval_sample/
- Evaluation dataset: https://docs.ragas.io/en/stable/concepts/components/eval_dataset/
- Non-LLM context recall: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/
- Non-LLM context precision with reference contexts: https://docs.ragas.io/en/v0.4.0/concepts/metrics/available_metrics/context_precision/
