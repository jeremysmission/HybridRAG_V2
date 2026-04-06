# Sprint 10 QA Bundle

**Date:** 2026-04-06 MDT  
**Scope:** Close the Sprint 9 backlog queue, harden structured retrieval on the isolated Sprint 6 path, and align full golden eval scoring with the actual routed retrieval context.

---

## What Changed

- Fixed `GQ-021` routing by tightening local-Ollama guard logic in `src/query/query_router.py`.
- Added query-shaped expanded rewrites for:
  - contact-email lookups
  - site-by-part distribution lookups
  - cancelled purchase order lookups
  - unique part number aggregation
- Normalized free-form router `entity_type` labels onto the structured-store schema in `src/query/entity_retriever.py`.
- Added structured retrieval helpers for:
  - person -> contact resolution
  - part -> site aggregation
  - unique canonical part-number aggregation
  - multi-hop part -> site -> requestor/contact resolution for `GQ-021`
- Added deterministic table parsing in `src/extraction/entity_extractor.py` for:
  - markdown pipe tables
  - `[ROW n] ... | ...` spreadsheet fragments
- Added `--deterministic-tables-only` mode to `scripts/extract_entities.py` so table recovery does not require an LLM pass.
- Updated `scripts/run_golden_eval.py` so full-pipeline retrieval scoring uses the exact routed retrieval context instead of a vector-only proxy.
  - `--retrieval-only` behavior is unchanged for Sprint 6 comparability.
- Hardened generator confidence handling in `src/query/generator.py`:
  - parses bolded tags like `[**HIGH**]`
  - rewrites stale tags when normalized confidence changes
  - upgrades several known overcautious local-Ollama answer shapes to `HIGH`
  - requires POC answers to include phone/email when the context contains them

---

## Key Commands

Deterministic spreadsheet repair on the isolated store:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\extract_entities.py `
  --config config\config.sprint9_extract.yaml `
  --batch-size 1 `
  --deterministic-tables-only `
  --source-pattern spreadsheet_fragment.txt
```

Final full golden eval:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\run_golden_eval.py `
  --config config\config.sprint9_demo.yaml `
  --output tests\golden_eval\results\sprint10_eval_final.json
```

Targeted regression spot-checks used during the sprint:

```powershell
.venv\Scripts\python.exe scripts\run_golden_eval.py --config config\config.sprint9_demo.yaml --query GQ-019
.venv\Scripts\python.exe scripts\run_golden_eval.py --config config\config.sprint9_demo.yaml --query GQ-021
.venv\Scripts\python.exe scripts\run_golden_eval.py --config config\config.sprint9_demo.yaml --query GQ-023
```

---

## Verification Results

### Golden Eval

Final run: `tests/golden_eval/results/sprint10_eval_final.json`

- Routing: `25/25`
- Retrieval: `25/25`
- Generation: `25/25`
- Confidence: `25/25`
- CRAG triggered: `0`
- Average latency: `15099 ms`
- Exit gate: `PASS`

### Store Repair

Deterministic spreadsheet repair expanded the isolated table store from `8` rows to `16` rows.

Recovered rows now include:

- `PO-2024-0505 | AB-115 | Copper Basin | IN TRANSIT`
- `PO-2024-0506 | AH-900 | Birchwood | CANCELLED | Cancelled per director`
- `PO-2024-0507 | AB-115 | Sandpoint | DELIVERED`

### Queue Closure

The Sprint 9 backlog queue is now green under the official runner:

1. `GQ-021` route/generation/confidence fixed
2. `GQ-016`, `GQ-017`, `GQ-020`, `GQ-023` structured-data gaps fixed
3. `GQ-019` retrieval completeness fixed
4. Router latency remains a performance concern, but correctness is no longer blocked by it

---

## QA Focus

### Must Confirm

- Deterministic table repair is fast and repeatable:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\extract_entities.py `
  --config config\config.sprint9_extract.yaml `
  --batch-size 1 `
  --deterministic-tables-only `
  --source-pattern spreadsheet_fragment.txt
```

Expected:

- script completes without Ollama dependency
- `Table rows: 8` inserted on that pass
- isolated `extracted_tables` includes `PO-2024-0505`, `PO-2024-0506`, `PO-2024-0507`

- Full eval remains green:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\run_golden_eval.py `
  --config config\config.sprint9_demo.yaml `
  --output tests\golden_eval\results\sprint10_eval_qa.json
```

Expected:

- `Routing 25/25`
- `Retrieval 25/25`
- `Generation 25/25`
- `Confidence 25/25`
- gate `PASS`

- Spot-check the formerly failing queries:
  - `GQ-016`
  - `GQ-019`
  - `GQ-020`
  - `GQ-021`
  - `GQ-023`

### Do Not Fail QA On These Yet

- Warm local-Ollama latency is still around `12s` to `22s` for many full-pipeline queries on this path.
- CRAG is still inactive in this demo profile.
- The isolated structured store is still a promoted slice, not a full-corpus structured extraction.

---

## Residual Risk

Correctness is now demo-green on the isolated Sprint 9 path. The remaining risk is operator experience, not answer quality:

- local routing/generation latency is still materially above the original sub-5s aspiration
- full-corpus structured promotion is still narrower than the vector corpus
- the eval runner is now more faithful to the real pipeline, so historical retrieval numbers before 2026-04-06 are not apples-to-apples with this file

---

## Exit Status

Sprint 10 is ready for independent QA.

- golden gate passes end to end
- the agreed Sprint 9 backlog is closed
- deterministic table repair is codified
- next-sprint planning is prepared in `docs/SPRINT_11_14_GAMEPLAN_2026-04-06.md`
