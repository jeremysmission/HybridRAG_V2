# GUI QA Entrypoints

This file exists to stop harness sprawl.

For the main user-facing query panel in `HybridRAG_V2`, the standard QA
harness is:

- [tools/qa/query_panel_live_harness.py](C:\HybridRAG_V2\tools\qa\query_panel_live_harness.py:1)

Standard launcher:

- [guiharness_query_panel.bat](C:\HybridRAG_V2\guiharness_query_panel.bat:1)

Companion documentation:

- [docs/qa/QUERY_PANEL_LIVE_HARNESS.md](C:\HybridRAG_V2\docs\qa\QUERY_PANEL_LIVE_HARNESS.md:1)
- [tools/qa/README.md](C:\HybridRAG_V2\tools\qa\README.md:1)

## Rule

Do not create a new generic main query-panel harness.

If a future GUI feature needs new coverage, extend
`tools/qa/query_panel_live_harness.py` unless the new work is on a genuinely
different GUI surface.

## Why This Harness Is The Standard

It already exercises the real `HybridRAGApp` user-facing query surface and is
meant to catch the kinds of issues that manual spot checks miss:

- boot/readiness timing on the real app
- default clean user surface
- admin drawer behavior
- semantic query rendering
- deterministic aggregation rendering
- footnote/source-card wiring
- repeated toggle/Stop interaction
- callback/thread exceptions

That makes it more than a launcher. It is the repeatable button-smash and
human-use regression harness for the main chat-style query panel.

## Related Harness

- [tools/qa/gui_button_smash_harness.py](C:\HybridRAG_V2\tools\qa\gui_button_smash_harness.py:1)

Keep using that only when you explicitly need the older QA Workbench or broader
multi-surface smash behavior. It is not the default harness for the main user
query panel.


