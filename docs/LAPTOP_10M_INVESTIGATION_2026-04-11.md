# Laptop LanceDB 10,000,000 chunk investigation

**Date:** 2026-04-11 MDT
**Agent:** reviewer
**Trigger:** Laptop's `C:\HybridRAG_V2\data\index\lancedb` landed at exactly
10,000,000 chunks instead of the canonical 10,435,593 primary workstation has.

## What I searched

A full sweep across V2 code, V2 config, and the installed lancedb wheel:

- Literal `10000000` / `10_000_000` / `1e7` — zero matches in any `.py`,
  `.yaml`, or `.bat` file.
- `limit=` defaults on argparse and config fields — nothing round.
- `store.ingest_chunks` and `scripts/import_embedengine.py::run_import` —
  straight-through, no row-count cap.
- `LanceTable.add` and the lancedb `SearchBuilder.to_batches` surface —
  no Python-side row/byte caps.
- Byte-level constants (`10 * 1024^3`, `10_737_418_240`, pyarrow int32
  buffer limits, max_rows_per_file, max_bytes_per_fragment) — zero matches.
- primary workstation's on-disk fragment layout: **18 fragments, 41.6 GB data, largest
  4.58 GB, avg 2.3 GB, ~4 KB per chunk.** 10M chunks on this ratio would
  occupy ~40 GB, not 10 GB, so the "10 GB cap" hypothesis fails the
  per-chunk math.

## Conclusion

There is no row-count or byte-level cap in V2 or in the lancedb 0.30.2
package that can explain the exact 10,000,000 stopping point. The most
plausible non-code causes are:

1. **Operator Stop at a psychologically round batch boundary.**
   `INGEST_BATCH_SIZE = 1000`; any multiple of 1000 is a clean stop
   point; progress UI reading "10,000,000 / 10,435,593" is a common
   human stopping trigger.
2. **External process kill** that happened to land on a 1000-batch
   boundary coincident with 10M.
3. **Truncated CorpusForge export on the laptop** where the manifest
   or chunks.jsonl file was short by ~435K before V2 even started.
4. **LanceDB fragment rollback** triggered by
   `optimize()`'s `cleanup_older_than=timedelta(seconds=0)` — theoretical,
   but would need to coincidentally land at exactly 10M.

None of these are code bugs that I can fix at the source from primary workstation.

## The durable fix

Added `LanceStore.verify_ingest_completeness()` (src/store/lance_store.py)
that runs a cheap `count_rows()` check after every ingest and asserts:

- `net_delta == expected_delta` — table row delta equals what
  `ingest_chunks` claimed to insert.
- `manifest.chunk_count == attempted` — when a CorpusForge manifest
  is supplied, its count matches what actually got handed to the
  store.
- `0 <= inserted <= attempted` — sanity check on the ingest-return
  value. A negative `inserted` means the caller handed back an
  invalid counter; `inserted > attempted` means the caller
  over-counted. Both surface as separate issue lines.

Note: `duplicates` is a derived field (`attempted - inserted`), not an
independently enforced invariant. Round 2 QA caught an earlier version
of this doc that overstated rule 3 as `inserted + duplicates ==
attempted`; that identity holds by construction of `duplicates` and
wouldn't catch a new bug class. The actual rule 3 is the bounds check
above.

Both the CLI (`scripts/import_embedengine.py`) and GUI
(`scripts/import_extract_gui.py`) import paths call this helper and
surface a loud `[WARN] INGEST INTEGRITY CHECK FAILED` if any rule fails.
The GUI also sets a `ingest_integrity` stat so the panel shows it.
Report is included in the import_report JSON as `ingest_integrity`.

Had this helper existed when the laptop was imported, it would have
printed the 435K gap at the moment of ingest instead of surfacing two
days later as "why is Tier 1 reporting 10,000,000 / 10,000,000".

## Follow-up I did NOT fix in this commit

- `LanceStore.optimize()` calls `cleanup_older_than=timedelta(seconds=0)`
  which destroys all prior LanceDB versions. That's a destructive
  default and the only remaining theoretical path to silent truncation
  after a botched write. Worth reviewing separately — not in scope
  for this commit, per strict-scope discipline.

Signed: reviewer | HybridRAG_V2 | 2026-04-11 MDT
