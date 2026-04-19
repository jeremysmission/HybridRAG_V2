# Count Benchmark Run Note 2026-04-15

## Purpose

Turn the tranche-1 count audit into a repeatable benchmark lane for high-specificity targets.

This lane is intentionally narrow:
- benchmark-ready first
- high-specificity identifiers/entities first
- ambiguous acronym and alias families held back unless explicitly included

## Benchmark Inputs

- Frozen target lane:
  - `C:\HybridRAG_V2\tests\golden_eval\count_benchmark_targets_2026-04-15.json`
- Runner:
  - `C:\HybridRAG_V2\scripts\count_benchmark.py`

Count modes are explicit:
- `raw_mentions`
- `unique_documents`
- `unique_chunks`
- `unique_rows`

Deterministic surfaces are explicit:
- `chunk_exact`
- `entity_exact`
- `row_exact`

## Default lane

Default behavior uses only the audited tranche-1 targets:
- `Eareckson Air Station, Shemya, AK`
- `Pituffik Space Base`
- `IGSI-754`
- `IGSI-755`
- `IGSI-1803`
- `IGSI-1804`
- `IGSI-1805`

Deferred targets stay out of the headline lane unless `--include-deferred` is set.

## Commands

Dry run:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\count_benchmark.py --dry-run
```

Deterministic benchmark run:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\count_benchmark.py --output-dir tests\golden_eval\results\count_benchmark
```

Score model predictions against the deterministic baseline:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\count_benchmark.py `
  --predictions-json tests\golden_eval\results\count_benchmark\sample_predictions.json `
  --output-dir tests\golden_eval\results\count_benchmark
```

## Prediction JSON shape

Accepted shapes:

```json
{
  "predictions": [
    {
      "target": "IGSI-754",
      "counts": {
        "raw_mentions": 28,
        "unique_documents": 20,
        "unique_chunks": 26,
        "unique_rows": 0
      }
    }
  ]
}
```

The runner also accepts:
- `results` instead of `predictions`
- row objects with the four count modes at top level instead of nested under `counts`

## Outputs

Each run writes:
- one JSON artifact
- one markdown artifact

Both include:
- selected target count
- active store paths
- deterministic counts
- frozen expectation verification
- prediction exact-match summary if `--predictions-json` is supplied

## Current v1 recommendation

- Green for `IGSI-*`-style identifiers as the first benchmark-ready family
- Yellow for exact site phrases with known duplication pressure
- Red for alias-bearing families in the headline lane until alias policy is frozen
