# Sprint 11 Work Sequence And To-Do

**Date:** 2026-04-06 MDT  
**Purpose:** Give a clear operator sequence for the current sprint so work can continue without guessing.  
**Audience:** Project owner / operator at work

---

## Bottom Line

This sprint is not a normal feature sprint.

This is a **recovery sprint** with one supporting **production-staging track**.

### The Recovery Problem

The current corpus appears to contain too many near-duplicate documents:

- `DOC`
- `DOCX`
- `PDF`
- signed variants
- export variants
- lightly edited copies

That means too much duplicate content survived into:

1. parsing
2. chunking
3. embedding
4. indexing
5. extraction

So the next big win is not tuning the current inflated index.  
The next big win is building a **canonical source list** and rebuilding from that.

### The Two Primary Tracks

**Track A: Recovery**
- one-time cleanup and rebuild preparation
- dedup before chunking
- create canonical file list
- rebuild from the cleaned source set

**Track B: Immediate Sidecar Progress**
- dedup pilot/review tooling from existing outputs
- structured-store exploitation from overnight outputs
- use the time productively even while workstation install issues are being repaired

Track A is the immediate main effort.  
Track B is worthwhile in parallel because it does not depend on the installer thread and turns existing artifacts into usable progress.

### Deferred Supporting Track

**AWS batch production staging** still matters, but it is no longer the first sidecar priority while recovery and installer repair are active.

It remains:

- request/response schema work
- controlled parallel batch submission design
- S3 staging
- result collection
- rate-limit measurement

---

## What Is Recovery Vs What Is Production

## Recovery Work

Recovery work is the part that exists because the first large build was done from a bloated source set.

It includes:

- cross-format duplicate discovery
- canonical-file selection
- duplicate audit output
- rebuilding from `canonical_files.txt`

This is a cleanup and correction step.

## Production Automation Work

Production automation is the part that should remain useful after recovery is done.

It includes:

- repeatable batch packaging
- controlled parallel processing
- S3 staging
- job manifests
- result collection
- rate-limit logging
- import back into the local search stack

This is not a cleanup step.  
This is the future repeatable processing path.

---

## What Has Already Been Built

### CorpusForge Recovery Tools

Already available:

- `INSTALL_WORKSTATION.bat`
- `COPY_TORCH_FROM_EXISTING_HYBRIDRAG.bat`
- `start_corpusforge.bat --dedup`
- `scripts\build_document_dedup_index.py`
- `scripts\run_pipeline.py --input-list <canonical_files.txt>`

Recovery outputs already supported:

- `document_dedup.sqlite3`
- `canonical_files.txt`
- `duplicate_files.jsonl`
- `dedup_report.json`

### Workstation Install Docs

Already available:

- `docs\WORKSTATION_STACK_INSTALL_2026-04-06.md`
- `C:\CorpusForge\docs\WORKSTATION_SETUP_2026-04-06.md`
- `C:\CorpusForge\docs\TORCH_REUSE_FROM_EXISTING_HYBRIDRAG_2026-04-06.md`

### Verified Immediate Overnight Asset

The most useful overnight output available right now is the populated structured store in:

- `C:\HybridRAG_V2\data\index\entities.sqlite3`

Verified current counts:

- `entities`: `20,450`
- `relationships`: `4,683`
- `extracted_tables`: `3,397`

This means the immediate sidecar work should focus on auditing and exploiting the structured store, not assuming the latest export package already contains useful enriched text.

---

## Sprint 11 Objective

Build confidence in the recovery pass and create the canonical rebuild input.

This sprint is complete only when:

- the dedup recovery tool runs on the real source tree or a meaningful slice
- duplicate decisions look sane on reviewed samples
- `canonical_files.txt` is trustworthy enough to become rebuild input

---

## Exact Work Order

## Phase 0: Get The Source Folder And Start Recovery Dedup

This is now the immediate main action.

If the full source folder is available tomorrow, start the recovery dedup run on the high-capacity local machine immediately. Do not wait for workstation installs to become perfect before beginning this step.

### Step 0.1: Pull latest repos

Pull:

- `CorpusForge`
- `HybridRAG_V2`

### Step 0.2: Confirm CorpusForge is runnable on the high-capacity local machine

This machine is the first real recovery runner.

### Step 0.3: Start the recovery dedup pass as soon as the source tree is available

Preferred operator path:

```text
start_corpusforge.bat --dedup
```

CLI path:

```powershell
cd C:\CorpusForge
.\.venv\Scripts\python.exe scripts\build_document_dedup_index.py --input <SOURCE_FOLDER>
```

---

## Parallel Enablement Thread: Recover The Workstations

This thread still matters because the assembly-line plan assumes working `CorpusForge` and `HybridRAG_V2` installs on the workstations.

The workstations become the background preprocessors, shard helpers, and local extraction lanes after recovery dedup and rebuild are underway.

### Step P.1: Install CorpusForge

Run:

```text
INSTALL_WORKSTATION.bat
```

If torch download is blocked, run:

```text
COPY_TORCH_FROM_EXISTING_HYBRIDRAG.bat
```

Then continue with the remaining install steps.

### Step P.2: Install HybridRAG V2

Run:

```text
INSTALL_WORKSTATION.bat
```

This installer is now workstation-aware. Missing API keys and OCR tools still matter, but they no longer break the install batch by themselves.

---

## Phase 1: Run The Recovery Dedup Pass

This is the main sprint action.

### Goal

Process the source tree and build a canonical file list before any rebuild.

### What This Produces

- `document_dedup.sqlite3`
- `canonical_files.txt`
- `duplicate_files.jsonl`
- `dedup_report.json`

### What To Pay Attention To

- total candidate files scanned
- number of duplicate families found
- canonical file count
- percentage reduction
- whether the duplicate families look plausible

---

## Phase 2: Review Duplicate Samples Before Rebuild

Do not skip this.

### Goal

Confirm the tool is removing the right files before spending days rebuilding.

### Review Method

Open `duplicate_files.jsonl` and inspect a sample of:

- same-name `docx/pdf` families
- signed PDF variants
- large duplicate families
- edge cases where one file may have slightly more content than another

### Questions To Ask

- did it keep the best editable version?
- did it keep the version with the best text quality?
- did it accidentally merge documents that are actually meaningfully different?

### Rule

Do **not** start the full rebuild until this sample review looks sane.

---

## Phase 3: Freeze The Canonical List

Once the sample review looks correct, treat `canonical_files.txt` as the rebuild input.

That file becomes the controlled input to the next large run.

---

## Phase 4: Rebuild From Canonical Files

This is likely the first expensive time step after recovery.

### Goal

Re-run CorpusForge on the cleaned source set instead of the raw folder.

### Command

```powershell
cd C:\CorpusForge
.\.venv\Scripts\python.exe scripts\run_pipeline.py --input-list <PATH_TO_CANONICAL_FILES.TXT>
```

### Expected Outcome

- fewer files processed
- fewer chunks created
- smaller output package
- smaller downstream V2 index
- less later extraction cost and time

### Important Rule

Build side-by-side. Do not overwrite the current index first.

---

## Phase 5: Import Into A Fresh V2 Index

### Goal

Create a fresh reduced V2 path using the rebuilt export.

### Why

This allows a clean before/after comparison without risking the current working index.

### Capture These Numbers

- source file count before and after
- chunk count before and after
- index size before and after
- import time
- later extraction candidate volume

---

## Phase 6: Prepare For The AWS Batch Path

This can happen after the immediate sidecar work, but it is not the first blocking step.

### Goal

Be ready for AWS batch processing without depending on the final endpoint being ready yet.

### What To Build Or Confirm

- batch manifest format
- request JSON schema
- response JSON schema
- `10`, `50`, and `100` chunk test packs
- S3 folder layout
- result collector and importer
- rate-limit and throughput logging

### Why This Can Start Now

These pieces do not require the final OSS endpoint URL to exist yet.

They are the safe staging work:

- packaging
- manifests
- S3 structure
- concurrency controls
- result handling

---

## AWS Batch Strategy

The AWS side should be designed as controlled parallel processing, not a giant dump of all chunks at once.

The target operating mode for a while is an assembly line:

- dedup and rebuild create the reduced corpus
- shard packaging keeps a ready queue
- local lanes process their assigned tiers continuously
- AWS is continuously fed with validated shard manifests
- merge/import keeps consuming finished shards in parallel

### Correct Pattern

1. small smoke batch
2. medium validation batch
3. larger controlled batch
4. only then production-scale rollout

### Recommended Ramp

- batch size `10`
- then `50`
- then `100`

Concurrency:

- start with `2`
- then `4`
- then `8`

Only increase if:

- latency stays stable
- errors stay low
- throttling does not show up

### What To Measure

- submit time
- completion time
- bytes per batch
- chunks per batch
- failures
- retries
- throttling or backoff events

---

## What Not To Do

- do not rebuild from the raw source tree again until the recovery pass is reviewed
- do not treat exact file hashes as sufficient dedup
- do not overwrite the current working index first
- do not send unbounded parallel requests to AWS just because the instance has many CPUs
- do not assume the final endpoint shape until the real AWS OSS deployment details are confirmed

---

## Immediate To-Do List

### First Priority

1. Pull latest `CorpusForge` and `HybridRAG_V2`
2. Get the source folder onto the high-capacity local machine
3. Start the recovery dedup pass on the real source tree or a meaningful slice
4. Keep workstation install recovery moving in parallel
5. Review duplicate samples
6. Freeze `canonical_files.txt`

### Second Priority

7. Generate duplicate-review samples and canonical-choice rules from existing dedup outputs
8. Audit the populated structured store and document immediate useful commands/reporting
9. Prepare the rebuild run from the canonical file list
10. Keep AWS staging and shard packaging ready so the later flow behaves like an assembly line instead of a stop/start batch
9. Build into a fresh output path
10. Import into a fresh V2 index path
11. Record before/after metrics

### Third Priority

12. Stage AWS batch packaging and manifests
13. Define the request/response schema
14. Prepare `10 -> 50 -> 100` batch tests for when the endpoint is ready

---

## Success Looks Like This

At the end of this sprint, we should have:

- a trusted dedup recovery output
- a reviewed canonical source list
- a clear rebuild input
- a side-by-side rebuild plan
- an AWS batch path that is staged and ready for endpoint integration

---

## Reference Docs

- [DEDUP_RECOVERY_PLAN_2026-04-06.md](/C:/HybridRAG_V2/docs/DEDUP_RECOVERY_PLAN_2026-04-06.md)
- [SPRINT_11_14_GAMEPLAN_2026-04-06.md](/C:/HybridRAG_V2/docs/SPRINT_11_14_GAMEPLAN_2026-04-06.md)
- [WORKSTATION_STACK_INSTALL_2026-04-06.md](/C:/HybridRAG_V2/docs/WORKSTATION_STACK_INSTALL_2026-04-06.md)
