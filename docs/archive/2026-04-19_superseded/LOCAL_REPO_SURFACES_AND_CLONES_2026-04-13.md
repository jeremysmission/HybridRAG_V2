# Local Repo Surfaces And Clones 2026-04-13

## Purpose

This is the primary workstation-local inventory of repo surfaces that a coordinator might
mistake for valid scratch space.

The point is to stop future coordinators from assuming every `_Dev` or
side-copy tree is safe, current, or authoritative.

## Authoritative Repos

These are the active source-of-truth working repos on primary workstation:

| Path | Role | Current Use |
|---|---|---|
| `C:\HybridRAG_V2` | authoritative V2 repo | primary development and execution path |
| `C:\CorpusForge` | authoritative Forge repo | primary upstream ingest/export repo |

## Additional Local Repo Surfaces

### `C:\HybridRAG_V2_Dev`

- branch: `master`
- HEAD at inspection time: `172d729`
- local state: **dirty**
- observed modified/deleted files included:
  - `.gitignore`
  - `sanitize_before_push.py`
  - `scripts/tiered_extract.py`
  - `src/query/embedder.py`
  - `src/store/entity_store.py`
  - `src/store/relationship_store.py`
  - several eval artifacts
  - deleted `CoPilot+.md`

**Use:** not safe to assume clean scratch space without deliberate cleanup.

### `C:\CorpusForge_Dev`

- branch: `master`
- HEAD at inspection time: `ca46fbf`
- local state: **dirty**
- observed modified files included:
  - `docs/OPERATOR_QUICKSTART.md`
  - `docs/WORKSTATION_SETUP_2026-04-06.md`
  - `scripts/run_pipeline.py`
  - `src/config/schema.py`
  - `src/pipeline.py`

**Use:** not safe to assume clean scratch space without deliberate cleanup.

### `{USER_HOME}\CorpusForge_Hustle`

- branch: `master`
- HEAD at inspection time: `90ad7db`
- local state: clean at inspection time

**Use:** useful for local comparison only.

**Do not treat as authoritative for “what Forge supports today.”**

## Coordinator Guidance

1. Default to:
   - `C:\HybridRAG_V2`
   - `C:\CorpusForge`
2. Treat `_Dev` trees as suspect until explicitly inspected.
3. Treat `CorpusForge_Hustle` as comparison-only, not truth.
4. If a disposable clean test surface is needed, create a fresh worktree or
   fresh clone instead of assuming an old `_Dev` tree is safe.

## Short Summary

primary workstation has multiple repo-shaped directories, but only `C:\HybridRAG_V2` and
`C:\CorpusForge` should be treated as authoritative by default. The `_Dev`
trees are currently dirty, and `CorpusForge_Hustle` is explicitly not the
Forge source-of-truth.
