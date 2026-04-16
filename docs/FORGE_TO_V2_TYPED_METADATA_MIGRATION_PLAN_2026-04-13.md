# Forge -> V2 Typed Metadata Migration Plan — 2026-04-13

**Mode:** Read-only sidecar synthesis preserved for implementation handoff.

## Executive Summary

- Forge currently emits only `7` chunk fields.
- V2 ingests those directly and reconstructs most retrieval-critical metadata from brittle `source_path` regexes at query time.
- The smallest high-ROI Sprint 9 slice is:
  - `cdrl_code`
  - `po_number`
  - `site_token`
  - `shipment_date`
  - `is_filed_deliverable`
- These fields are metadata-only:
  - no re-embedding required
  - one fresh re-import is enough
  - vectors remain unchanged
- This is a buildable `3-5 day` slice if Forge and V2 move in parallel.
- The single biggest hidden risk is **silent drop at V2 ingest**:
  - Forge can emit the new fields correctly
  - V2 can still discard them if `lance_store.py` record construction is not extended first

## Minimal Sprint 9 Field Set

- `cdrl_code`
  - exact CDRL anchor
  - highest-value CDRL retrieval field
- `po_number`
  - exact procurement lookup anchor
- `site_token`
  - site-scoped narrowing for logistics and field queries
- `shipment_date`
  - date-scoped logistics narrowing
- `is_filed_deliverable`
  - separates real filed deliverables from reference/DID noise

## V2-Now vs Forge-Required

### V2 stopgap now

- V2 already contains path-regex logic for:
  - `cdrl_code`
  - `po_number`
  - site extraction
  - date extraction
- A short-lived stopgap can centralize those into one helper and use them more consistently.
- This is useful for a few days, but it remains fragile because it depends on path shape.

### Forge canonical source

- All 5 Sprint 9 fields should ultimately be emitted by Forge.
- Why Forge is the right authority:
  - it sees the original path once at parse/chunk time
  - the field is computed once, not re-guessed on every query
  - the field survives re-import and becomes filterable in Lance
  - `is_filed_deliverable` is cleaner when derived upstream from document context

### Later, after May 2

- `source_doc_hash`
- revision / release metadata
- cyber-family typed fields
- parser-native table structure
- OCR-confidence fields

## Exact File / Function Migration Map

### Forge

- `C:\CorpusForge\src\pipeline.py`
  - add metadata extraction before chunk export
- `C:\CorpusForge\src\export\packager.py`
  - likely no behavioral change if chunk dict is already enriched upstream
- `C:\CorpusForge\src\analysis\export_metadata_contract.py`
  - extend contract checks for the 5 Sprint 9 fields
- New helper module recommended:
  - `C:\CorpusForge\src\chunk\metadata_extractor.py`
  - one extractor that returns the 5 fields consistently

### V2

- `C:\HybridRAG_V2\src\store\lance_store.py`
  - extend explicit record dict in `ingest_chunks()`
  - this is the critical silent-drop point
- `C:\HybridRAG_V2\scripts\import_embedengine.py`
  - add defensive logging for chunk keys not recognized by ingest schema
- `C:\HybridRAG_V2\scripts\stage_forge_import.py`
  - confirm staging preserves the extra keys
- `C:\HybridRAG_V2\src\query\query_router.py`
  - propagate extracted typed values into query classification where needed
- `C:\HybridRAG_V2\src\query\vector_retriever.py`
  - add typed-field guardrail filters for:
    - CDRL
    - PO
    - site
    - shipment date
- `C:\HybridRAG_V2\src\query\reranker.py`
  - optional small match-boost later

## Re-embed / Re-import / Re-index

- Re-embed: **No**
- Re-import: **Yes**
- Re-index: **No explicit vector rebuild**

Reason:
- vectors are derived from `text` / `enriched_text`
- the new fields are additive metadata columns
- one fresh import of the new Forge export is the real data-side cost

## Validation Gates

### Layer 1 — Export contains the fields

- run Forge metadata-contract checks
- confirm the new fields exist in exported chunk rows
- confirm useful coverage, not just sparse presence

### Layer 2 — V2 ingests the fields

- import completes without schema mismatch
- import counts stay correct

### Layer 3 — Lance records expose the fields

- sample live rows from Lance
- confirm all 5 fields are present
- stop here if they are missing

### Layer 4 — Retrieval actually uses them

- spot-check representative CDRL / PO / site / date queries
- verify filters narrow in the intended direction

### Layer 5 — 400-pack lift

- rerun the frozen 400-pack
- compare to the `226 PASS` post-CDRL baseline
- require no regressions on the current demo-safe set

## Smallest Pre-May-2 Viable Migration

1. Extend V2 ingest/schema first.
2. Add a lightweight defensive key-check in import.
3. Add Forge extractor for the 5 fields.
4. Re-export once.
5. Re-import once.
6. Add typed-field guardrails in V2 retrieval.
7. Rerun the 400-pack and compare.

## Critical Sequencing Rule

- **V2 ingest/schema must land before the first Forge re-export that carries the new fields.**
- Otherwise the sprint can fail in the quietest possible way:
  - Forge emits correctly
  - V2 ingests without surfacing the new fields
  - query-layer debugging burns time even though the chain already broke at ingest

## Coordinator Read

- This is the buildable Sprint 9 metadata ticket.
- It is large enough to matter and still small enough to land before May 2.
- If the promotion run happens before this migration or before an explicit waiver, the run should be downgraded:
  - valid refresh
  - **not** a meaningful retrieval-architecture step
