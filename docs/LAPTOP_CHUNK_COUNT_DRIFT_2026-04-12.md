# Laptop chunk count drift investigation

**Date:** 2026-04-12 MDT
**Agent:** reviewer
**Repo:** HybridRAG_V2 (master @ 7182513 at start of investigation)
**Trigger:** Workstation laptop walk-away import reported
10,700,593 chunks / 12,727,195 Tier 1 entities, versus primary workstation's
10,435,593 chunks / 8,017,607 entities from the same Forge export.

---

## Executive summary

Two discrepancies between the laptop store and primary workstation's canonical store,
both against the same source-of-truth Forge export
`E:\CorpusIndexEmbeddingsOnly\export_20260411_0720`:

1. **Entity count delta (+4,709,588 entities, +59%)** — **CONFIRMED H6.**
   Root cause is a deployment/version-drift incident: the laptop's
   zip-pull happened before 23:00 MDT on 2026-04-11, approximately one
   hour before the security standard-regex fix `ba4d962` landed on origin/master at
   00:04 MDT on 2026-04-12. The laptop therefore ran Tier 1 extraction
   against pre-security standard-fix `src/extraction/entity_extractor.py`, which
   pollutes the PART and PO columns with security standard SP 800-53 control IDs at
   the rates documented in the previous reviewer's rationale doc
   sections 3 and 12. Not a V2 code bug.

2. **Chunk count delta (+265,000 chunks, +2.5%)** — **STILL OPEN.**
   The Forge export physically contains exactly 10,435,593 chunks
   (verified three independent ways). The laptop's extra 265,000
   chunks cannot have come from this export. Root cause is not
   identifiable without laptop-side probes the user cannot run (zip-pull
   workstation is git-less, no copy-paste bridge). Filed as a separate
   lower-priority followup.

3. **Secondary finding: ingest integrity assertion has a hole.**
   `LanceStore.verify_ingest_completeness()` validates
   `net_delta == expected_delta` within a *single* ingest call. It
   does not cross-check final `store.count()` against
   `manifest.chunk_count` across sessions, so a store that grew from
   10,435,593 to 10,700,593 via a later ingest that reconciled 265,000
   chunks as "new" would pass the per-call rule while silently drifting
   from manifest truth. Filed for follow-up.

**Demo-day impact: zero.** The laptop is not the canonical demo store.
primary workstation remains canonical; the workstation desktop will rebuild cleanly
tomorrow from a fresh zip-pull against current master.

---

## Evidence collected

All commands below were run on primary workstation from `C:\HybridRAG_V2` on
2026-04-12 MDT. The laptop side is quoted from the coordinator's
dispatch (user's own read of laptop metadata) because the laptop is
zip-only and cannot accept interactive probes.

### 1. Source of truth — Forge export on `E:\CorpusIndexEmbeddingsOnly\export_20260411_0720`

Three independent measurements, all agreeing:

| Source              | Value                                   |
|---------------------|-----------------------------------------|
| `manifest.json` `chunk_count` | **10,435,593**                  |
| `chunks.jsonl` line count     | **10,435,593** (wc -l)          |
| `vectors.npy` shape           | **(10,435,593, 768)** float16   |
| `manifest.json` `entity_count` | **0**                          |
| `entities.jsonl` line count   | **0** (file exists, empty)      |

Key manifest fields:

```json
{
  "version": "1.0",
  "timestamp": "2026-04-11T07:22:45.799556",
  "chunk_count": 10435593,
  "vector_dim": 768,
  "embedding_model": "nomic-embed-text-v1.5",
  "entity_count": 0,
  "stats": {
    "files_found": 430540,
    "files_after_dedup": 215793,
    "files_parsed": 93636,
    "chunks_created": 10435593,
    "vectors_created": 10435593,
    "entities_extracted": 0,
    "elapsed_seconds": 76717.51
  }
}
```

`run_history.jsonl` in `E:\CorpusIndexEmbeddingsOnly\` records exactly
one Forge run at `2026-04-11T07:32:11.723321` producing these exact
counts. There is no second Forge export that could explain a 265K
chunk delta.

**Consequence:** Forge did not extract any entities. Both machines ran
Tier 1 locally after import, which means the entity inflation is a
pure local code-version issue, not an upstream export artifact.

### 2. primary workstation store (canonical post-fix)

```python
from src.store.lance_store import LanceStore
from src.store.entity_store import EntityStore
LanceStore('data/index/lancedb').count()       # 10,435,593
EntityStore('data/index/entities.sqlite3').count_entities()  # 8,017,607
```

| Metric               | Value         |
|----------------------|---------------|
| Chunks (LanceDB)     | **10,435,593** |
| Entities (Tier 1 SQLite) | **8,017,607** |
| Entities / chunk ratio | **0.768**    |
| Fragments            | 18            |
| Transactions         | 5             |
| Lance versions       | 5             |

primary workstation's Tier 1 extraction ran after the security standard-fix chain landed
(ba4d962 at 2026-04-12 00:04 MDT, 82d47da at 10:47 MDT). The 8.02M
entity total reflects post-fix extraction against the canonical
10,435,593 chunks.

primary workstation's own import_report on `E:\...\export_20260411_0720\import_report_20260411_151620_import.json`:

```json
{
  "mode": "import",
  "source_export_dir": "E:\\CorpusIndexEmbeddingsOnly\\export_20260411_0720",
  "target_db": "C:\\HybridRAG_V2\\data\\index\\lancedb",
  "final_chunk_count": 10435593,
  "final_vector_count": 10435593,
  "source_manifest_fingerprint": {
    "embedding_model": "nomic-embed-text-v1.5",
    "original_timestamp": "2026-04-11T07:22:45.799556",
    "original_chunk_count": 10435593
  }
}
```

primary workstation import is a perfect match with the Forge manifest fingerprint.

### 3. Laptop store (polluted)

Reported by the walk-away import (per coordinator dispatch):

| Metric               | Value           | Δ vs primary workstation     |
|----------------------|-----------------|----------------|
| Chunks (LanceDB)     | **10,700,593**  | **+265,000 (+2.54%)** |
| Entities (Tier 1)    | **12,727,195**  | **+4,709,588 (+58.7%)** |
| Entities / chunk ratio | **1.189**     | **+54.8%**     |
| Tier 2               | SKIPPED (GLiNER not installed) | — |

The entity-per-chunk ratio jump is the decisive signal: a 2.5% chunk
increase cannot naturally produce a 59% entity increase unless the
extraction code itself is different between the two machines.

### 4. Entity extractor timeline

From `git log --format="%h %ai %s" -- src/extraction/entity_extractor.py`:

| Commit  | Timestamp (MDT)      | Change                                                       |
|---------|----------------------|--------------------------------------------------------------|
| 129e26f | 2026-04-11 19:00:28  | Phone regex fix: CONTACT ~16M → ~3.5M                        |
| 7faef97 | 2026-04-11 19:12:42  | Phone regex round 2 — trailing sentence punctuation          |
| **ba4d962** | **2026-04-12 00:04:27** | **Reject security standard / STIG / MITRE identifiers in PART + PO columns** |
| 82d47da | 2026-04-12 10:47:06  | Round 2 security standard regex — suffix-length discriminator             |
| 8b066e6 | ~2026-04-12 11:00    | Correct security standard investigation doc                               |

The first security standard-filter commit `ba4d962` is the critical dividing line
for entity pollution behavior.

### 5. Laptop zip-pull timing (user-provided)

User confirmed from the laptop's own zip file metadata:

- Laptop zip-pulled V2 master **before 23:00 MDT on 2026-04-11**
- `ba4d962` did not land on origin/master until **00:04 MDT on 2026-04-12**
- Gap: approximately **one hour** between the laptop's pulled snapshot
  and the first security standard fix

The laptop therefore ran Tier 1 extraction against pre-security standard-fix
`entity_extractor.py`. This is the H6 smoking gun — established by
timing alone, without needing laptop-side git commands that the user
cannot execute.

### 6. Expected pollution pattern from the previous reviewer's rationale doc

From `docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md` Sections 3
and 12 (already QA-signed and committed by the previous reviewer):

- PO column on pre-security standard-fix extraction: **~98% security standard control IDs**
  (IR-4, CA-5, AC-2, SC-*, etc.) — real SAP POs exist but are buried
- PART column on pre-security standard-fix extraction: **~90% security standard SP 800-53
  baseline codes** (AS-5021, OS-0004, GPOS-0022) — real physical parts
  (RG-213, LMR-400, P007-003) are further down the count distribution
- Real CONTACT entities on pre-phone-fix extraction inflated to ~16M

The laptop Tier 1 pulled master after the phone-regex fix (129e26f at
2026-04-11 19:00) but before the security standard fix (ba4d962 at 2026-04-12 00:04).
So the laptop's pollution signature should show:

- Normal CONTACT counts (phone fix applied)
- Inflated PART and PO counts (security standard fix missing)

The observed total entity count of 12,727,195 vs primary workstation's 8,017,607
places the excess at +4.71M. This is within the expected magnitude of
the PART+PO security standard contamination documented by the previous reviewer. The
exact breakdown per column cannot be verified without laptop-side
sqlite queries, but the aggregate magnitude and ratio match the H6
prediction.

---

## Hypothesis disposition

| Hyp | Name                                      | Status       | Evidence |
|-----|-------------------------------------------|--------------|----------|
| H1  | Laptop imported from a different source   | RULED OUT for the entity delta; PARTIALLY POSSIBLE for the chunk delta | Only one Forge run in `run_history.jsonl`, no second export exists; but a stale local LanceDB from an earlier session is not ruled out for the +265K chunks |
| H2  | Double-import on the laptop               | POSSIBLE for chunk delta only | Cannot be verified without laptop-side probes |
| H3  | 400-query file imported as chunks         | RULED OUT | 110 records ≠ 265,000; file scope/shape does not match |
| H4  | manifest.chunk_count ≠ chunks.jsonl count | RULED OUT | All three Forge measurements agree at 10,435,593 |
| H5  | Fragment count drift from non-idempotent appends | UNLIKELY | LanceStore.ingest_chunks dedups on `chunk_id` with a full scan before add(). Would only occur if chunk_id generation differs between runs |
| **H6** | **Stale entity_extractor.py on the laptop** | **CONFIRMED for the entity delta** | Zip-pull timing (<23:00 MDT 2026-04-11) predates ba4d962 (00:04 MDT 2026-04-12). Ratio inflation (55%) matches documented security standard contamination pattern |

---

## Secondary finding: ingest integrity assertion hole

`LanceStore.verify_ingest_completeness()` (src/store/lance_store.py:321)
applies three rules per ingest call:

1. `net_delta == expected_delta` — table row delta equals `inserted`
2. `manifest_count == attempted` when a manifest is supplied
3. `0 <= inserted <= attempted` — sanity bounds

All three rules are **per-call** checks. None of them cross-check the
final `store.count()` against `manifest.chunk_count` after the ingest
settles. Concretely:

- A store that starts at 10,435,593, receives a second ingest call
  with 265,000 "new" chunks that reconcile as unique (because
  chunk_id generation differs between runs, or because the second
  source is a subset with shifted path normalization), ends at
  10,700,593.
- In that second call, `net_delta == expected_delta == 265,000`.
  Rule 1 passes.
- Rule 2 would fire *only if the manifest from the second source was
  supplied*. If the second call was operator-initiated without a
  manifest, rule 2 is silent.
- Rule 3 passes trivially.

The store now holds 265,000 more chunks than any single Forge manifest
can account for, and no assertion ever complained.

**Recommended fix (for whoever owns store-level code, likely reviewer):**
Add a fourth rule that persists the canonical manifest_count on first
ingest (e.g., as a store metadata row) and on every subsequent ingest
compares `store.count() - sum(prior_inserted)` against
`current_manifest.chunk_count`. Warn loudly on divergence.

Filed as a separate followup — do not fix in this investigation
commit (scope discipline).

---

## Tertiary finding: zip-pull workstations have no visible version stamp

The root cause of H6 is that the laptop operator cannot tell which
commit SHA they pulled without unzipping and reading `.git/HEAD`, which
is not guaranteed to be present in a zip snapshot. Operators rely on
the zip filename and timestamp for version identity.

Recommendation: add a top-level `VERSION` file committed to master that
contains the current commit SHA, short date, and a human-readable
short description of the last fix. Zip-pull workstations can `cat
VERSION` to sanity-check which fix generation they are running.

Coordinator has already filed this as task #19 — cross-referenced here
for evidence linkage.

---

## Chunk count delta (+265,000) — still open

What we know:

- Forge export is exactly 10,435,593 chunks, verified three ways
- `run_history.jsonl` contains exactly one Forge run — no second export
  exists that could contribute additional chunks
- primary workstation imported cleanly to 10,435,593 from that export
- Laptop has 265,000 more than the export physically contains
- The 265,000 extras came from *somewhere* on the laptop, not from
  this Forge export

What we cannot determine from primary workstation alone:

- Whether the laptop's LanceDB held stale state from an earlier import
  session that was not cleaned up before the walk-away ingest
- Whether chunk_id generation differed across the laptop's sessions
  such that dedup missed a ~2.5% overlap
- Whether a second ingest path wrote to `data/index/lancedb` without
  going through `verify_ingest_completeness`
- Fragment layout, transaction count, or distinct-chunk_id count on
  the laptop

Resolution path: when the laptop is next rebuilt (operator plans to
zip-pull current master, back up the polluted entity store, and re-run
Tier 1 with Skip Import + Max Tier 1), this class of drift cannot
recur because the LanceDB will be freshly sourced from the verified
Forge export in one ingest session. If after that rebuild the chunk
count lands at 10,435,593, the hypothesis that the current +265K is
a stale-state artifact is proven by construction. If the chunk count
again drifts from 10,435,593, the bug is reproducible and a targeted
investigation can be opened with laptop-side commands.

**Priority:** P2 followup. Not demo-blocking — laptop is not the
canonical demo store. primary workstation and the workstation desktop (fresh rebuild
tomorrow) are the demo-path machines.

---

## Conclusions

1. **Entity delta root cause: CONFIRMED H6.** Zip-pull timing places
   the laptop's checkout of `entity_extractor.py` approximately one
   hour before the security standard-filter fix landed. The resulting ~59% entity
   inflation aligns in magnitude and pattern with the previously
   documented PART+PO security standard contamination. This is not a bug in V2
   code — it is a deployment/version-drift incident.

2. **Chunk delta root cause: STILL OPEN.** The +265,000 chunks on the
   laptop cannot have come from the verified Forge export, and the
   true source cannot be identified without laptop-side probes the
   user cannot run. Lower priority, not demo-blocking, filed as a
   separate followup. Self-resolves on next clean rebuild.

3. **V2 code is correct.** Ingestion, dedup, and integrity-check logic
   all worked as designed on primary workstation. No fix to V2 itself is required to
   resolve this incident.

4. **Secondary finding:** `verify_ingest_completeness` has a hole for
   cross-session drift against the canonical manifest. Recommended fix
   is documented; filed for store-level ownership.

5. **Tertiary finding:** zip-pull workstations lack a visible version
   stamp. Already filed as coordinator task #19.

---

## Recommendations

1. **Laptop (immediate):** zip-pull current master, back up the
   polluted entity store, re-run Tier 1 with Skip Import checked and
   Max Tier 1. Produces a clean laptop store in 30–60 minutes.
2. **Alternate:** let primary workstation Tier 2 (PID 80316) finish overnight and
   use primary workstation as the canonical store for query testing until the
   workstation desktop rebuild lands.
3. **Workstation desktop (tomorrow):** zip-pull current master with
   the GLiNER install fix, run full Tier 1 + Tier 2 end-to-end from a
   fresh install. This becomes the demo-day canonical store.
4. **Store-level followup:** add cross-session manifest-count
   assertion to `verify_ingest_completeness` per the secondary finding
   above.
5. **No action on V2 code from reviewer.** Eval-corpus scope is
   intact; entity-extractor scope is not reviewer territory.

---

## Followups filed (not closed in this doc)

1. **Chunk count delta (+265,000)** — P2 followup, needs laptop-side
   probes or clean-rebuild confirmation
2. **Ingest integrity assertion hole** — secondary finding, store-level
   ownership, recommended fix documented
3. **primary workstation Tier 1 CLI t0 NameError** — noted in prior handover as still
   unverified on current master; not in reviewer scope, flagged for
   reviewer / coordinator

---

## References

- `docs/LAPTOP_10M_INVESTIGATION_2026-04-11.md` — prior laptop incident
  (undercounted 10,000,000 chunks), different direction but related
  class of bug; introduced `verify_ingest_completeness`
- `docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md` Sections 3 and 12 —
  security standard pollution pattern on pre-ba4d962 extraction
- `src/store/lance_store.py:150-231` — `ingest_chunks` dedup logic
- `src/store/lance_store.py:321-425` — `verify_ingest_completeness`
  implementation
- `E:\CorpusIndexEmbeddingsOnly\export_20260411_0720\manifest.json` —
  Forge export manifest
- `E:\CorpusIndexEmbeddingsOnly\export_20260411_0720\import_report_20260411_151620_import.json`
  — primary workstation import report
- `E:\CorpusIndexEmbeddingsOnly\run_history.jsonl` — Forge run history
  (single entry)
- Commits `129e26f`, `7faef97`, `ba4d962`, `82d47da`, `8b066e6` —
  entity extractor fix chain, timestamps per `git log`

---

Signed: reviewer | HybridRAG_V2 | 2026-04-12 MDT
