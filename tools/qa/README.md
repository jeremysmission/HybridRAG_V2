# QA Harnesses

This folder holds reusable GUI QA harnesses.

## Primary Standard For Main Query Panel

For the main user-facing query surface in `HybridRAG_V2`, use:

- [query_panel_live_harness.py](C:\HybridRAG_V2\tools\qa\query_panel_live_harness.py:1)

Run it with:

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe tools\qa\query_panel_live_harness.py --mode real
```

Or:

```powershell
C:\HybridRAG_V2\guiharness_query_panel.bat
```

## Standard Usage Rule

Do not add another generic harness for the main query panel.

When query-panel features change, extend `query_panel_live_harness.py` with the
new checks instead of creating a parallel harness.

## What The Standard Harness Covers

- real `HybridRAGApp` boot and Ask readiness
- clean default user surface
- admin drawer visibility
- semantic query path checks
- deterministic aggregation query checks
- footnote and source-card behavior
- repeated toggle/Stop button smashing
- callback/thread exception capture
- JSON and log artifact generation

## Other Harness In This Folder

- [gui_button_smash_harness.py](C:\HybridRAG_V2\tools\qa\gui_button_smash_harness.py:1)

That harness is useful for older QA Workbench or broader chaos-style GUI
exercises. It is not the default starting point for main query-panel work.


