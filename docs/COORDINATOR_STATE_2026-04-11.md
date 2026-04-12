# Coordinator State — 2026-04-11

**Purpose:** Snapshot of active state so the coordinator can resume without re-reading the full session.

---

## Pushed Commits Today (HybridRAG_V2)

| Commit | Summary |
|--------|---------|
| `07764d8` | Walk-away import+extraction script, GLiNER GPU auto-detect, import benchmark docs |
| `95c13dc` | GUI import+extraction panel with live progress, sanitize docs |
| `f4727d9` | Streaming chunk extraction for 10M+ corpora, GUI matched |
| `715fe4b` | Fix FTS index creation for LanceDB 0.30+ single-column API |
| `957eaab` | Fix hybrid_search to use LanceDB 0.30+ builder chain (vector+text) |

## Live State

### primary workstation (here)
- **LanceDB:** `C:\HybridRAG_V2\data\index\lancedb` — 10,435,593 chunks, 44GB
- **Vector index:** IVF_PQ working
- **FTS index:** Built (164.8s build time), verified with maintenance/PO-24/ACAS/STIG/shipment/calibration
- **Entity store:** 21,660,323 entities from Tier 1 regex (BUT 16M CONTACT are over-matched phone fakes — needs fix)
- **Tier 2 GLiNER:** Not yet run — pending CONTACT fix first

### Laptop
- **Status:** Importing 10.4M chunks (~75% at last check, ~7.86M inserted)
- **Will need after import:** `git pull` for FTS + hybrid fixes, then manual `create_fts_index()` call (~3 min)
- **Extraction will run automatically** via walk-away script after import completes

### Workstation Desktop (10 min drive)
- Has V2 installed
- Waiting for validated code push before the unattended run
- NOT yet touched today

### AWS
- User is wiring up GovCloud OSS-20B endpoint
- Rate limits: 150K TPM / 5M TPH
- Endpoint URL / auth method still TBD from admin
- SageMaker notebook + S3 bucket already provisioned

## Verified Working

| Layer | Evidence |
|-------|----------|
| 10.4M LanceDB import | 44GB on disk, `store.count()` returns 10,435,593 |
| IVF_PQ vector index | `list_indices()` shows it, queries return results in <20ms |
| FTS index | reviewer V2 probe, 55% → 73% exact-match hit rate |
| `LanceStore.hybrid_search()` | reviewer app-path probe 25/25 identical to raw path |
| `VectorRetriever.search()` | Same, end-to-end verified |
| Streaming extraction (iter_chunk_batches) | Code pushed, not yet used on primary workstation Tier 1 (old run) |
| GUI import/extraction panel | Pushed, live on laptop via `RUN_IMPORT_AND_EXTRACT_GUI.bat` |

## Known Issues

| Issue | Severity | Status |
|-------|----------|--------|
| 16M CONTACT over-matching (phone regex) | HIGH | reviewer getting this task after hybrid QA clears |
| Only 59 relationships in Tier 1 | Expected | Will improve with Tier 3 LLM extraction via AWS |
| 4 lookup queries still miss (L01/L02/L03/E05) | Data gap, not code | Tokens don't exist in current corpus — Sprint 6 ingest territory |
| Aggregation queries fail retrieval alone | Expected | Needs entity store — that's why we're extracting |
| Tier 2 GLiNER not yet run | Pending | Wait for CONTACT fix, then run on GPU 1 ~1-2 hours |

## Active Agents

| Agent | Task | Status |
|-------|------|--------|
| QA | Verify hybrid_search commit `957eaab` | Round 2 pending — round 1 caught the API bug |
| reviewer | App-path retrieval probe | DONE — 25/25 identical, ready for QA |
| reviewer | Golden eval queries across 5 personas (PM/Logistics/Field Eng/NetAdmin-Cyber/Aggregation) | In progress |
| reviewer | GUI streaming fix | DONE — committed in `f4727d9` |
| AWS Agent | Wire up GovCloud OSS-20B endpoint | In progress — blocked on admin for endpoint URL/auth |

## Next Actions (When Coordinator Resumes)

1. **Watch for:** QA signoff on `957eaab` hybrid_search fix
2. **Watch for:** Laptop import completion → tell user to pull latest + rebuild FTS (~3 min)
3. **Watch for:** reviewer returning golden eval queries → review for 5 personas coverage
4. **Watch for:** AWS agent hitting blockers with endpoint auth → help debug if needed
5. **When QA clears:** Hand reviewer the phone regex fix task (brief already drafted in conversation history, see `docs/PHONE_REGEX_FIX_BRIEF_2026-04-11.md` if saved)
6. **After phone fix:** Re-run Tier 1 on primary workstation, then launch Tier 2 GLiNER on GPU 1
7. **Before workstation desktop run:** Ensure all validated code is pushed, re-verify on laptop first

## Key Reference Files

- `docs/SESSION_GAMEPLAN_2026-04-11.md` — full game plan
- `docs/HOW_TO_IMPORT_FORGE_EXPORT_TO_V2_LANCEDB.md` — import guide
- `docs/IMPORT_BENCHMARK_10M_2026-04-11.md` — import timing reference
- `docs/DEMO_TALKING_POINT_NIGHTLY_SUSTAINABILITY_2026-04-11.md` — nightly ops story
- `docs/RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md` — retrieval quality evidence
- `scripts/run_full_import_and_extract.py` — walk-away CLI
- `scripts/import_extract_gui.py` — walk-away GUI
- `RUN_IMPORT_AND_EXTRACT.bat` / `RUN_IMPORT_AND_EXTRACT_GUI.bat` — batch wrappers

## Demo Day Story (Current)

- 430K source files, 215K unique, 93K text-parseable, 10.4M chunks embedded
- 20-30 files/day real churn rate (nightly delta sustainable on local workstation)
- Hybrid retrieval: 73% exact-match hit rate, 23ms P50 query latency
- $0 infrastructure cost — runs on workstation already in inventory
- GovCloud + offline compatible by design
- No LangChain, no vendor lock-in, direct Python with debuggable layers

Signed: CoPilot+ | Coordinator | 2026-04-11 MDT
