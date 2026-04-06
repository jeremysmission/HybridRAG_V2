# Sprint 8 + 9 Game Plan

**Author:** CoPilot+
**Date:** 2026-04-05 MDT
**Purpose:** Actionable next-step plan prepared during Sprint 6/7 QA time per `docs/QA_EXPECTATIONS_2026-04-05.md`

---

## Sprint 8: Demo Gate And Delivery

## Goal

Turn the current Sprint 6 proof build into a demo-safe system with a timed rehearsal, clear skip acknowledgment, and a stable backup path.

## Critical Preconditions

- Overnight extraction is no longer occupying the shared local `ollama` path, or demo generation is moved to a separate model/service path.
- A generation-capable config is selected: local `ollama` or commercial/Azure API.
- V2 server is started against the isolated Sprint 6 store or a newer promoted store.

## Current-Source Findings

### 1. Local Ollama serving is the main demo risk, not retrieval

- Ollama exposes `keep_alive` on `/api/chat`, and responses include both `total_duration` and `load_duration`. That gives us a clean way to separate cold-start penalty from steady-state latency during rehearsal.
- Ollama’s FAQ documents that concurrent requests can queue and eventually return `503` when the server is overloaded. It also documents that parallel request processing increases effective context memory usage by `OLLAMA_NUM_PARALLEL * OLLAMA_CONTEXT_LENGTH`.
- Ollama will place a model on a single GPU when it fully fits on one GPU, which is the preferred performance path.

**Implication for this repo:** the next live rehearsal should not share the same Ollama service with extraction. Use a dedicated port and the less-busy GPU, keep `OLLAMA_NUM_PARALLEL=1`, keep `OLLAMA_MAX_LOADED_MODELS=1`, preload the model, and hold it in memory with `keep_alive=-1` or `OLLAMA_KEEP_ALIVE=-1` during the rehearsal window.

### 2. LanceDB OSS needs explicit index hygiene after new imports

- LanceDB OSS requires manual vector-index maintenance. Their docs state that `create_index()` is asynchronous, and `wait_timeout` or `wait_for_index()` should be used when index readiness matters.
- LanceDB’s reindexing guidance states that when new rows are added without reindexing, LanceDB merges indexed results with flat search on unindexed rows, which increases latency.
- Their docs recommend `index_stats()` to confirm whether unindexed rows remain, and `optimize()` to compact fragments, prune old files, and update indexes.
- For `IVF_PQ`, LanceDB’s current starting point is `num_partitions = num_rows // 4096` and `num_sub_vectors = dimension // 8`; they also recommend leaving `nprobes` auto-tuned unless recall is still insufficient.

**Implication for this repo:** every promoted demo store needs an explicit “index ready” check after import or fixture changes. The rehearsal path should treat `list_indices()` plus `index_stats()` or equivalent zero-unindexed verification as a hard prerequisite before timing is trusted.

### 3. Remaining demo validation should stay eval-driven

- OpenAI’s current evaluation guidance recommends eval-driven development, scoped tests at every stage, task-specific evals, logging everything, automated scoring where possible, and calibration against human judgment.
- OpenAI’s trace grading guidance recommends evaluating the full workflow trace, not just the final output, because traces show where orchestration and routing fail.

**Implication for this repo:** the remaining Sprint 7/8 demo work should log and review route choice, retrieval success, answer quality, confidence, and stage timing together. Rehearsal should not be judged only on whether the final answer looked acceptable.

## Pre-Sprint Checklist

1. Decide the live generation path for rehearsal: dedicated local `ollama` service or commercial/Azure API.
2. If using local `ollama`, start a dedicated server on a fixed port with one GPU reserved for it and no concurrent extraction workload on that service.
3. Preload `phi4:14b-q4_K_M` and pin it in memory for the rehearsal window so latency numbers are not dominated by reloads.
4. Verify the promoted demo store is fully indexed after the latest import or fixture add: row count, vector index present, no meaningful unindexed tail.
5. Confirm whether V1 will be live or whether `scripts/compare_v1_v2.py` should use an approved offline V1 capture.
6. Confirm who will perform the non-developer button-smash pass and when.
7. Freeze the exact corpus counts for the skip-file acknowledgment slide before recording or demo rehearsal.

## Work Items

1. Start a dedicated demo-generation path:
   - local option: separate `ollama` service on a fixed port, less-busy GPU, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KEEP_ALIVE=-1`
   - API option: explicit deployment/base URL in a dedicated demo config
2. Re-run `scripts/demo_rehearsal.py --config config\config.sprint7_ollama.yaml --timing` only after the generation path is isolated and warm.
3. Capture per-query route, latency, confidence, and failure mode for the 10 demo queries. Treat cold-start and warm-start timings separately when local `ollama` is used.
4. Rehearse the three persona flows in sequence: program manager, logistics analyst, engineer.
5. Start the V2 API server on a fixed port and verify `/health`, `/query`, and `/query/stream`.
6. Run `scripts/compare_v1_v2.py` against live V2 and either a live V1 endpoint or an approved offline V1 capture.
7. Lock the final skip-file acknowledgment text to the exact indexed/deferred counts shown by the promoted demo store.
8. Produce the backup recording after the rehearsal passes.
9. Do the human button-smash pass once the GUI is pointing at the stable server.

## Exit Criteria

- Full 10-query rehearsal passes on the chosen demo store.
- Measured demo latency is within the agreed story for live presentation.
- Backup recording exists.
- Skip-file slide text matches the promoted corpus exactly.

---

## Sprint 9: Post-Demo Production Push

## Goal

Convert the proven demo build into a production-minded extraction and retrieval workflow that can scale beyond the current proof subset.

## Work Items

1. Populate the isolated entity store once the shared local `ollama` path is free or an alternate extraction service is configured.
2. Fix the remaining golden gaps still failing in retrieval-only mode:
   - `GQ-016` Mike Torres email
   - `GQ-017` AB-115 site aggregation
   - `GQ-019` Riverside vs Cedar Ridge comparison completeness
   - `GQ-020` cancelled PO retrieval
   - `GQ-023` corpus-wide unique part-number aggregation
3. Add an explicit “index freshness” verification step to promotion/checklist flows so new rows never silently force flat search on an unindexed tail.
4. Promote the config-loader path resolution fix everywhere it matters in QA and deployment scripts.
5. Package offline wheels for both repos and stage the work-machine transfer bundle.
6. Verify a clean install path on the target work machine from docs alone.
7. Run a larger scale extraction/import pass once the work machine path is ready.
8. Replace the current demo subset counts with larger-corpus metrics for the next stakeholder review.

## Risks To Watch

- Shared local `ollama` service causing unstable latency during extraction and demo work.
- Empty entity store hiding structured-query weaknesses during retrieval-only testing.
- Config-relative-path bugs reappearing in scripts that bypass `load_config()`.
- Larger corpus mixes introducing more parser failures or noisy chunks than the Sprint 6 proof subset.
- Late-added rows in LanceDB causing hidden flat-search fallback and misleading latency numbers if `optimize()` / reindex checks are skipped.
- Treating demo rehearsal as a black-box pass/fail instead of reviewing route choice, timing, and answer quality together.

## Recommended Order

1. Isolate and warm the live generation path.
2. Verify the promoted demo store is fully indexed and timing-safe.
3. Finish live demo rehearsal with route/timing review, not answer-only review.
4. Run V1 vs V2 comparison on the same live or approved-capture query set.
5. Populate entity extraction on the isolated store.
6. Re-run golden eval full pipeline if a reliable generator is available.
7. Package deployment bundle.
8. Move to larger-corpus or work-machine extraction.

## Sources

- Ollama API chat docs: https://docs.ollama.com/api/chat
- Ollama FAQ: https://docs.ollama.com/faq
- LanceDB vector indexing docs: https://docs.lancedb.com/indexing/vector-index
- LanceDB scalar indexing docs: https://docs.lancedb.com/indexing/scalar-index
- LanceDB reindexing docs: https://docs.lancedb.com/indexing/reindexing
- OpenAI evaluation best practices: https://developers.openai.com/api/docs/guides/evaluation-best-practices/
- OpenAI trace grading guide: https://developers.openai.com/api/docs/guides/trace-grading
