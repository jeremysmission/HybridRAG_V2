# Dedup Recovery Plan

**Date:** 2026-04-06 MDT  
**Audience:** Non-programmer operator and project owner  
**Purpose:** Explain the problem, why it happened, what the fix is, and what happens next.

---

## Executive Summary

The current index is not a failure. It proved the pipeline works.

The problem is economic and operational:

- the current source set appears to contain many near-duplicate documents
- many of those duplicates are not exact byte-for-byte copies
- the most common pattern appears to be the same document in `DOC`, `DOCX`, and `PDF` forms
- some versions differ only by a signature page, export artifact, or a few small lines

Because the old dedup logic mainly worked on **exact file hashes**, too many of these near-duplicates survived into parsing and chunking.  
Once that happens, the project pays for the same content multiple times:

1. parse it again
2. chunk it again
3. embed it again
4. store it again
5. often extract entities from it again

That is why a recovery stage now makes sense.

---

## What Went Wrong

### What The Old Dedup Did Well

- exact file-hash duplicates
- `_1` suffix copies
- unchanged files across reruns

That is still useful and should stay.

### What The Old Dedup Missed

- `report.docx` and `report.pdf`
- `report.doc` and `report_signed.pdf`
- exported PDF copies of native Word docs
- versions with one extra approval page or one minor edit

These are **content-level near-duplicates**, not file-level duplicates.

So the old approach answered:

"Are these the exact same file bytes?"

But the real business question is:

"Are these effectively the same document for indexing purposes?"

That is the gap.

---

## Why This Matters So Much

We already spent about five weeks downloading and chunking to get the current index.

That means we should be careful about throwing work away.  
The recovery answer is not to start over blindly.  
The recovery answer is:

1. build a better preprocessing stage
2. create a canonical source list
3. rebuild once from the cleaned set
4. keep the current index as fallback until the rebuild is proven

If that works, the next rebuild should be much smaller, faster, and cheaper.

---

## The Solution

Add a **recovery preprocessing stage** before chunking.

### What The Recovery Stage Does

It looks only at the formats most likely to be duplicate families:

- `PDF`
- `DOC`
- `DOCX`

Then it does four things:

1. **Groups likely related files by normalized filename family**
   - example: `Report.docx`, `Report.pdf`, `Report_Final_1.pdf`

2. **Parses and normalizes extracted text**
   - removes page-number noise
   - collapses whitespace differences
   - reduces formatting-only differences

3. **Compares documents at the content level**
   - exact normalized-text fingerprint for true cross-format copies
   - near-duplicate scoring for files that are almost the same

4. **Chooses one canonical file to keep for rebuilding**
   - usually the best parsed, most complete, most editable version

The output is not just a yes/no result. It creates:

- a SQLite audit index
- a canonical file list
- a duplicate report

That means the dedup pass is reviewable and recoverable.

---

## Why This Approach Is Sound

This is not a random custom trick. It follows well-known large-scale duplicate-detection patterns:

- Google documents near-duplicate detection for very large corpora:
  - https://research.google/pubs/detecting-near-duplicates-for-web-crawling/
- `datasketch` documents MinHash LSH for duplicate candidate search:
  - https://ekzhu.com/datasketch/lsh.html
- `datasketch` documents containment-aware matching for cases where one version mostly contains another plus extra material:
  - https://ekzhu.com/datasketch/lshensemble.html
- OpenSearch documents MinHash as a document-similarity tool:
  - https://docs.opensearch.org/latest/analyzers/token-filters/min-hash/
- Microsoft research describes shingling as a scalable way to generate good candidate groups before expensive comparison:
  - https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/submission-v1.pdf

In plain English:

- do not compare everything with everything
- build good candidate families first
- compare content, not file bytes
- keep an audit trail
- rebuild from the canonical set

---

## What Has Already Been Built

In CorpusForge, the first version of this recovery path now exists:

- focused recovery script:
  - `C:\CorpusForge\scripts\build_document_dedup_index.py`
- recovery core logic:
  - `C:\CorpusForge\src\dedup\document_dedup.py`
- pipeline can now consume a canonical file list directly:
  - `C:\CorpusForge\scripts\run_pipeline.py --input-list ...`
- a dedicated recovery GUI path now exists behind:
  - `start_corpusforge.bat --dedup`

The recovery output includes:

- `document_dedup.sqlite3`
- `canonical_files.txt`
- `duplicate_files.jsonl`
- `dedup_report.json`

---

## Recovery Plan In Order

### Phase 1: Build The Recovery Index

Run the recovery-stage dedup pass over the source tree, focused on `PDF/DOC/DOCX`.

### Phase 2: Review Sample Duplicates

Before a full rebuild, inspect a sample of duplicate decisions to make sure the canonical choice is sensible and the false-positive rate is acceptable.

### Phase 3: Freeze The Canonical Source List

Once reviewed, treat `canonical_files.txt` as the rebuild input.

### Phase 4: Rebuild From The Canonical List

Run CorpusForge against the canonical list instead of the raw folder.

### Phase 5: Import Into A Fresh V2 Index

Do not overwrite the current index first. Build a fresh reduced index side by side.

### Phase 6: QA The Rebuilt Corpus

Compare:

- file count
- chunk count
- index size
- import time
- retrieval behavior
- extraction volume

### Phase 7: Promote Only If The Rebuild Clears QA

The current index remains the fallback until the rebuilt path is proven.

---

## What This Does Not Mean

It does **not** mean the past five weeks were wasted.

What they gave us:

- a working ingest and query pipeline
- a working GUI path
- working embeddings and retrieval
- working eval harnesses
- a real-world view of where the source set is inflated

That is exactly what exposed the need for the recovery stage.

---

## Main Risks

### Risk 1: False Positives

Two files can have similar names but different meaning.  
That is why the recovery pass should be reviewed on a sample before full rebuild approval.

### Risk 2: Weak PDF Text

Some PDFs parse poorly.  
If the PDF text is weak but the DOCX is strong, the canonical choice should prefer the better source.

### Risk 3: Signed Or Appended Variants

Some documents are the same core content plus one extra page.  
That is why containment-style logic matters, not just exact similarity.

---

## What You Should Expect Next

### Immediate Next Sprint

The next sprint is a **Recovery Dedup sprint**, not a polish sprint.

Its purpose is to produce a trusted canonical source list for the rebuild.

### After That

If the duplicate reduction is meaningful and the review sample looks good:

1. rebuild the corpus from the canonical list
2. import into a fresh V2 index
3. QA that rebuilt corpus
4. only then resume downstream optimization work

---

## Bottom Line

The real fix is not "dedup chunks a little better."

The real fix is:

**build a recovery-stage canonical source set before chunking, then rebuild once from that cleaner input.**

That is the safest path to cutting index size, extraction time, and downstream AI cost without gambling on the current inflated corpus.
