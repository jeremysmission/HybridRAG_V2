# Sprint 9-12 Game Plan

**Date:** 2026-04-05 MDT  
**Prepared during:** Sprint 8 QA window  
**Purpose:** Four-sprint forward plan after the Sprint 8 demo gate passed

---

## Current-Source Findings

### 1. Ollama stability and latency need service-shaping, not just prompt changes

- Ollama documents `keep_alive` on `/api/chat`, which is the right way to hold the demo model warm between requests.
- Ollama documents that concurrency can queue work and eventually return `503` if the server is overloaded.
- Ollama documents that effective context memory scales with `OLLAMA_NUM_PARALLEL * OLLAMA_CONTEXT_LENGTH`.

**Implication:** keep the model pinned, keep concurrency at `1` for stable timing, and separate extraction workloads from live query workloads.

### 2. LanceDB promotion needs explicit index-freshness checks

- LanceDB documents that new rows can remain outside the current ANN index until reindex/maintenance finishes.
- LanceDB exposes `wait_for_index()`, `index_stats()`, and reindex guidance for confirming readiness.

**Implication:** any promoted store needs a hard gate of:

- expected row count
- vector index present
- zero unindexed tail

### 3. Deployment should stay wheel-first and documented

- PyPA packaging guidance keeps `python -m build` and wheel artifacts as the clean offline-transfer path.
- FastAPI deployment guidance keeps `fastapi run` / `uvicorn` simple for controlled local service launches.

**Implication:** the work-machine path should use repeatable wheel installs and a single documented API launch path, not ad hoc editable installs.

### 4. Eval discipline stays mandatory as scope expands

- OpenAI evaluation guidance emphasizes task-specific evals, full workflow logging, and trace-aware review.

**Implication:** larger-corpus promotion should not rely on spot checks alone. Routing, retrieval, confidence, and latency need to be reviewed together.

---

## Sprint 9: Entity Promotion And Latency Reduction

### Goal

Turn the current demo-safe build into a more complete V2 proof by populating the structured stores and reducing warm-path latency where possible.

### Work Items

1. Populate the isolated entity/table/relationship store once the chosen extraction service path is available.
2. Re-run full golden eval with generation enabled on the isolated store.
3. Fix the remaining retrieval gaps still called out in Sprint 6:
   - `GQ-016`
   - `GQ-017`
   - `GQ-019`
   - `GQ-020`
   - `GQ-023`
4. Profile warm local-Ollama latency by stage:
   - router
   - retrieval
   - generation
5. Test smaller response caps and prompt reductions where they do not hurt answer quality.
6. Decide whether the demo path remains local-Ollama or moves to a commercial/Azure endpoint for presentation-grade latency.

### Exit Criteria

- Entity store is populated on the isolated demo store.
- Full golden eval runs end-to-end.
- A documented latency recommendation exists for demo vs offline use.

---

## Sprint 10: Work-Machine Deployment And Clean Install

### Goal

Prove that the current stack can be installed, started, and queried on the work machine from packaged artifacts and docs alone.

### Work Items

1. Refresh wheel bundles for both repos from the current promoted commits.
2. Write a single clean-install runbook:
   - Python version
   - wheel install order
   - environment variables
   - model pull / service start
   - API launch
3. Validate install on a clean target environment without relying on editable mode.
4. Verify config path resolution on the target machine from outside the repo root.
5. Validate the health check, one golden query, and one demo-gate smoke query on the target machine.

### Exit Criteria

- Clean install succeeds from wheel artifacts.
- Target machine passes health check and a minimal smoke suite.
- Deployment docs are sufficient without tribal knowledge.

---

## Sprint 11: Larger-Corpus Promotion

### Goal

Move beyond the current proof subset and promote a materially larger staged corpus without losing index hygiene or eval visibility.

### Work Items

1. Run a larger CorpusForge extraction pass on the next approved source slice.
2. Apply dedup before import and preserve skip/deferred accounting.
3. Import into a new promoted LanceDB store.
4. Build and verify fresh vector indices.
5. Re-run golden eval plus persona-specific query packs against the larger store.
6. Compare quality and latency deltas against the current Sprint 8 store.

### Exit Criteria

- Larger promoted store exists with verified index readiness.
- Skip/deferred counts are documented.
- Eval deltas are reviewed and accepted.

---

## Sprint 12: Production Hardening And Operator Readiness

### Goal

Convert the larger proof into an operationally safe local service with clear operator expectations.

### Work Items

1. Add a promotion checklist that includes:
   - row count
   - index readiness
   - golden eval
   - demo gate
2. Add structured logging for:
   - route choice
   - retrieval counts
   - confidence
   - latency
3. Add one-button local startup and shutdown wrappers for the API and dedicated Ollama path.
4. Write operator-facing notes for known limits:
   - empty-entity fallback behavior
   - latency expectations
   - deferred file classes
5. Prepare a simple rollback path to the last known-good promoted store.

### Exit Criteria

- Promotion checklist is documented and usable.
- Local operator runbook exists.
- Rollback path is tested.

---

## Sources

- Ollama API chat docs: https://docs.ollama.com/api/chat
- Ollama FAQ: https://docs.ollama.com/faq
- LanceDB vector indexing docs: https://docs.lancedb.com/indexing/vector-index
- LanceDB reindexing docs: https://docs.lancedb.com/indexing/reindexing
- PyPA packaging tutorial: https://packaging.python.org/en/latest/tutorials/packaging-projects/
- FastAPI deployment manual run docs: https://fastapi.tiangolo.com/deployment/manually/
- Official evaluation best-practices guide
- Official trace-grading guide
