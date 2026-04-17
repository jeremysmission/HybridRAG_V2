# Parallel Recovery Handover — 2026-04-09

Purpose: if the session or machine dies, this file is the quickest way to recover the current overnight plan without rebuilding context from scratch.

## Repo anchors

- CorpusForge repo: `C:\CorpusForge`
- HybridRAG V2 repo: `C:\HybridRAG_V2`
- CorpusForge onboarding: `C:\CorpusForge\___OnboardingInfo_2026_04_09.md`
- HybridRAG V2 onboarding: `C:\HybridRAG_V2\___OnboardingInfo_2026_04_09.md`

## Current high-signal state

- Clean Forge export is still `C:\CorpusForge\data\production_output\export_20260409_0720`
- Current basic V2 import path is `C:\HybridRAG_V2\scripts\import_embedengine.py`
- Active Forge runtime config is now `C:\CorpusForge\config\config.yaml`
- `config.local.yaml` is retired from the live runtime path
- GUI Save Settings now writes to `config/config.yaml`
- Resume/hash persistence was recently fixed so interrupted work files persist as `hashed` in the SQLite state DB instead of living only in RAM
- Latest pushed CorpusForge commit before this note: `734b98b`
- Latest pushed HybridRAG V2 commit before this note: `592f64f`

## Active parallel lanes

### Lane 1 — CorpusForge nightly delta scheduling + canary ops

Worker nickname: `Tesla`

Mission:
- detect new/changed files on the source drive
- copy only delta locally
- run the existing Forge pipeline on that delta
- add canary-ready proof/testing
- produce a scheduler/task install path and runbook

### Lane 2 — CorpusForge GUI control + live telemetry

Worker nickname: `Anscombe`

Mission:
- improve stop/pause behavior
- add live chunk count + chunks/sec
- keep operator-visible stage/status honest
- run GUI harness and button-smash coverage

Latest QA blocker on that lane:
- Stop Pipeline is not a real live stop yet
- button-smash does not cover Stop yet

### Lane 3 — HybridRAG V2 staging/import ops

Worker nickname: `Hooke`

Mission:
- make nightly Forge handoff cleaner on the V2 side
- keep imports/staging explicit and operator-visible
- add durable reporting artifacts
- make canary validation easy

Scope:
- `C:\HybridRAG_V2\scripts\import_embedengine.py`
- helper scripts under `C:\HybridRAG_V2\scripts\`
- `C:\HybridRAG_V2\docs\planning\SPRINT_SYNC.md`
- short runbook doc under `C:\HybridRAG_V2\docs\`
- tests if needed

### Lane 4 — docs, sprints, sanitizer, golden/canary test plan

Worker nickname: `Singer`

Mission:
- remove the old workstation nickname from remote-bound technical docs
- harden banned-word hygiene if needed
- add tonight's work into sprint slices/boards
- create a better golden-production-data + canary test plan
- add a concise operator note that low GPU during parse is generally expected

## QA plan

- QA1 should pick up whichever lane posts `Ready for QA` first
- Priority order:
  1. Lane 2 GUI control/telemetry
  2. Lane 1 nightly delta scheduler
  3. Lane 3 V2 staging/import
  4. Lane 4 docs/sanitizer/golden-plan
- QA2 only needs to activate if two substantial lanes finish close together

## Important recent fix already landed

The single-config + crash persistence batch is already in mainline:

- CorpusForge commit: `734b98b`
- summary:
  - active runtime config is `config/config.yaml`
  - no live `config.local.yaml` path
  - dedup now persists work-file hashes as `hashed` before full export success
  - interrupted runs no longer lose all hash progress

## Operator facts worth preserving

- During parse, low GPU usage is usually expected because parse is mostly CPU, disk, decompression, OCR, and parser bound
- GPU should matter more during embedding than during discovery/parse
- The 700GB operator docs now point at `config/config.yaml`, not `config.local.yaml`

## If recovery is needed

1. Open the onboarding file in either repo root.
2. Open this file.
3. Reopen:
- `C:\CorpusForge\archive\2026-04-17\docs\planning\SPRINT_SYNC.md`
- `C:\CorpusForge\GUIDE.md`
- `C:\HybridRAG_V2\docs\planning\SPRINT_SYNC.md`
4. Resume lane work from the scopes above instead of rediscovering context.
