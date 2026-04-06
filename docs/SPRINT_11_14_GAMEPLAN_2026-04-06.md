# Sprint 11-14 Game Plan

**Date:** 2026-04-06 MDT  
**Prepared during:** Sprint 10 closeout after the dedup recovery issue was surfaced  
**Purpose:** Replace the previous latency-first next-sprint plan with a recovery-first plan.

---

## Why The Plan Changed

The Sprint 9/10 isolated path is functionally green, but a more serious economics problem was discovered:

- roughly five weeks were spent downloading and chunking the current corpus
- the current index footprint is about `170 GB`
- a large share of the source set appears to be cross-format near-duplicates:
  - `DOC` / `DOCX` and `PDF`
  - signed variants
  - lightly edited exports
  - document families that differ by only a few lines

This means the expensive work is happening too late. Exact file-hash dedup was not enough, and chunk-level dedup only catches the problem after parsing, chunking, embedding, and often extraction have already been paid for.

The new immediate priority is a **recovery preprocessing stage** ahead of re-chunking.

---

## Current Decision

**Sprint 11 becomes a Recovery Dedup sprint.**

The goal is not to debate whether the current index is usable. It is.  
The goal is to stop rebuilding the next large index from a bloated source set.

The working assumption is:

- HybridRAG3 can likely rebuild a cleaned corpus in `3-5 days`
- the real leverage is preprocessing the source tree into a canonical file set
- the old exact-hash skip machinery still matters, but it must sit behind a better recovery-stage dedup pass

---

## Research Notes Driving The Plan

### Exact And Near-Duplicate Detection

- Google documents SimHash-based near-duplicate detection as a web-scale pattern for large repositories:
  - https://research.google/pubs/detecting-near-duplicates-for-web-crawling/
- `datasketch` documents MinHash LSH for Jaccard-threshold duplicate search:
  - https://ekzhu.com/datasketch/lsh.html
- `datasketch` also documents `MinHashLSHEnsemble` for **containment**, which is the better fit when one version contains almost all of another plus extra pages or signatures:
  - https://ekzhu.com/datasketch/lshensemble.html
- OpenSearch exposes MinHash as a built-in similarity filter and explicitly frames it as document-similarity detection:
  - https://docs.opensearch.org/latest/analyzers/token-filters/min-hash/

### Practical Large-Scale Conflation

- Microsoft research describes a scalable shingling-first candidate-generation approach:
  - build shingles
  - cluster candidates by shared shingles
  - avoid comparing every document with every other document
  - https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/submission-v1.pdf

### Practical Implication For This Project

The recovery stage should follow a layered pattern:

1. **strict normalization + exact normalized hash**
2. **same-family near-duplicate comparison**
3. **containment-aware matching for appended or signed variants**
4. **canonical representative selection**
5. **audit trail and recovery manifest**

That is the industry-shaped version of this problem, and it fits the current architecture well.

---

## Sprint 11: Recovery Dedup Stage

### Goal

Create a new preprocessing stage in CorpusForge that builds a canonical source list before chunking so the next rebuild is materially smaller and cheaper.

### Slices

| Slice | Work | Status |
|-------|------|--------|
| 11.1 | Recovery-stage design doc: cause, economics, recovery sequence, operator workflow | TODO |
| 11.2 | Focused file discovery for `PDF`, `DOC`, `DOCX` only | DONE |
| 11.3 | Normalized extracted-text fingerprinting for cross-format exact matches | DONE |
| 11.4 | Same-family near-duplicate comparison with containment-style scoring | DONE |
| 11.5 | Persistent recovery outputs: sqlite index, canonical file list, duplicate audit | DONE |
| 11.6 | Pipeline consume path: `run_pipeline.py --input-list <canonical_files.txt>` | DONE |
| 11.7 | Recovery GUI for non-programmer operation | DONE |
| 11.8 | Pilot run on a controlled folder slice, measure duplicate reduction and false positives | TODO |
| 11.9 | Canonical-choice review rules: prefer best parse quality and best editable source | TODO |
| 11.10 | Signed/exported variant handling: appended pages, cover sheets, signature blocks | TODO |
| 11.11 | Recovery QA bundle: duplicate samples, false-positive audit, operator commands | TODO |
| 11.12 | Freeze the rebuild input list for the next corpus rebuild | TODO |

### Exit Criteria

- Recovery stage produces:
  - `document_dedup.sqlite3`
  - `canonical_files.txt`
  - `duplicate_files.jsonl`
  - `dedup_report.json`
- Canonical file list can be fed directly into CorpusForge reprocessing
- Pilot run shows a meaningful reduction in file count before chunking
- False positives are reviewed on a sample before full rebuild approval

### Key Commands

```powershell
cd C:\CorpusForge
.venv\Scripts\python.exe scripts\build_document_dedup_index.py --input C:\Path\To\Source
```

```powershell
cd C:\CorpusForge
.venv\Scripts\python.exe scripts\run_pipeline.py --input-list C:\CorpusForge\data\dedup\document_dedup_YYYYMMDD_HHMMSS\canonical_files.txt
```

### GUI Path

Use the normal launcher with a recovery switch:

```powershell
cd C:\CorpusForge
start_corpusforge.bat --dedup
```

This opens the dedicated recovery GUI instead of the normal pipeline monitor.

---

## Sprint 12: Canonical Rebuild

### Goal

Re-chunk and re-embed from the canonical file list instead of the raw source tree.

### Slices

1. Run CorpusForge on the canonical file list.
2. Build a fresh export package from the reduced corpus.
3. Import into a fresh V2 LanceDB path.
4. Compare:
   - source file count
   - chunk count
   - index size
   - import time
   - entity-extraction candidate volume
5. Preserve the old index until the rebuilt path clears QA.

### Exit Criteria

- Fresh reduced corpus export exists
- Fresh reduced V2 index exists
- Before/after metrics are documented
- Old index remains available as fallback

---

## Sprint 13: Structured Promotion On The Rebuilt Corpus

### Goal

Apply the structured-extraction work to the smaller rebuilt corpus so extraction cost and time are reduced at the source.

### Slices

1. Run structured extraction on the rebuilt corpus slice.
2. Measure extraction time savings versus the bloated corpus path.
3. Re-run golden eval and demo rehearsal on the rebuilt path.
4. Confirm that dedup did not remove required business content.

### Exit Criteria

- Golden behavior remains acceptable on the rebuilt corpus
- Extraction volume is materially reduced
- Retrieval correctness is not regressed by recovery-stage dedup

---

## Sprint 14: Operator Hardening

### Goal

Make the recovery path safe for repeated use by a non-programmer operator.

### Slices

1. One-button launcher guidance for:
   - recovery dedup
   - canonical rebuild
   - smoke-check
2. Add clearer status text and operator guidance in the GUI.
3. Document stop/resume behavior and known limits.
4. Prepare a short runbook for work-machine execution.

### Exit Criteria

- A non-author can launch the recovery pass and understand what output to use next
- Recovery output can be handed directly to the rebuild path without shell scripting

---

## Priority Order

1. Build canonical source list
2. Review duplicate samples
3. Rebuild from canonical list
4. Re-import into fresh V2 index
5. Re-run QA on the rebuilt corpus
6. Only then return to latency and polish work

---

## Guiding Principle

Do not spend more time optimizing the wrong corpus.

The next real win is not shaving milliseconds off the current inflated index.  
The next real win is rebuilding from a cleaner source set so every downstream stage becomes cheaper.
