# QA Report -- GUI Import RAM Fix

**Reviewer:** CoPilot+ (QA)
**Date:** 2026-04-17 MDT
**Target:** `scripts/import_extract_gui.py`, `scripts/import_embedengine.py`, `tests/test_gui_import_streaming_and_gpu_label.py`
**Source checklist:** CoPilot+'s GUI Import RAM Fix checklist (2026-04-17)
**Code freeze in effect:** yes -- no edits made during this QA

---

## Verdict

**CONDITIONAL PASS.** Code-level QA is strong. Two push-safety findings (F2, F3) must be resolved before the test file is `git add`-ed or the changed GUI file is pushed. Real-hardware 10M-chunk walk-away QA still required before sign-off.

---

## Code-level verification (all PASS)

| # | Claim | Evidence |
|---|-------|----------|
| 1 | 73 tests pass | Re-ran exact sweep: `73 passed, 3 warnings in 10.92s` |
| 2 | GUI import no longer calls `load_export` | grep on `scripts/import_extract_gui.py`: zero matches. Uses `prepare_streaming_import` + `stream_export_batches` only |
| 3 | Vectors memory-mapped, not loaded | `import_embedengine.py:323` `np.load(..., mmap_mode="r")` |
| 4 | chunks.jsonl iterated line-by-line | `import_embedengine.py:373-395` file iterator with per-line `json.loads`, bounded `batch` list |
| 5 | Per-batch Python-level cleanup | `import_extract_gui.py:334-336` explicit `batch_chunks = None`, `batch_vecs = None`, `records = None` |
| 6 | GPU/RAM helpers separated | `_get_gpu_info()` (l.109-130) has zero memory queries. `_get_ram_info()` (l.133-149) has zero CUDA calls. `torch.cuda.mem_get_info` is called only inside `_refresh_tier2_gpu_stat()` closure |
| 7 | VRAM never shown in Import or Tier 1 | `gpu_status` stat is set only inside Tier 2 block (l.652, 759, 772). Import sets only `ram_status` (l.229, 343, 348). Tier 1 sets only `ram_status` (l.554, 570) |
| 8 | Tier 1/Tier 2 periodic refresh | 2s interval refreshes added at l.553-555 (Tier 1 loop), l.755-760 (Tier 2 loop), plus Tier-boundary flushes at l.570, 771-772 |
| 9 | Malformed-line handling | `import_embedengine.py:380-387` emits `WARNING: skip malformed chunks.jsonl line N` and continues |
| 10 | Integrity check runs post-import | `import_extract_gui.py:364-388` calls `verify_ingest_completeness` and surfaces PASS/FAIL on the panel |
| 11 | Stop path clean | `import_extract_gui.py:298-302` breaks mid-stream, calls `store.close()`, routes to `_finish_stopped` |
| 12 | CLI `load_export` still reachable | `import_embedengine.py:180` intact, `test_load_export_still_available_for_cli_compat` passes |

---

## Claim validation -- operator-facing behavior

### "Streaming and purge, bounded peak RAM"

**Verified.** The path is:
- memory-mapped `vectors.npy` (never resident in whole)
- line-iterated `chunks.jsonl` with batch list capped at `INGEST_BATCH_SIZE`
- explicit `None` reassignment of batch-local refs before next iteration
- LanceDB `table.add(records)` per batch, no accumulation

Caveats that are legitimate, not defects:
- Python allocator does not shrink RSS aggressively -- Task Manager will plateau, not sawtooth
- Dedup set on re-import costs ~40B per chunk_id + set overhead (1-2 GB for 10M); skipped for fresh tables (l.266-285)
- FTS and IVF_PQ index build after ingest is LanceDB-internal and not streamed

### "GPU and RAM never conflated"

**Verified by construction.** Two separate helpers, two separate stat keys (`gpu_status` vs `ram_status`), phase-gated VRAM readout with an unambiguous `(Tier 2 VRAM free X.X / Y.Y GB)` prefix. The 2026-04-13 symptom (stale 23/24 GB VRAM shown as RAM during import) is no longer reachable -- no code path queries VRAM during IMPORT or TIER 1 REGEX phases.

---

## Findings

### F1 -- LOW -- Sanitizer command in checklist is invalid

The checklist says: `python sanitize_before_push.py --check finds no new NVIDIA workstation GPU/GeForce/RTX hits...`

Running that command today:
```
error: unrecognized arguments: --check
```

The script supports only `--apply` and `--archive-dir`. Dry-run is the default (no-arg). Corrected tester instruction:

```
.venv\Scripts\python.exe sanitize_before_push.py
```

Impact: tester cannot execute the sanitizer step as written. Low severity because the fix is trivially obvious, but ship the corrected command in any regenerated checklist.

### F2 -- MEDIUM -- `scripts/import_extract_gui.py` will be flagged on push

Running the sanitizer today against the current tracked state:
```
[WOULD SANITIZE] scripts/import_extract_gui.py
```

Root cause: the `_sanitize_gpu_name` docstring at line 92 contains the literal example string `"NVIDIA NVIDIA workstation GPU"` to illustrate what gets sanitized. The sanitizer's own pattern matches this.

Two resolution paths, both acceptable, operator's call:
1. Leave as-is, let `--apply` rewrite to `"NVIDIA workstation GPU"` on the push gate. Docstring loses its illustrative value.
2. Edit the docstring now to use a neutral placeholder (e.g. `"<vendor> <product-line> <model>"` or reference only the sanitizer pattern without reproducing the banned string).

Memory rule `feedback_sanitizer_scope.md` says sanitizer is a push-time gate and local dev keeps terms -- so option 1 is consistent with that rule. Flag for visibility only.

### F3 -- MEDIUM -- New test file will self-sanitize on push

`tests/test_gui_import_streaming_and_gpu_label.py` is currently untracked. Once `git add`-ed, the sanitizer will scan it and find ~10 hits (parametrize inputs, docstrings, banned-list constants, end-to-end assertion loops). `--apply` will rewrite every `"NVIDIA NVIDIA workstation GPU"` string to `"NVIDIA workstation GPU"` -- which will then break the very assertions the rewritten strings feed (`assert "NVIDIA workstation GPU" not in out` etc.).

Two resolution paths:
1. Add a sanitizer allowlist entry for this test file specifically (test needs the banned strings literally to prove they get scrubbed).
2. Rewrite the test to build the banned strings at runtime from hex-escaped or base64-encoded literals so no banned-word pattern appears in source, and the tests still prove the sanitizer logic.

Memory rule `feedback_sanitize_before_push.md` says `local commit -> sanitize -> push`. Sanitizer breaking the test is a real push-blocker, not theoretical. Resolve before the test file is committed and pushed.

---

## Checklist fidelity delta

Compared to CoPilot+'s posted checklist, these items need either clarification or correction:

| Item | Status | Note |
|------|--------|------|
| "python sanitize_before_push.py --check" | WRONG flag | use `.venv\Scripts\python.exe sanitize_before_push.py` |
| "sanitize_before_push.py still clean on tracked files before any push" | FAILS TODAY | `import_extract_gui.py` is dirty per F2 |
| "73 passed" sweep | MATCHES | 73 passed on current tree |
| "Tier 2 VRAM free number should visibly change..." | Requires real HW | cannot prove headless -- keep as human-eyes check on primary workstation |

---

## Still required for full sign-off (real-hardware)

The code-level QA proves the mechanisms. The user-reported defect (30+ GB RAM on 10M corpus, VRAM mislabel) can only be finally closed by a real walk-away run. Minimum additional QA:

- [ ] 10M-chunk CorpusForge export imported on primary workstation, peak RSS observed in Task Manager under the per-batch + dedup-set budget
- [ ] `nvidia-smi` side-by-side during IMPORT -- VRAM numbers on GPU 0 (or whichever Tier 2 lands on) do not move during the IMPORT or TIER 1 phases
- [ ] Tier 2 run with other GPU workloads on the box -- panel VRAM number moves visibly on the 2-second refresh interval
- [ ] Single-CUDA work machine run (RTX 4000 / RTX 3000 Pro Blackwell) -- stat panel still reads "NVIDIA GPU" with no model leak
- [ ] Stop button mid-stream -- LanceDB row count reflects only committed batches (integrity line prints correct numbers)
- [ ] Skip-Import path -- Tier 1 regex runs against existing LanceDB, RAM row updates, no banned token leaks

---

## What was NOT done in this QA (out of scope)

- No code edits (freeze in effect)
- No git operations
- No sanitizer `--apply` invocation
- No real-hardware 10M run (requires primary workstation session)
- No push to remote

---

Signed: Jeremy Randall (CoPilot+) | HybridRAG_V2 | 2026-04-17 MDT
