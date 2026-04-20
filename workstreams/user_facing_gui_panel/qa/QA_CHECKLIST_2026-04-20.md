# QA Checklist: User Facing GUI Panel

Date: 2026-04-20

## Core Rules
- Test on the real main app surface, not only QA Workbench.
- Use real hardware whenever possible.
- Exact command, exact output, PASS/FAIL, and why.
- No GUI slice is done until live interaction is verified.
- For the main query surface, start with the standard harness:
  - [query_panel_live_harness.py](C:\HybridRAG_V2_Dev2\tools\qa\query_panel_live_harness.py:1)
  - [guiharness_query_panel.bat](C:\HybridRAG_V2_Dev2\guiharness_query_panel.bat:1)
- Do not create a new generic main query-panel harness unless the GUI surface is
  genuinely different.

## Required Checks

### 1. Boot
- launcher opens without Tk traceback
- ready/degraded state is visible
- Ask is disabled until the pipeline is real

### 2. Default User Surface
- question entry visible
- Ask and Stop visible
- answer area visible
- sources toggle visible
- metrics line visible
- admin-only controls hidden by default

### 3. Admin Drawer
- opens and closes reliably
- advanced controls appear there
- does not break layout

### 4. Semantic Query
- answer renders
- citations appear
- clickable citation behavior works
- source cards expand and highlight correctly

### 5. Aggregation Query
- deterministic aggregation still renders correctly
- tier formatting preserved
- table formatting preserved
- no regression in query path or confidence

### 6. Interaction Safety
- repeated toggle clicks do not crash
- repeated Stop clicks do not crash
- copy actions work
- feedback actions work

### 7. Resize / Small Window
- important controls remain reachable
- right-side scrolling remains usable
- long answers and long source lists stay navigable

### 8. Regression
- scoped pytest still passes
- no import breakage

## Suggested Core Queries
- `What is CDRL A002?`
- `top 5 failing parts in NEXION in 2024`

## Evidence to Capture
- startup command and logs
- harness report
- exact query path / confidence
- callback exception count
- screenshot set if doing manual pass

## Banked Promotion Suggestion
For major GUI slices, require:
- isolated slice QA
- integrated bundle QA
- resize/smash pass
- no callback exceptions
