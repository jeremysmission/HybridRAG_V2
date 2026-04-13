# Clean Store 400 Eval Runbook 2026-04-13

## Purpose

Run the 400-query production baseline against the isolated clean Tier 1
store without overwriting the current live-store baseline artifacts.

## Preconditions

- Clean Tier 1 isolated rerun completed successfully
- Clean config exists:
  - `config/config.tier1_clean_2026-04-13.yaml`
- Clean store paths exist:
  - `data/index/clean/tier1_clean_20260413/entities.sqlite3`
  - `data/index/clean/tier1_clean_20260413/relationships.sqlite3`

## Commands

### 1. Run the 400-query baseline against the clean config

```powershell
cd C:\HybridRAG_V2
$env:CUDA_VISIBLE_DEVICES='1'
.\.venv\Scripts\python.exe scripts\run_production_eval.py `
  --queries tests\golden_eval\production_queries_400_2026-04-12.json `
  --config config\config.tier1_clean_2026-04-13.yaml `
  --results-json docs\production_eval_results_clean_tier1_2026-04-13.json `
  --report-md docs\PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md
```

### 2. Optional rebuild of the markdown report from saved JSON

```powershell
cd C:\HybridRAG_V2
$env:CUDA_VISIBLE_DEVICES='1'
.\.venv\Scripts\python.exe scripts\run_production_eval.py `
  --rebuild-report `
  --results-json docs\production_eval_results_clean_tier1_2026-04-13.json `
  --report-md docs\PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md
```

## Output Artifacts

- `docs/production_eval_results_clean_tier1_2026-04-13.json`
- `docs/PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md`

## Notes

- This path uses the isolated clean Tier 1 entity store through the clean
  config file.
- It does **not** overwrite the existing live-store baseline outputs.
- The runner now supports:
  - `--config`
  - `--results-json`
  - `--report-md`
- Use this runbook only after the clean Tier 1 run is complete.
