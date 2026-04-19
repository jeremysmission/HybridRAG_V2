# Metadata Migration Implementation — 2026-04-13

## Scope

This landing implements the smallest typed Forge->V2 metadata layer that improves retrieval without a schema redesign or re-embedding pass.

Landed in V2 only:
- typed source-metadata sidecar at `data/index/retrieval_metadata.sqlite3`
- import-time metadata upsert from `chunks.jsonl`
- `--metadata-only` backfill path in `scripts/import_embedengine.py`
- retriever consumption of typed fields for exact lookup families

Not landed in this pass:
- Forge-side typed field emission
- broad LanceDB schema mutation
- benchmark edits

## Fields Implemented

Derived now from `source_path` and consumed when present on chunk rows later:
- `cdrl_code`
- `incident_id` (`igsi` alias accepted on import)
- `po_number`
- `contract_number`
- `site_token`
- `site_full_name`
- `is_reference_did`
- `is_filed_deliverable`
- `source_ext`
- `shipment_mode` when path terminology makes it obvious
- `source_doc_hash` passthrough if Forge emits it later

## Migration / Backfill Path

No re-embedding is required.

Two supported paths:

1. Normal import:
   `.\.venv\Scripts\python.exe scripts\import_embedengine.py --source <export_dir>`

   This now ingests chunks into LanceDB and upserts one typed metadata row per unique `source_path`.

2. Metadata-only backfill:
   `.\.venv\Scripts\python.exe scripts\import_embedengine.py --source <export_dir> --metadata-only`

   This skips LanceDB row ingest and backfills only `retrieval_metadata.sqlite3`. Use this when the chunks are already in V2 and the goal is to populate typed metadata without touching vectors or re-running Forge embeddings.

## Retrieval Impact

Typed metadata is now used ahead of brittle path heuristics for:
- CDRL exact lookup
- IGSI/CAP lookup
- PO exact lookup
- DID/reference vs filed-deliverable separation
- contract-number-constrained deliverable lookup

Existing `source_path` heuristics remain as fallback for date-heavy and subtype-heavy queries, especially A027/date combinations where the MVP field set does not yet include a typed date column.

## What Was Backfilled

This change adds the backfill mechanism and tests it on synthetic exports.

This lane did **not** backfill the live workstation store. The live `C:\HybridRAG_V2\data\index\lancedb` remains unchanged until an operator runs one of the commands above against a canonical Forge export.

## What Still Needs Fresh Forge Export Later

Still better handled by future Forge emission rather than V2 path derivation:
- authoritative `source_doc_hash`
- any metadata not reliably encoded in `source_path`
- broader typed fields beyond the May 2 MVP

The V2 importer already accepts chunk-supplied typed fields when Forge starts emitting them; chunk values override path-derived fallback where present.

## Machine Probes

Direct probe of path derivation:
- DID path -> `A002`, `.pdf`, `is_reference_did=true`
- filed CAP path -> `A001`, `IGSI-1811`, `Fairford`, `is_filed_deliverable=true`
- logistics PO path -> `po_number=5000338041`

## Exact Commands Run

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe -m py_compile `
  C:\HybridRAG_V2\src\store\retrieval_metadata_store.py `
  C:\HybridRAG_V2\src\store\lance_store.py `
  C:\HybridRAG_V2\src\query\vector_retriever.py `
  C:\HybridRAG_V2\scripts\import_embedengine.py `
  C:\HybridRAG_V2\tests\test_candidate_pool_wiring.py `
  C:\HybridRAG_V2\tests\test_retrieval_metadata_store.py

C:\HybridRAG_V2\.venv\Scripts\python.exe -m pytest `
  C:\HybridRAG_V2\tests\test_candidate_pool_wiring.py `
  C:\HybridRAG_V2\tests\test_retrieval_metadata_store.py `
  C:\HybridRAG_V2\tests\test_import_validation.py `
  C:\HybridRAG_V2\tests\test_forge_v2_integration.py -q
```

Result:
- `51 passed in 1.65s`
