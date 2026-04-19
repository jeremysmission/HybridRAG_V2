# Count Benchmark Lane 2026-04-15

This lane freezes the tranche-1 count-audit target set and makes count mode explicit.

## Files

- `scripts/count_benchmark.py`
- `tests/golden_eval/count_benchmark_targets_2026-04-15.json`

## Modes

- `raw_mentions`
- `unique_documents`
- `unique_chunks`
- `unique_rows`

## Surfaces

- `chunk_exact`
- `entity_exact`
- `row_exact`

## Default Lane

The script defaults to the audited high-specificity tranche and skips deferred targets unless `--include-deferred` is set.

## Example

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\count_benchmark.py --dry-run
```

For a full run with artifacts:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\count_benchmark.py --output-dir tests\golden_eval\results\count_benchmark
```
