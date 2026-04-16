# Demo Machine Audit -- 2026-04-12

**Purpose:** Name the current authoritative demo machine, the best backup machine, and the machines that are not safe for demo truth right now.

**Rule:** Live repo-local probes beat narrative docs. For desktop and laptop, this audit falls back to dated docs because those machines are not directly reachable from `C:\HybridRAG_V2`.

## Machine Mapping

- **primary workstation** in coordinator language maps to the current dual-RTX-3090 `C:\HybridRAG_V2` box documented elsewhere as the **primary workstation**.
- **desktop workstation** and **laptop workstation** are evaluated from the latest dated docs plus any explicit machine facts already frozen into those docs.

## Side-by-Side Audit

| Machine | Evidence basis | Repo commit / tree | Store state | Installer / prerequisites | Import path | Live demo use | Clean reruns | Verdict |
|---|---|---|---|---|---|---|---|---|
| **primary workstation / primary workstation** | **Live probes** on `C:\HybridRAG_V2` plus canonical docs | `22b22c2`; **dirty** (`docs/PRODUCTION_EVAL_RESULTS_2026-04-11.md`, `docs/production_eval_results_2026-04-11.json`, `scripts/run_production_eval.py`) | LanceDB **10,435,593** chunks. FTS index present and FTS-only probe returns rows. Vector index present: `IVF_PQ`, **10,435,593 indexed / 0 unindexed**. Hybrid probe returns rows. `entities.sqlite3` has **19,959,604** rows. `relationships.sqlite3` has **59** rows. | Installer surfaces exist: `INSTALL_WORKSTATION.bat`, `tools/setup_workstation_2026-04-12.ps1`, `tools/setup_workstation_2026-04-12.bat`. `scripts/verify_install.py` passes **9/9** critical deps. Two RTX 3090 GPUs visible. Ollama running with `phi4`. | Import path is complete for the canonical Forge export. `E:\CorpusIndexEmbeddingsOnly\export_20260411_0720\manifest.json` and `import_report_20260411_151620_import.json` both match **10,435,593** chunks into `C:\HybridRAG_V2\data\index\lancedb`. | **Yes, conditionally.** Best current live demo box for retrieval-first use after same-day freeze and scripted query checks. Not safe for broad aggregation claims. Not frozen right now because background eval / Tier 1 clean work is active. | **Yes** for V2 clean-store work. Not the preferred box for long unattended Forge reruns because GPU/state must stay protected for authoritative V2 work. | **Authoritative demo machine right now.** Also the only machine with a directly probed, complete, indexed 10.4M store. |
| **desktop workstation** | **Doc-derived only** from `BACKGROUND_RUNBOOK_2026-04-12.md`, `WORKSTATION_STACK_INSTALL_2026-04-12.md`, `CRASH_RECOVERY_2026-04-12.md`, `C:\CorpusForge\docs\FORGE_DESKTOP_RERUN_PACKET_2026-04-12.md` | **Unknown tonight**. No direct repo path reachable from this machine. Current state should be treated as unverified until a fresh pull/zip-pull plus machine-local checks run. | No directly probed V2 store. No authoritative chunk/entity/index counts available tonight. | Repo installer path is ready in source control, but desktop machine-local health is still **unverified**. Canonical instruction remains: pull frozen installer state, then run `scripts/verify_install.py` before using it. | No direct evidence of a completed V2 import on desktop tonight. | **Not yet.** It is a backup candidate, not current demo truth. | **Yes, best choice** for long unattended reruns once install correctness is confirmed. This is the correct Forge rerun box. | **Best backup candidate, but not demo-truth tonight.** It becomes the backup demo machine only after install, import, count parity, and scripted-query parity close. |
| **laptop workstation** | **Doc-derived only** from `LAPTOP_CHUNK_COUNT_DRIFT_2026-04-12.md`, `BACKGROUND_RUNBOOK_2026-04-12.md`, `WORKSTATION_STACK_INSTALL_2026-04-12.md`, `CRASH_RECOVERY_2026-04-12.md` | Exact SHA **unknown** because the laptop path is git-less / zip-pulled. Known bad timing: pulled **before 23:00 MDT 2026-04-11**, which predates security-standard fix `ba4d962` at **00:04 MDT 2026-04-12**. | Known non-canonical store: **10,700,593** chunks and **12,727,195** entities from the same Forge export that produced 10,435,593 chunks on primary workstation. Chunk drift remains open. Tier 2 was skipped because GLiNER was not installed. FTS/vector health not directly probed. | Current laptop install state must be treated as **unverified** until a fresh zip-pull plus `scripts/verify_install.py`. Historical evidence already shows dependency/version drift. | Import path is **not trustworthy** on the current laptop store because the final count drifted **+265,000** chunks from the verified export. | **No.** Not safe for demo truth. | **No** for heavy reruns tonight. Use only for smoke tests, operator rehearsal, or presentation support after rebuild. | **Not demo-truth.** Useful only as a secondary operator/support machine until rebuilt and revalidated. |

## Recommendation

### Authoritative Demo Machine

Use **primary workstation / primary workstation** as the authoritative demo machine **right now**.

Why:

- It is the only machine with a **directly probed** 10.4M-chunk LanceDB store.
- The canonical import from Forge is documented and matches live count truth.
- FTS, hybrid retrieval, and the IVF_PQ vector index are all visibly healthy.
- The workstation installer path exists in the repo and `scripts/verify_install.py` passes locally.

Constraint:

- Treat it as **retrieval-first authoritative truth**, not broad aggregation truth.
- It is **not frozen tonight** because the repo is dirty and long-running V2 work is still active.

### Backup Demo Machine

The **desktop workstation** is the best backup machine, but it is only a **backup candidate** until it passes all machine-local checks.

Why:

- It is the intended unattended rerun and backup-compute lane in the current runbook.
- It is the right place for the Forge desktop rerun packet that is already prepared in `C:\CorpusForge`.
- The laptop already has a documented drift incident and should not be promoted over desktop.

### Machines Not Safe For Demo Truth

- **desktop workstation**: not safe for demo truth **yet** because its repo state, store state, and install state were not directly probed tonight.
- **laptop workstation**: not safe for demo truth because its current store is known non-canonical (`+265,000` chunks) and its extraction code snapshot was stale.

## Required Pre-Demo Checks For primary workstation

Before freezing primary workstation as the live demo box, all of the following must be true on the same day as the demo or rehearsal:

1. No long-running mutation job is still writing to the authoritative store.
2. `git rev-parse HEAD` is recorded and `git status --short` is explained or frozen.
3. `.\.venv\Scripts\python.exe .\scripts\verify_install.py` passes.
4. `.\.venv\Scripts\python.exe .\scripts\health_check.py` reports the expected chunk count and ready vector index.
5. Direct store probes still show:
   - LanceDB count = **10,435,593**
   - relationships in `relationships.sqlite3` = **59**
   - entity count matches the frozen packet chosen for the demo day script
6. FTS-only and hybrid retrieval both return results on at least two known-good scripted queries.
7. If answer generation is in scope, the required provider path is present for that script:
   - OpenAI / Azure credentials, or
   - the approved local Ollama path
8. Once those checks pass, freeze the machine and stop ad hoc installer/store changes.

## Commit / Store / Prerequisite Mismatches To Watch

1. **Repo freeze mismatch on primary workstation:** the current authoritative machine is on `22b22c2` but the tree is dirty. That is acceptable for engineering work, not for demo freeze.
2. **Health-check relationship mismatch:** `scripts/health_check.py` currently reports `0` relationships because it does not read `relationships.sqlite3`, while direct SQLite probe shows **59** relationships. Use direct SQLite counts, not `health_check.py`, as the final relationship truth gate.
3. **Stale older docs:** `docs/CRASH_RECOVERY_2026-04-12.md` still describes an older **8,017,607**-entity store snapshot. The current authoritative entity count is the newer **19,959,604** live-probe value reflected in `AUTHORITATIVE_FACTS_AND_SOURCES_2026-04-12.md` and `MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md`.
4. **Laptop provenance gap:** the laptop's exact repo SHA is unknowable from this machine because it was zip-pulled without git. Treat that box as non-authoritative until rebuilt.
5. **Desktop proof gap:** the desktop is the best backup path, but there is no direct proof tonight that its repo, install, or store matches the current canonical packet.

## Bottom Line

- **Authoritative demo machine right now:** **primary workstation / primary workstation**
- **Best backup machine:** **desktop workstation**, conditional on install + import + query-pack validation
- **Not safe for demo truth:** **laptop workstation**, and **desktop workstation until validated**

If a demo had to run tonight with no more machine work, the honest choice is:

- run on **primary workstation**
- keep it **retrieval-first**
- keep **desktop** as the planned backup path
- keep **laptop** in operator/support duty only

## Sources

- [AUTHORITATIVE_FACTS_AND_SOURCES_2026-04-12.md](/C:/HybridRAG_V2/docs/AUTHORITATIVE_FACTS_AND_SOURCES_2026-04-12.md)
- [SOURCE_OF_TRUTH_MAP_2026-04-12.md](/C:/HybridRAG_V2/docs/SOURCE_OF_TRUTH_MAP_2026-04-12.md)
- [WORKSTATION_STACK_INSTALL_2026-04-12.md](/C:/HybridRAG_V2/docs/WORKSTATION_STACK_INSTALL_2026-04-12.md)
- [V2_INDEX_ARCHITECTURE_AND_REBUILD_2026-04-11.md](/C:/HybridRAG_V2/docs/V2_INDEX_ARCHITECTURE_AND_REBUILD_2026-04-11.md)
- [LAPTOP_CHUNK_COUNT_DRIFT_2026-04-12.md](/C:/HybridRAG_V2/docs/LAPTOP_CHUNK_COUNT_DRIFT_2026-04-12.md)
- [MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md](/C:/HybridRAG_V2/docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md)
- [FORGE_DESKTOP_RERUN_PACKET_2026-04-12.md](/C:/CorpusForge/docs/FORGE_DESKTOP_RERUN_PACKET_2026-04-12.md)
