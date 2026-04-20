# User Facing GUI Panel

This folder is the working home for the V2 user-facing GUI panel effort.

Purpose:
- keep GUI work organized as its own workstream
- let GUI work advance in parallel with backend substrate work
- preserve a clean user surface while keeping operator controls available
- track V1 feature harvest decisions without cluttering the main repo docs

Current focus:
- chat-style query surface
- admin drawer for power-user controls
- live GUI harness
- cold-start/readiness UX
- citation/source-card UX
- responsive small-window usability

Current status as of 2026-04-20:
- Dev2 GUI Phase 1: QA signed off
- follow-on slices in flight:
  - main-app live harness
  - readiness UX
  - sequential footnote numbering
- Agent D integration pass is expected after the three slices land

Standard harness rule:
- for the main user-facing query panel in Dev2, use the existing standard
  harness:
  - [query_panel_live_harness.py](C:\HybridRAG_V2_Dev2\tools\qa\query_panel_live_harness.py:1)
  - [guiharness_query_panel.bat](C:\HybridRAG_V2_Dev2\guiharness_query_panel.bat:1)
  - [GUI_QA_ENTRYPOINTS.md](C:\HybridRAG_V2_Dev2\GUI_QA_ENTRYPOINTS.md:1)
- do not create a new generic query-panel harness
- extend the standard harness when new query-panel features need coverage

Working rule:
- the default screen should stay simple
- advanced knobs belong behind an admin/operator surface unless they directly help normal users

Folder layout:
- [planning/SPRINT_SLICE_USER_FACING_GUI_PANEL_2026-04-20.md](C:\HybridRAG_V2\workstreams\user_facing_gui_panel\planning\SPRINT_SLICE_USER_FACING_GUI_PANEL_2026-04-20.md)
- [planning/BACKLOG_2026-04-20.md](C:\HybridRAG_V2\workstreams\user_facing_gui_panel\planning\BACKLOG_2026-04-20.md)
- [qa/QA_CHECKLIST_2026-04-20.md](C:\HybridRAG_V2\workstreams\user_facing_gui_panel\qa\QA_CHECKLIST_2026-04-20.md)
- [reference/V1_HARVEST_NOTES_2026-04-20.md](C:\HybridRAG_V2\workstreams\user_facing_gui_panel\reference\V1_HARVEST_NOTES_2026-04-20.md)
- [handoffs/README.md](C:\HybridRAG_V2\workstreams\user_facing_gui_panel\handoffs\README.md)

Recommended ownership:
- one GUI owner
- one harness/QA automation owner
- one polish/readiness owner
- one integrator only after slice QA is complete

Success criteria:
- clean user-facing layout
- no loss of backend wiring correctness
- real-hardware GUI QA
- repeatable button-smash / human-use regression coverage
- stable resize behavior
- evidence-bearing citations and source cards
- clear ready/degraded boot messaging
