# Sprint Slice Aggregation QA Report
Date: 2026-04-19
Tester: Jeremy Randall (QA)
Hardware: primary workstation single GPU
API: none configured during this QA pass

## Environment
- Python: `3.14.3`
- torch: `2.11.0+cu128`
- CUDA: `yes`
- GPU: `NVIDIA NVIDIA workstation GPU`
- API env present: `no`

## Scope
This report covers the deterministic failure-aggregation sprint slice in
`C:\HybridRAG_V2`, with emphasis on:
- boot/config readiness
- deterministic aggregation substrate behavior
- no-LLM degradation behavior
- regression protection
- benchmark validity
- GUI harness stability

It does not claim full live-LLM narration validation because no API/provider
credentials were configured on this machine during the QA pass.

## Executed Checks

### Pillar 1: Boot & Config
- `python scripts/boot.py`
  - PASS
  - Verified:
    - boot completes
    - aggregation attach line present:
      `[OK] Aggregation executor attached (failure_events=35649, with_system=35649)`
    - aggregation-only pipeline assembly line present:
      `[OK] Query pipeline assembled in aggregation-only mode (no LLM)`
- `yaml.safe_load(config/canonical_aliases.yaml)`
  - PASS
  - Verified keys: `systems`, `sites`, `part_number_patterns`

### Pillar 2: Core Pipeline
- No-LLM deterministic path verified through `boot_system()`
  - PASS
  - Verified:
    - `pipeline=True`
    - `generator=False`
    - Q1 returns `AGGREGATION_GREEN`
    - non-aggregation query returns safe `LLM_UNAVAILABLE`
- Live GUI narration with real API key
  - NOT EXECUTED
  - Reason: no API/provider credentials configured in QA environment

### Pillar 3: Regression Tests
- `python -m pytest tests/test_failure_aggregation.py tests/test_aggregation_benchmark_2026_04_15.py tests/test_count_benchmark.py -q`
  - PASS
  - Result: `61 passed in 0.21s`

### Pillar 4: Real Data Pass
- `failure_events.sqlite3` exists and is readable
  - PASS
- Row counts:
  - total: `35649`
  - monitoring system: `26745`
  - legacy monitoring system: `8904`
  - Djibouti: `392`
  - PASS
- Distinct systems:
  - raw: `legacy monitoring system`, `monitoring system`
  - PASS

### Pillar 5: Graceful Degradation
- Missing aliases (simulated path)
  - PASS
  - Behavior: fail closed / passthrough (`result None`)
- Missing substrate (simulated path)
  - PASS
  - Behavior: `RED` with `UNSUPPORTED`
- No LLM configured
  - PASS
  - Deterministic aggregation still works
  - Non-aggregation query returns safe `LLM_UNAVAILABLE`

### Pillar 6: Aggregation Contract
- `python scripts/run_failure_aggregation_benchmark.py`
  - PASS
  - Result: `PASS 16/20`
- Determinism check
  - PASS
  - Q1 top-5 repeated identically across 10 runs
- Filter parsing checks
  - PASS
  - Verified:
    - Q1: `system=monitoring system`, `year=2024`
    - Q2: `system=legacy monitoring system`, `site_token=djibouti`, `year_from=2022`, `year_to=2025`
    - Q3: `YELLOW`, per-year `2019-2025`, rate disclaimer path

### Pillar 7: GUI Harness
- Prebuilt Tier A report
  - PASS
  - `96/96`
- Tier B smart monkey
  - PASS
  - `18/18`
- Tier C dumb monkey
  - PASS
  - `1/1`
- Tier D human non-author smash
  - NOT EXECUTED
  - Reason: requires separate human tester by protocol

### Pillar 8: Headline Preservation / Parallel A-B
- 400-query headline preservation eval
  - NOT EXECUTED in this pass
  - Reason: optional heavier lane / can run overnight
- Dev-lane parity
  - NOT EXECUTED in this pass
  - Reason: outside current primary-lane closeout

### Pillar 9: Sanitizer & Compliance
- `python sanitize_before_push.py`
  - PASS as dry-run invocation
  - Note: docs/dispatch originally referenced `--dry-run`, but the actual CLI
    uses dry-run by default with no flag
- Dry-run result:
  - 2 tracked files would be sanitized before push
  - This is a pre-push hygiene item, not a local runtime blocker

## Key Verified Outcomes
- Deterministic aggregation is active on the primary lane.
- The primary target queries are supported by the backend:
  - Q1 monitoring system 2024: `GREEN`
  - Q2 legacy monitoring system Djibouti 2022-2025: `GREEN`
  - Q3 failure rate x 7 years: `YELLOW` with denominator disclaimer
- Aggregation now survives no-LLM conditions, which was previously a blocker.
- Missing aliases now fails closed instead of producing ambiguous `GREEN` results.
- The substrate no longer exposes blank system rows in the distinct-system check.

## Issues Found
1. Live LLM-backed GUI narration was not tested in this pass because no API key
   or provider endpoint was configured locally.
2. Tier D human smash remains pending because the protocol requires a non-author
   human tester.
3. `sanitize_before_push.py` dry-run indicates 2 tracked files still need
   sanitization before any remote push.

## Verdict
- [ ] PASS — ready for next sprint
- [x] CONDITIONAL — primary deterministic aggregation slice is verified and may advance; remaining items are external/manual/pre-push:
  - live LLM narration check with real API/provider
  - Tier D non-author human smash
  - pre-push sanitization of 2 tracked files
  - optional overnight 400-query headline preservation / parity lane
- [ ] FAIL — blocking issues

Signed: Jeremy Randall (CoPilot+, QA) | HybridRAG_V2 | 2026-04-19 MDT
