# Query Panel Live Harness

Real-mode QA harness for the main `HybridRAGApp` query surface.

## Command

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe tools\qa\query_panel_live_harness.py --mode real
```

Or:

```powershell
C:\HybridRAG_V2\guiharness_query_panel.bat
```

The harness normalizes its working directory to `PROJECT_ROOT` at startup, so
relative-resource behavior is not dependent on the caller's current shell
location.

## What It Checks

1. Real GUI boot and Ask readiness timing
2. Default clean query-panel view
3. Admin drawer open/close visibility
4. Live semantic query surface:
   `What is CDRL A002?`
5. Live aggregation query surface:
   `top 5 failing parts in NEXION in 2024`
6. Source toggle / Stop safety
7. Tk callback exception capture
8. Background thread exception capture

## Artifacts

Per run, the harness writes:

- `output/query_panel_live_harness_<timestamp>/query_panel_live_harness_report.json`
- `output/query_panel_live_harness_<timestamp>/query_panel_live_harness.log`

## Exit Codes

- `0` = all checks passed
- `2` = one or more checks failed

## Notes

- The harness is intentionally strict. If the app silently routes an aggregation
  query down generic `AGGREGATE` instead of deterministic `AGGREGATION_GREEN`,
  the run fails.
- Footnote verification checks that a clickable footnote tag exists. In
  automation, Tk text-tag click synthesis can be unreliable on a disabled
  `Text` widget, so the harness falls back to the bound scroll/highlight path
  after confirming the click binding exists.

