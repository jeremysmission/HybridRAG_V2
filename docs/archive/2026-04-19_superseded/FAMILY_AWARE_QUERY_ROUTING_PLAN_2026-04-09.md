# Family-Aware Query Routing Plan 2026-04-09

Purpose: define a V2 routing plan that is grounded in the current query/import/store code and in the measured Forge-side family evidence, without baking in source-specific assumptions.

This is a docs/analysis artifact. No runtime changes are proposed here.

## Evidence Basis

The Forge-side evidence packet shows a stable pattern:

- raw file presence is dominated by images and archives
- retrieval weight is dominated by a much smaller set of table-heavy operational records
- drawings and image assets matter, but mostly as metadata-bearing or low-text objects
- archive-derived descendants and low-quality parse families can distort retrieval if they are allowed to compete as ordinary semantic chunks

Measured counts behind that statement:

- clean export parsed docs: `17,134`
- clean export chunks: `242,650`
- chunk leaders:
  - `.xlsx = 189,862`
  - `.jpg = 14,623`
  - `.pdf = 14,324`
  - `.txt = 11,201`
- family leaders:
  - operational support / travel-admin records: `549` docs, `177,181` chunks
  - inventory / manifest records: `54` docs, `17,922` chunks
  - image / photo assets: `13,442` docs, `13,494` chunks
  - drawing / diagram assets: `690` docs, `784` chunks
  - archive-derived bundles: `159` docs, `2,338` chunks

Routing implication:

- query-type alone is not enough
- V2 needs a second axis that says which document families to prefer, suppress, or cap

## Current V2 Grounding

### Import boundary

Current import behavior is still family-blind.

Code anchors:

- `scripts/import_embedengine.py`
  - required chunk fields are only `chunk_id`, `text`, and `source_path`
  - import validation does not require or preserve `document_family`
  - skip-manifest data is printed for operators, but family metadata is not pushed into the vector store

### Vector store boundary

Code anchor:

- `src/store/lance_store.py`
  - persisted chunk fields are `chunk_id`, `text`, `enriched_text`, `vector`, `source_path`, `chunk_index`, and `parse_quality`
  - the module docstring still mentions `doc_type`, but the actual insert path does not populate it

Result:

- vector retrieval can score text and parse quality
- it cannot filter or rerank on document family because that metadata is not present

### Structured store boundary

Code anchors:

- `src/store/entity_store.py`
  - entity rows keep `entity_type`, `text`, `raw_text`, `confidence`, `chunk_id`, `source_path`, and `context`
  - table rows keep `source_path`, `table_id`, `row_index`, `headers`, `values_json`, and `chunk_id`
- `src/store/relationship_store.py`
  - relationship rows keep subject/object/predicate fields, `confidence`, `source_path`, `chunk_id`, and `context`

Result:

- V2 has structured stores
- V2 does not preserve family, bundle, drawing, or table-shape metadata strongly enough to do family-aware routing cleanly

### Query routing boundary

Code anchors:

- `src/query/query_router.py`
  - emits `query_type`, `expanded_query`, `sub_queries`, and `entity_filters`
  - does not emit `query_family`, `preferred_families`, `blocked_families`, or `structured_first`
- `src/query/pipeline.py`
  - dispatches by `query_type` only
  - semantic path is vector-first
  - structured path always also runs vector search and merges the results
  - complex path decomposes by sub-query type, not by document family

Result:

- V2 can choose between semantic, entity, aggregate, tabular, and complex paths
- V2 cannot yet say "this is an operational-table question" or "this is a drawing-identity lookup"

### Operator surface boundary

Code anchors:

- `src/api/models.py`
  - response exposes `query_path` and `sources`
- `src/gui/panels/query_panel.py`
  - GUI shows the query path badge and sources list
  - it does not show routing family, family filters, or suppression/cap decisions

Result:

- even if family-aware routing existed internally, operators could not inspect it yet

## Recommended Routing Model

Keep the existing top-level `query_type` values as they are.

Add a second routing layer:

- `query_type` decides the store shape
- `query_family` decides which document families to prefer, suppress, or combine

Minimal additional router outputs:

- `query_family`
- `preferred_families`
- `blocked_families`
- `structured_first`
- `family_routing_reason`

That is enough to improve retrieval behavior without replacing the current architecture.

## Where Family-Aware Routing Helps Most

### 1. Table-heavy operational lookups

Best family targets:

- operational support / travel-admin records
- inventory / manifest records

Why this is the clearest win:

- `603` documents in those families account for `195,103` chunks
- they are naturally answered as rows, not prose windows

Recommended behavior:

- treat row-level structured retrieval as the primary path
- use exact identifiers, statuses, destinations, requestors, dates, and similar fields as first-class ranking signals
- only add vector context when the answer needs explanation around the record

### 2. Narrative reference questions

Best family targets:

- manuals
- procedures
- reference notes
- mixed PDF/DOC/DOCX/TXT narrative material

Recommended behavior:

- keep semantic retrieval plus reranking as the primary path
- suppress operational tables unless the query explicitly asks for a record, identifier, status, count, or list
- boost heading continuity and parse quality

### 3. Drawing and asset identity lookups

Best family targets:

- drawings
- diagrams
- CAD-adjacent assets

Recommended behavior:

- route explicit drawing, layout, schematic, title-block, revision, or asset-ID questions to metadata-first lookup
- return the asset card first: identifier, title, revision, sheet/page, source
- allow limited text fallback only when the asset has meaningful text density or the query explicitly asks for prose from the drawing package

### 4. Image-heavy families

Best family targets:

- photos
- scans
- image-only attachments

Measured reason:

- `13,442` image-family docs produced only `13,494` chunks

Recommended behavior:

- keep image families queryable
- do not let them dominate broad semantic searches by default
- only favor them for explicit image/scan/photo intent, or when linked to a primary asset/document result

### 5. Archive-derived bundles

Best family targets:

- extracted archive descendants
- archive-labeled duplicate bundles

Recommended behavior:

- do not delete them silently
- apply per-document and per-bundle caps
- suppress them from default broad retrieval when a primary non-archive source exists

This is an audit-first lane, not an auto-skip lane.

### 6. Low-quality OCR and weak-parse families

Best family targets:

- scanned PDFs
- low-confidence OCR
- repetitive telemetry/BIT-style XML or similar weak-text technical outputs

Recommended behavior:

- keep them available
- down-rank them when clean table or narrative evidence exists
- surface lower trust when answers rely on them

## Metadata V2 Needs From Forge

These fields are the minimum useful surface:

| Metadata | Why it matters |
|---|---|
| `document_family` | primary routing/filter key |
| `family_confidence` | prevents weak labels from dominating retrieval |
| `source_extension` | cheap and highly predictive routing clue |
| `source_doc_id` or stable file hash | per-document caps, dedup, provenance |
| `table_heavy` | separates row-oriented material from prose |
| `table_id`, `row_index`, `header_tokens`, `sheet_name` | preserves row fidelity |
| `section_path` or `heading_path` | improves narrative grouping and ranking |
| `page_number` or `sheet_name` | useful for citations and asset lookup |
| `archive_derived` plus `bundle_signature` | supports flood control on archive descendants |
| `image_or_metadata_only` | suppresses low-text assets in general search |
| `is_drawing_like`, `drawing_id`, `title_block_tokens` | enables metadata-first drawing lookup |
| `parse_quality`, `is_ocr`, `ocr_confidence` | quality-aware ranking and fallback |
| `identifier_tokens` | exact match boost for operational lookup |

## Safe Implementation Order

1. Preserve family metadata during import.
   - extend `scripts/import_embedengine.py`
   - extend `src/store/lance_store.py`
2. Preserve family metadata in structured stores.
   - extend `src/store/entity_store.py`
   - extend `src/store/relationship_store.py`
3. Extend router output.
   - add `query_family`, family preferences, and `structured_first` in `src/query/query_router.py`
4. Make retrieval consume the new metadata.
   - apply family filters/boosts in `src/query/pipeline.py`
   - keep structured and semantic paths, but make their merge policy family-aware
5. Surface the decision to operators.
   - extend `src/api/models.py`
   - extend `src/gui/panels/query_panel.py`

## QA Focus Once Implementation Starts

The first proof set should cover:

1. exact row lookup from a table-heavy operational record
2. aggregate query over operational records
3. narrative troubleshooting/procedure lookup
4. mixed query needing both a record answer and a narrative explanation
5. drawing or asset-ID lookup
6. archive-derived flood-control proof
7. low-quality OCR result staying below a clean primary source

## Limits

This plan is grounded in current code and measured family evidence, but it still has limits:

- it assumes Forge can emit stable family metadata without exposing corpus-specific logic to V2
- it does not prove that all XML failures belong to one safe defer family
- it does not justify removing archive-derived or image-heavy material from the corpus

## Handoff Status 2026-04-09

- this lane stayed in docs/analysis scope
- no V2 runtime code was changed in this pass
- the repo already contains unrelated dirty work, but this lane itself is isolated to new docs only
- the next safe coding slice is a minimal metadata-preservation change from Forge export into V2 import and Lance storage

Signed: reviewer | Lane 4
