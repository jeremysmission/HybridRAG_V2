# Aggregation Benchmark Run Note — 2026-04-15

Pack:
- `tests/aggregation_benchmark/aggregation_seed_manifest_2026-04-15.json`

What this lane does:
- loads a frozen aggregation seed manifest
- scores candidate answers against the exact-count rules in the manifest
- treats the full set as a promotion gate: all items must pass

How to run:
1. Self-check the frozen seed set:
   `python scripts/run_aggregation_benchmark_2026_04_15.py`
2. Score a candidate answer file:
   `python scripts/run_aggregation_benchmark_2026_04_15.py --answers-file path\\to\\answers.json`
3. Override the output report path if needed:
   `python scripts/run_aggregation_benchmark_2026_04_15.py --answers-file path\\to\\answers.json --output path\\to\\aggregation_report.json`

Expected answer file shape:
- JSON object: `{ "AGG-001": 76, "AGG-002": 39, ... }`
- or JSON array of objects: `[{"id":"AGG-001","answer":76}, ...]`

Validation:
- `python -m pytest -q tests/test_aggregation_benchmark_2026_04_15.py`

Notes:
- This is intentionally narrow and deterministic.
- The runner does not inspect the live corpus; it only scores answers against the frozen manifest.
- The gate is strict by default: one miss fails the lane.
