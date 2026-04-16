# Crash Recovery Document — 2026-04-11/12 Overnight Session

> WARNING: Historical recovery snapshot only. This file is not safe as the current crash-recovery entrypoint because its store/entity assumptions are stale.
> Start instead with `docs/SOURCE_OF_TRUTH_MAP_2026-04-12.md`, `docs/REBOOT_HANDOVER_2026-04-13.md`, and `docs/COORDINATOR_CONTINUITY_NOTES_2026-04-13.md`.

**Purpose:** If the computer crashes, the session dies, or the user wakes up and needs to re-orient fast, this doc is the quickest path back to productive work.

**Last updated:** 2026-04-11 late evening MDT
**Author:** CoPilot+ (Coordinator)

---

## Read this first

The project is V2 of a RAG system for a enterprise/government corpus. Demo day is **May 2, 2026**. V1 was cancelled because aggregation queries didn't work. V2 is **the last chance** — there is no Plan C. The user pays ~10 hrs/week on this; the rest is personal time. Career goal: stretch assignment → AI applications role.

**The corpus:** ~700 GB raw source, ~215K unique files after dedup, ~93K successfully parsed, **10,435,593 text chunks** with 768-dim embeddings. Lives at `E:\CorpusTransfr\verified\IGS\` (source) and `E:\CorpusIndexEmbeddingsOnly\export_20260411_0720\` (Forge export).

---

## Active processes running overnight

**primary workstation (this machine):**
- **Tier 2 GLiNER extraction** running in background via `scripts/tiered_extract.py --tier 2` on GPU 1
- Task ID: `b0dgtt808`
- Output log: `C:\WINDOWS\TEMP\CoPilot+\C--Users-{USERNAME}\1272f332-a04a-4bee-8713-91d989a97f10\tasks\b0dgtt808.output`
- Will NOT finish by morning — expect 11-18 hours total, so late morning through afternoon tomorrow
- Re-streams Tier 1 first (~30 min), then streams Tier 2 GLiNER
- RAM target <10GB, should be fine
- **If crashed:** check process with `powershell -c "Get-Process -Id 80316"` — if dead, re-run `cd /c/HybridRAG_V2 && CUDA_VISIBLE_DEVICES=1 .venv/Scripts/python.exe scripts/tiered_extract.py --tier 2` in a fresh terminal

**Workstation laptop (running beside user):**
- Walk-away GUI running `RUN_IMPORT_AND_EXTRACT_GUI.bat`
- Max Tier 1 only (to avoid the memory blowup from Tier 2 accumulation — commit `c32d126` GUI fix is pulled but caution)
- Skip Import unchecked — should be topping up the laptop's LanceDB from ~10M to 10,435,593 via dedup
- Expected to finish overnight

**Agents running (background):**
- **reviewer:** Task #16 — investigate and fix security standard regex over-matching (POs matching security standard control IDs, PARTs matching security standard SP 800-53 codes)
- **reviewer:** Research sprint on RAG aggregation ground truth patterns, then Phase 2A of 400-query eval corpus
- **reviewer:** Dual deliverable — demo-day research patterns + V2 readiness gap analysis (both read-only analysis)
- **AWS agent:** Wiring GovCloud OSS-20B endpoint (unknown status, user owns this track)

---

## Critical facts about V2 state

**LanceDB on primary workstation:** 10,435,593 chunks at `C:\HybridRAG_V2\data\index\lancedb`
**Entity store on primary workstation:** 8,017,607 Tier 1 entities at `C:\HybridRAG_V2\data\index\entities.sqlite3` (6.7 GB)
- DATE: 2,713,472
- CONTACT: 2,540,033 (down from 16.1M after phone regex fix)
- PART: 2,521,235 ← **~90% polluted with security standard SP 800-53 baseline codes** (reviewer discovered)
- PO: 150,602 ← **~98% polluted with security standard control IDs** (reviewer discovered)
- SITE: 87,477
- PERSON: 4,788

**FTS index on primary workstation:** Built and working (commit `715fe4b`)
**IVF_PQ index on primary workstation:** Built and working (created during import)
**Hybrid retrieval on primary workstation:** Verified working end-to-end 25/25 app-path matches (commit `957eaab`)

**Backup stores on primary workstation (safety):**
- `C:\HybridRAG_V2\data\index\entities_pre_phonefix_20260411.sqlite3.bak` (18 GB — old over-matched phone data)
- `C:\HybridRAG_V2\data\index\lancedb_pre_10M_20260411\` (safety copy of LanceDB before 10.4M import)

---

## Pushed commits this session (in chronological order)

All on `origin/master`. If local tree is lost, `git pull` recovers everything:

| Commit | Summary |
|--------|---------|
| `07764d8` | Walk-away script + GLiNER GPU auto-detect |
| `95c13dc` | GUI import/extract panel with live progress |
| `f4727d9` | Streaming chunk extraction for 10M+ corpora |
| `715fe4b` | **Fix FTS single-column API (was silently broken for 7 days)** |
| `957eaab` | **Fix hybrid_search builder chain (was silently vector-only)** |
| `7faef97` | **Phone regex round 2 (CONTACT 16M → 2.54M)** |
| `8a1531b` | CLI Tier 2 streaming real path |
| `c32d126` | GUI Tier 2 streaming port |
| `8a1361d` | verify_install.py + installer Step 7/7 |
| `e9be0ef` | Lane 9.2 GUI evidence harness |
| `e6d1678` | Lane 9.2 Tier D handoff plan |
| `96dac08` + `0f97b00` | Ingest integrity assertion (laptop 10M investigation) |
| `c8b6bd3` + `e02e777` | Production eval runner + round 2 fixes |
| `7975b13` | Retrieval probes, coordinator state, eval fixture updates |
| `08c9162` | GUI skip-import UX fix |
| `5d6a0ba` | 400-query RAGAS eval Phase 1 (50 queries + anchor miner) |
| `0a19fb9` | Agent research standing orders |

---

## What to do when you wake up

### First 5 minutes — health checks

1. **Is primary workstation still alive?**
   ```
   powershell -c "Get-Process python* | Format-Table"
   ```
   If a Python process is running with high CPU, Tier 2 is still going. Leave it alone.

2. **Is the laptop Tier 1 done?**
   - Look at the GUI window, check the phase label
   - Run `.venv\scripts\python -c "from src.store.entity_store import EntityStore; print(EntityStore('data/index/entities.sqlite3').count_entities())"` — should be ~7.5-8M if done

3. **Check overnight agent output:**
   - Did reviewer push a commit for task #16 (security standard regex fix)? `git log origin/master --oneline -10`
   - Did reviewer push commits for research/Phase 2A?
   - Did reviewer push commits for gap analysis?
   - QA signoffs: check whatever channel you use for QA feedback

### First 30 minutes — triage

1. **Read `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md`** (reviewer's deliverable, if committed). This gives you the frank state of V2 as of this morning with GREEN/YELLOW/RED ratings on 10 dimensions.

2. **Read `docs/RAG_AGGREGATION_EVAL_RESEARCH_2026-04-12.md`** (reviewer's research sprint, if committed). This tells you what approach to use for demo-day ground truth.

3. **Read reviewer's task #16 output** — was the security standard regex fix committed? If yes, the clean Tier 1 re-run becomes a coordinator decision.

4. **Check primary workstation Tier 2 progress** — how far through the filtered GLiNER subset? Estimate remaining time.

### The critical path to demo day

```
reviewer task #16 (security standard regex fix) 
  → Coordinator decision: re-run Tier 1 on primary workstation (~40 min)
  → Wait for Tier 2 GLiNER to finish (primary workstation)
  → reviewer runs production eval against clean store
  → Review eval results, tune router, pick demo queries
  → Rehearse demo queries end-to-end
  → Demo day May 2
```

### The aggregation problem (THE biggest risk)

**Status:** aggregation queries currently return polluted counts. PO is 98% security standard IDs, PART is 90% baseline codes. V1 died on this exact class of problem.

**Path to fix:**
1. reviewer's task #16 fixes the regex patterns
2. Re-run Tier 1 produces honest counts
3. reviewer's research (tonight) identifies the right pattern for provable ground truth — likely canary injection or scoped real-data queries
4. Task #18 (canary injection, blocked on #16) creates known-good validation records
5. Demo uses 5 verified aggregation queries, not "plausible-looking" numbers

**If the regex fix fails or is deferred**, the fallback demo story is:
- Lead with SEMANTIC and ENTITY_LOOKUP queries where retrieval quality (73% exact-match hit rate) is strong
- Avoid corpus-wide AGGREGATE claims until the fix lands
- Use canary-backed narrow-scope aggregation only

---

## Tasks open in the task list

| # | Status | Subject |
|---|--------|---------|
| 3 | in_progress | Tier 2 GLiNER on primary workstation (overnight) |
| 7 | pending | Push validated code (mostly done) |
| 8 | pending | Prepare workstation desktop for unattended run (blocked on 16) |
| 9 | pending | Set up AWS OSS-20B endpoint (user-owned) |
| 16 | NEW | security standard regex over-matching fix (reviewer) |
| 17 | in_progress | 400-query RAGAS eval corpus (reviewer, Phase 1 done) |
| 18 | blocked on 16 | Canary injection for aggregation validation |

---

## Machines and hardware

| Machine | GPU | RAM | Role |
|---------|-----|-----|------|
| primary workstation (here) | NVIDIA workstation desktop GPUs (24 GB each) | 64 GB | Dev/lab, running Tier 2 overnight |
| Workstation Laptop (beside user) | RTX 3000 Pro (12 GB) | 64 GB | Running walk-away overnight, dev/query testing |
| Workstation Desktop (10 min drive) | RTX A4000 (20 GB) | 64 GB | Tomorrow: pull latest, run clean production extraction unattended 24-48h |

**GPU assignment on primary workstation:** GPU 1 is the clean one, GPU 0 has overhead from desktop processes. All heavy work goes to GPU 1.

---

## Standing orders in effect (pushed as `0a19fb9`)

All agents have been told to:
- Bias toward recency — assume training data is stale, web-search before implementing
- Cite sources in handoff notes
- Use firewall-relaxed window the user is providing tonight
- Meet or exceed industry standard best practices

See `docs/AGENT_RESEARCH_STANDING_ORDERS.md` for the full policy.

---

## What NOT to do when recovering

1. **Do NOT kill the primary workstation Tier 2 process.** It's hours into GLiNER streaming. If it's still running when you wake, let it finish.
2. **Do NOT wipe the entity store.** The current primary workstation entity store has honest phone data from the fix, just polluted PO/PART. Task #16 will fix the regex patterns, then a targeted re-run produces clean data.
3. **Do NOT re-run the full pipeline on primary workstation** without coordinator review — it's a 30-60 min operation that wastes time if the fix hasn't landed.
4. **Do NOT re-trigger the laptop walk-away** if it already finished successfully.
5. **Do NOT try to run the workstation desktop overnight without first pulling latest code and running `scripts/verify_install.py`** — task #14 verification step catches missing dependencies.

---

## If the agent team has gone quiet or stuck

1. **reviewer** may be blocked on something in the security standard regex research. He knows to cite sources and keep scope tight. If he pushed nothing, check what he last posted and whether he's waiting on clarification.

2. **reviewer** has two tracks — research sprint OR Phase 2A query authoring. He was told to research first, so by morning he should have either the research doc done and Phase 2A started, OR still in research.

3. **reviewer** has two deliverables — demo research and gap analysis. Gap analysis is higher priority, so if only one is done, expect that one.

4. **QA** should have cleared anything sent by agents. Check for pending QA items.

5. **AWS agent** — user-owned track, coordinator doesn't have status. User should check personally.

---

## Key reference files (most important for recovery)

- `docs/SESSION_GAMEPLAN_2026-04-11.md` — original game plan
- `docs/COORDINATOR_STATE_2026-04-11.md` — live state doc before tonight's work
- `docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md` — reviewer's eval rationale + critical entity pollution discovery
- `docs/LAPTOP_10M_INVESTIGATION_2026-04-11.md` — ingest integrity investigation (reviewer)
- `docs/DEMO_TALKING_POINT_NIGHTLY_SUSTAINABILITY_2026-04-11.md` — demo narrative draft
- `docs/IMPORT_BENCHMARK_10M_2026-04-11.md` — import timing reference
- `docs/HOW_TO_IMPORT_FORGE_EXPORT_TO_V2_LANCEDB.md` — import operator guide
- `docs/AGENT_RESEARCH_STANDING_ORDERS.md` — agent research policy
- `docs/CRITICAL_PYLANCE_INSTALL_REQUIRED_2026-04-11.md` — SUPERSEDED (pylance not needed, `lancedb.SearchBuilder.to_batches` is used instead)
- `CoPilot+.md` or equivalent — V2 agent entry point

---

## Five demo candidates the user is thinking about (from conversation)

Not yet written or verified — these are seeds for the demo query set:

1. "How many unique part numbers across the corpus?" — needs PART entity fix first (task #16)
2. "List all purchase orders from 2024" — needs PO entity fix + DATE filtering
3. "How many service events occurred at [real site name]?" — needs SITE + FSR/UMR report IDs
4. "Show me all documents referencing [specific real PO number]" — hybrid: FTS + entity lookup + aggregation
5. Something involving ACAS cybersecurity findings — real scoped, narrow subfolder

Each requires ground truth. Options from tonight's conversation: canary injection (known synthetic records for provable counts) OR narrow-scope real-data queries (manually verifiable subset). Hybrid of both is the likely demo strategy.

---

## Contact / session notes

**User preferences:**
- Direct honest communication, no soft-pedaling
- Scope discipline — don't touch files out of the requested change set
- Standing order: sanitize before every push
- Standing order: local commit → sanitize → push
- Standing order: never attribute work to AI/agents/CoPilot+ in repo commits — use "Jeremy Randall" or "CoPilot+"
- Do not include time estimates for future work
- GPU 1 for fast work on primary workstation (GPU 0 has overhead)
- Real hardware testing before push — no shortcuts

**Mission framing:**
- 3 demo personas: PM, Logistics Lead, Field Engineer
- Plus: Network Admin / Cyber, Aggregation/Cross-role
- Civilian enterprise audience
- offline / restricted deployment compatible
- Zero ongoing infrastructure cost claim

---

Signed: CoPilot+ | Coordinator | 2026-04-11 late evening MDT
