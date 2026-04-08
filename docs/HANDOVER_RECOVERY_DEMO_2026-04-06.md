# Handover Recovery Demo 2026-04-06

## Purpose

This handover is for the next implementation pass to continue without re-discovery.

The current work is no longer just about polishing the demo path.

It is now a recovery-and-rebuild effort with a clear path back to a stronger real-data demo.

---

## What This Project Is

The stack has three major roles:

1. `CorpusForge`
   - parses raw source files
   - OCRs scanned documents when needed
   - chunks, embeds, and exports packages

2. `HybridRAG_V2`
   - imports CorpusForge exports
   - serves retrieval, structured search, and question answering
   - runs eval, demo rehearsal, and structured extraction

3. AWS / OSS staging
   - overflow or scale lane for extraction/enrichment work when local capacity is not enough
   - especially relevant once representative chunk batches are ready

The current economics goal is to keep as much preprocessing local as possible, then use remote capacity selectively and intentionally.

---

## Current Dilemma

The current large corpus build is usable, but economically wrong.

Known facts:

- about five weeks were spent downloading and chunking the current corpus
- raw source size is about `700 GB`
- current index footprint is about `170 GB`
- a large share of the source set appears to be cross-format near-duplicates:
  - `DOC`
  - `DOCX`
  - `PDF`
  - signed variants
  - lightly edited exports
- the current enrichment backlog is about `6.9M` chunks
- a measured local extraction run with `phi4:14b-q4_K_M` produced about `33.2s/chunk`

That means the expensive work is happening too late.

Exact file-hash dedup and chunk-level dedup were not enough. The next major win is a recovery preprocessing stage before the next rebuild.

---

## Validated Current State

### Demo / Retrieval State

- Sprint 10 retrieval/generation path is functionally green on the isolated path.
- The remaining major problem is corpus economics and rebuild quality, not the isolated demo skeleton.

### Support-Slice QA Status

- Sprint 11A: `PASS`
  - `C:\HybridRAG_V2\scripts\structured_progress_audit.py`
  - `C:\HybridRAG_V2\docs\OVERNIGHT_ENRICHED_OUTPUTS_ACTION_PLAN_2026-04-06.md`

- Sprint 11B: `CONDITIONAL`
  - `C:\CorpusForge\scripts\review_dedup_samples.py`
  - `C:\CorpusForge\docs\DEDUP_REVIEW_GUIDE_2026-04-06.md`
  - document-level review path is good
  - chunk-level review path is not yet operator-meaningful enough for real human review

### Structured Store Counts

Verified current counts in `C:\HybridRAG_V2\data\index\entities.sqlite3`:

- `entities`: `20,450`
- `relationships`: `4,683`
- `extracted_tables`: `3,397`

### Overnight Extraction

As of the current handover:

- a live extraction run was started on `2026-04-06 20:35` local time
- command path: `scripts\overnight_extraction.py`
- explicit source DB:
  - `{USER_HOME}\HybridRAG3_Clone1\data\index\hybridrag.sqlite3`
- progress moved from `2000` to `2030` extracted chunks during the current session
- writes to:
  - `C:\HybridRAG_V2\data\index\entities.sqlite3`
  - `C:\HybridRAG_V2\data\extraction_progress.json`

Important caveat:

- the current overnight extractor is safe as a single lane
- it is not yet a clean dual-GPU production script
- the `--gpu` flag does not currently guarantee true runner isolation because the live Ollama routing is not fully separated

### Workstation Install State

Workstation laptop:

- `HybridRAG_V2` torch/CUDA was confirmed:
  - `2.7.1+cu128`
  - `12.8`
  - `True`
- `CorpusForge` install reached the final verification path with OCR tools present
- `tesseract` and `pdftoppm` are present on the laptop
- `phi4:14b-q4_K_M` was being pulled on the laptop during the latest session

Workstation desktop:

- still needs install recovery and verification
- remains the intended future `24/7` chunking lane once stable

---

## Recovery Plan

### Main Principle

Do not optimize the wrong corpus.

The next real win is to build a canonical source list before rechunking and re-embedding.

### Recovery Sequence

1. Backup source to the primary local machine.
2. Run document-level recovery dedup on the primary local machine.
3. Review duplicate samples before trusting the reduction.
4. Freeze `canonical_files.txt`.
5. Rebuild from the canonical list on the primary local machine.
6. Import the rebuilt export into a fresh V2 store.
7. Re-run eval and demo checks on the rebuilt path.

### Why The Primary Local Machine First

Use the primary local machine for the first real recovery run because:

- parser and OCR stack there is already trusted
- it is the safest machine for the first canonical rebuild
- workstations were still being repaired and verified during this session

### Role Of The Workstations

Workstation laptop:

- helper lane after full verification
- controlled chunking tests
- shard support
- AWS probe/export support

Workstation desktop:

- intended future `24/7` chunking lane
- fixed location
- best fit for uninterrupted chunking once install issues are fixed

---

## Next Sprint Sequence

The immediate next sprint changed after the workstation AWS probe attempt exposed a more basic blocker: `CorpusForge` itself must be operator-trustworthy for chunk generation before the recovery rebuild can be staged cleanly from work machines.

### Sprint 11: Forge GPU Operator Readiness

Goal:

- make `CorpusForge` stable and operator-meaningful for workstation chunk/export generation

Key outputs:

- repo-root config path hardening
- GUI/CLI preflight visibility for deferred and unsupported formats
- controlled workstation export proof
- trustworthy `skip_manifest.json` accounting for deferred drawing formats

### Sprint 12: Recovery Dedup

Goal:

- build the canonical source list before any rebuild

Key outputs:

- `document_dedup.sqlite3`
- `canonical_files.txt`
- `duplicate_files.jsonl`
- `dedup_report.json`

Key warning:

- use the document-level review path first
- do not rely on chunk-level review as final human-review tooling yet

### Sprint 13: Canonical Rebuild

Goal:

- run `CorpusForge` on the canonical list instead of the raw folder

Key outputs:

- fresh reduced export package
- fresh reduced V2 store
- before/after metrics:
  - file count
  - chunk count
  - index size
  - import time

### Sprint 14: Structured Promotion On The Rebuilt Corpus

Goal:

- apply structured extraction and retrieval validation on the smaller rebuilt corpus

Key outputs:

- extraction-time comparison against the bloated corpus
- re-run of eval and demo rehearsal on the rebuilt path
- confirmation that dedup did not remove required business content

### Sprint 15: Operator Hardening Back To Demo

Goal:

- make the recovery path and rebuilt demo path repeatable by a non-programmer operator

Key outputs:

- one-button runbook for:
  - dedup
  - canonical rebuild
  - import
  - smoke-check
- clearer stop/resume and output guidance
- repeatable path back to a real-data demo

---

## Immediate Priorities For The Next Pass

1. Finish `CorpusForge` workstation chunk/export proof.
2. Repair and verify workstation desktop installs.
3. Backup source to the primary local machine.
4. Start recovery dedup on the primary local machine.
5. Review duplicate samples before starting the full rebuild.
6. Keep using the workstation laptop for controlled export and AWS probe batches.

---

## Things That Are Safe To Do

- run a controlled `CorpusForge` export on the workstation laptop
- use that export for AWS probe timing and token measurements
- continue single-lane overnight extraction on the primary local machine
- use document-level dedup review output for real review work

---

## Things That Are Not Yet Safe To Assume

- do not assume chunk-level dedup review output is ready for human production review
- do not assume dual-GPU overnight extraction is production-safe with the current script
- do not overwrite the current main index before the canonical rebuild is validated
- do not assume the real source tree will reduce all the way to `3M` chunks; that is an aggressive target, not a guarantee

---

## Controlled AWS Probe Tonight

Use `CorpusForge`, not `HybridRAG_V2`, to create the chunk export.

Recommended path:

- use a controlled source folder
- keep output isolated
- prefer speed over enrichment for the first AWS timing pass

See also:

- `C:\CorpusForge\config\config.aws_probe_fast.yaml`

---

## Exact Machine Roles Going Forward

Primary local machine:

- source backup
- recovery dedup
- first canonical rebuild
- overnight structured extraction

Workstation desktop:

- future nonstop chunking lane once install recovery is complete

Workstation laptop:

- controlled export generation
- AWS probe batches
- shard/helper lane after full verification

Toaster:

- manifests
- audit scripts
- bookkeeping
- support tasks, not heavy model work

---

## If The Next Pass Only Reads One Thing

Read:

- `C:\HybridRAG_V2\docs\SPRINT_11_14_GAMEPLAN_2026-04-06.md`
- `C:\HybridRAG_V2\docs\SPRINT_11_WORK_SEQUENCE_AND_TODO_2026-04-06.md`
- `C:\HybridRAG_V2\docs\OPERATION_FREELOAD_TIERING_AND_REASSEMBLY_2026-04-06.md`
- this handover

Then continue from:

1. workstation verification
2. source backup
3. recovery dedup
4. duplicate sample review
5. canonical rebuild
