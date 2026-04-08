# Golden Eval Test Data

All golden eval data consolidated here for easy access.

## V2 Active (used by `run_golden_eval.py`)

| File | Count | Description |
|------|-------|-------------|
| `golden_queries.json` | 30 | V2 golden queries (25 original + 5 edge cases) |
| `golden_tuning_400.json` | 400 | 400-question tuning corpus across 7 roles |

## V2 Results (from `run_golden_eval.py`)

| Dir | Content |
|-----|---------|
| `results/` | Run results (latest.json, sprint eval JSONs, rebuild reports) |

## 3-Tier Test Corpus (in `tests/test_corpus/`)

| Tier | Files | Golden Queries |
|------|-------|---------------|
| `tier1_smoke/` | Clean enterprise program maintenance docs | `golden_queries_tier1.json` |
| `tier2_stress/` | Messy OCR, email chains, fragments | `golden_queries_tier2.json` |
| `tier3_negative/` | Empty, binary, injection, foreign | `golden_queries_tier3.json` |

## V1 Reference (historical, read-only)

| File | Description |
|------|-------------|
| `v1_reference/golden_baseline_24.json` | V1 24-question baseline |
| `v1_reference/golden_dataset_v2.json` | V1 20-question dataset |
| `v1_reference/golden_tuning_400.json` | V1 copy of 400-question corpus |
| `v1_reference/golden_eval_results_2026-03-24.json` | V1 eval results |
| `v1_reference/golden_probe_checks.py` | V1 hallucination probe code |
| `v1_reference/golden_probes_hallucination.py` | V1 hallucination guard probes |
| `v1_reference/quality_probe_pack_2026-03-18.json` | V1 quality probe queries |
| `v1_reference/new_format_corpus_tests_2026-03-23.json` | V1 format coverage tests |
| `v1_reference/role_query_matrix_2026-03-19.md` | V1 role x query type matrix |
| `v1_reference/v1_grounding_results.jsonl` | V1 grounding eval results |
| `v1_reference/v1_scored_results.jsonl` | V1 scored eval results |
| `v1_reference/golden_baseline_source/` | 9 source docs for V1 baseline |

## 400-Question Corpus Breakdown

| Role | Count | Types |
|------|-------|-------|
| CAD | 61 | answerable, ambiguous, unanswerable, injection |
| Logistics Analyst | 60 | answerable, ambiguous, unanswerable, injection |
| Systems Administrator | 58 | answerable, ambiguous, unanswerable, injection |
| Field Engineer | 57 | answerable, ambiguous, unanswerable, injection |
| Program Manager | 57 | answerable, ambiguous, unanswerable, injection |
| Engineer | 55 | answerable, ambiguous, unanswerable, injection |
| Cybersecurity | 52 | answerable, ambiguous, unanswerable, injection |

Query types: 278 answerable, 59 unanswerable, 41 injection, 22 ambiguous
