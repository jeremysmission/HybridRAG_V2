# Lane 2 QA Report — Structured + Tabular Foundation

**Date:** 2026-04-13 MDT
**Tester:** Jeremy Randall (CoPilot+ QA)
**Repo:** `C:\HybridRAG_V2`
**Scope:** Lane 2 deliverable per user QA checklist
**Upstream artifact:** `docs/LANE2_STRUCTURED_TABULAR_FOUNDATION_EVIDENCE_2026-04-13.md`

---

## Environment

- Machine: primary workstation (NVIDIA workstation desktop GPUs FE 24GB, GPU 1 = fast lane)
- Python: `.venv\Scripts\python.exe` (repo-local venv)
- Config under test: `config\config.tier1_clean_2026-04-13.yaml`
- Live baseline store: `data\index\clean\tier1_clean_20260413\{entities,relationships}.sqlite3`
- Testing mode: probe-first, read-only. No code edits. Test suite re-run was cheap and non-CUDA; Tier 2 dry-run not re-executed to avoid colliding with any in-flight production eval on GPU 1.

Rationale for scope: the user's QA checklist is narrow (path agreement, count truth, audit backing, measurement honesty, no overclaim). Full 5-pillar `QA_EXPECTATIONS` is not applicable here because Lane 2 did not touch boot/config, the live query pipeline, or the operator GUI — only the structured-store path, the tiered-extract CLI, and the new tabular substrate module. Pillars 1, 2, and 5 were spot-checked via the paths that Lane 2 *did* modify.

---

## QA Checklist Results

### 1. Path agreement — health / boot / server / runtime / RelationshipStore

**Claim:** All owned runtime surfaces resolve the relationship DB via a single canonical helper.

**Verified:**

| Surface | File | Line(s) | Call site |
|---|---|---|---|
| Path resolver | `src/store/relationship_store.py` | 51–63, 78 | `resolve_relationship_db_path()` normalizes `entities.sqlite3` → sibling `relationships.sqlite3`; `RelationshipStore.__init__` also calls it on every construction as a enterprise-in-depth fallback for non-owned callers |
| Health check | `scripts/health_check.py` | 43, 78, 172–174 | imports `resolve_relationship_db_path`, calls it in `collect_stores()` and `collect_disk()` |
| Boot | `scripts/boot.py` | 17, 36, 49–50, 150 | `boot_system()` resolves and prints real `Rel DB` path |
| API server | `src/api/server.py` | 24, 50–51 | `create_app()` resolves via helper before instantiating `RelationshipStore` |
| Tiered extraction | `scripts/tiered_extract.py` | 67–69, 574, 1046 | `_resolve_runtime_store_paths()` resolves baseline, stages via copy if `--stage-dir` set |

**Result:** **PASS.** All owned surfaces agree. The enterprise-in-depth normalization in `RelationshipStore.__init__` means non-owned callers that still pass `entities.sqlite3` land on the right file — the evidence memo's admission of residual non-owned-caller risk is effectively neutralized by the constructor-level fallback. No misrouting possible.

---

### 2. Reported relationship count matches direct probe

**Claim:** health/boot/server all report `59 relationships`. Evidence memo cites `59`.

**Direct sqlite3 probe of canonical store:**

```
path:   C:\HybridRAG_V2\data\index\clean\tier1_clean_20260413\relationships.sqlite3
tables: ['relationships', 'sqlite_sequence']
SELECT COUNT(*) FROM relationships: 59
```

**Result:** **PASS.** Probe count (59) matches claimed count (59) exactly. No drift between what health_check renders and what the store actually holds.

---

### 3. Structured-store changes are audit-backed

**Claim:** Every structured-store movement has a JSON audit artifact. Lane 2 cites two.

**Verified artifacts on disk and numerically consistent:**

**`docs/lane2_table_pilot_audit_2026-04-13.json`**

```
config_path:                C:\HybridRAG_V2\config\config.tier1_clean_2026-04-13.yaml
tier:                       1
dry_run:                    true
table_mode:                 logistics
table_limit:                200
runtime_entity_path:        ...\tier1_clean_20260413\entities.sqlite3
runtime_relationship_path:  ...\tier1_clean_20260413\relationships.sqlite3
stage_dir:                  null  (dry-run path)
table_pilot.raw_row_count:  289   ← claimed 289
table_pilot.scanned_chunks: 200
table_pilot.matched_chunks: 196
table_pilot.family_row_counts: { "bom": 289 }
duration_seconds:           0.26
```

**`docs/lane2_tier2_audit_2026-04-13.json`**

```
tier:                       2
dry_run:                    true
table_mode:                 off
tier2.allowed_types:        [ORG, PERSON, SITE]  ← claim validated
tier2.scanned_chunks:       200
tier2.raw_entity_count:     471  ← claimed 471
tier2.new_entity_count:     0
tier2.type_counts:          { SITE: 124, ORG: 242, PERSON: 105 }  ← claim validated
tier2.duration_seconds:     17.68
```

**Result:** **PASS.** Both artifacts exist, both contain audit framing (config, paths, tier, mode, before-snapshot, after-snapshot, duration), and every cited number in the evidence memo reproduces inside the JSON exactly.

---

### 4. Tabular / logistics work is measured, not just planned

**Claim:** The substrate is no longer aspirational; deterministic row recovery runs on real logistics chunks.

**Verified:**

- `src/extraction/tabular_substrate.py` exists (424 lines). Contains:
  - `SPREADSHEET_EXTENSIONS`, `LOGISTICS_TABLE_SOURCE_HINTS` (6 families), `LOGISTICS_FAMILY_PRIORITY`
  - `detect_logistics_table_families()`, `pick_primary_logistics_family()`
  - `DeterministicTableExtractor` with five shape handlers: markdown tables, `[ROW n]` bracket tables, key-value records, calibration projection rows, inventory-header rows with trailing qty
- Wired into `src/extraction/entity_extractor.py` line 28: `from src.extraction.tabular_substrate import DeterministicTableExtractor`, with a module-level shared extractor `_TABLE_EXTRACTOR` (line 33). Not a planned import — it's actively constructed at module load.
- Wired into `scripts/tiered_extract.py` via `_stream_logistics_tables()` (lines 609–709), which iterates Lance batches with a SQL `WHERE source_path LIKE ...` pre-filter and invokes the extractor per chunk.
- CLI surface wired: `--table-mode {off,logistics}`, `--table-limit`, `--table-source-like` (repeatable), `--audit-json`, `--stage-dir`, `--allow-baseline-write` all registered in `main()` (lines 970–1005).
- Audit artifact proves the code path actually executed against the real clean store and produced 289 rows from 196 matched chunks.

**Result:** **PASS.** The substrate is real, wired, and measured.

**However — honest framing the evidence memo gets right but the one-paragraph summary could flatten:** all 289 rows in the table pilot were **BOM family from 2 source files**. Packing List, PR & PO, DD250, Calibration, Spares, and Received produced **0 rows** on this slice. This validates the BOM extraction path end-to-end on real corpus data; it does **not** yet validate packing-list, DD250, calibration, or spares-inventory shapes against real chunks. See "Notes" section below.

---

### 5. No overclaiming on aggregation

**Claim:** Full Tier 2 promotion is not done; broad aggregation claims are out of scope.

**Verified in evidence doc language:**
- "This was intentionally a dry run against the clean baseline."
- "In-place promotion is blocked unless a staged store is used or the operator explicitly overrides the guard."
- "This was a scoped dry run only. It is evidence that the promotion slice is measurable, not a claim that the clean store has been fully re-promoted."
- Final section titled "Remaining risks" enumerates: table pilot is a filtered dry run not a full-corpus promoted store; full Tier 2 on clean store is pending staged run + audit review; tiered_extract still runs Tier 1 before the optional table pass so full-corpus table audits need bounded `--limit` or staged overnight plan.

**Verified in code:**
- Clean-baseline write guard at `scripts/tiered_extract.py` lines 1011–1026 raises `SystemExit` when: `(tier>=2 OR table_mode!=off) AND not dry-run AND stage_dir is None AND baseline path matches canonical clean Tier 1 path AND not --allow-baseline-write`. This is a *code*-level commitment, not just a doc promise.
- `_looks_like_clean_tier1_baseline()` (lines 555–558) recognizes the canonical path by suffix match on the normalized POSIX-style string.
- Unit test `tests/test_tiered_extract.py::TestLogisticsTablePilot::test_clean_baseline_guard_recognizes_canonical_path` exists and passes.

**Result:** **PASS.** The no-overclaim discipline is enforced by the guard, not just by politeness.

---

## Test Suite Re-Run

**Command:**
```powershell
.venv\Scripts\python.exe -m pytest tests\test_extraction.py tests\test_tiered_extract.py -q
```

**Result:** `127 passed in 3.28s`

Lane 2 reported `127 passed in 1.90s`. Count matches exactly. Duration variance is normal (cache state, background processes).

Collect-only enumeration also confirmed 127 test IDs including:
- `TestLogisticsTablePilot::test_where_sql_filters_source_paths`
- `TestLogisticsTablePilot::test_stream_logistics_tables_inserts_rows`
- `TestLogisticsTablePilot::test_stage_dir_copies_baseline_stores`
- `TestLogisticsTablePilot::test_clean_baseline_guard_recognizes_canonical_path`
- `TestModuleImports::test_canonical_helpers_exported`
- `TestRunTier2Streaming::*` (GLiNER streaming path, bounded batches, limit respect, empty-store behavior)

Test surface covers all five changes Lane 2 claims coverage for: relationship path normalization, store rebinding, logistics family detection, deterministic extraction shapes, staged copy, and clean-baseline guard.

---

## Notes — Items Not Failing, Worth Tracking

These are not defects under the user-provided checklist, but I am flagging them so they do not get lost if Lane 2 work continues.

1. **Table pilot family diversity is narrow.** The 289-row result is 100% BOM family from 2 source files. The other five logistics families (packing list, received/PR&PO, DD250, calibration, spares) produced zero rows on the 200-chunk filtered slice. Before claiming the deterministic substrate *broadly* works on logistics, a larger slice (or per-family targeted slice via `--table-source-like`) should exercise at least packing-list and DD250 shapes against real corpus chunks. The current evidence proves the pipe is working and the BOM pattern is valid, not that all five shapes are validated.

2. **Tier 2 slice yielded 0 new inserts.** The 471 raw entities produced `new_entity_count: 0` after dedup against the baseline store. This is consistent with "scoped dry run, not a re-promotion" framing and the types narrowing to PERSON/ORG/SITE which were already partially populated. The slice validates the pipeline runs and the `allowed_types` gate works; it does not yet prove the promotion path would meaningfully improve coverage on the clean baseline. Worth a larger slice before treating Tier 2 re-promotion as evidence-backed.

3. **`--stage-dir` is silently dropped when `--dry-run` is set.** `scripts/tiered_extract.py` line 1013: `stage_dir = args.stage_dir if args.stage_dir and not args.dry_run else None`. Aligned with audit-only intent (you cannot materialize a staged copy during a dry run), but an operator who runs `--stage-dir staged_test --dry-run` expecting the stage dir to appear will be confused. A one-line warning print when the flag is dropped would close the usability gap without changing semantics.

4. **Table pilot `200 scanned chunks` semantics.** `--table-limit 200` caps chunks *after* the SQL `source_path LIKE` pre-filter, not raw corpus chunks. The audit shows 200 scanned / 200 candidate / 196 matched, which is correct but could read as "we looked at 200 corpus chunks." Worth clarifying in the evidence memo or the audit JSON schema that `scanned_chunks` is post-filter.

5. **Non-owned callers of `RelationshipStore(cfg.paths.entity_db)`** (acknowledged in memo). Safe in practice because the constructor normalizes, but there is no lint/grep gate preventing new code from taking the old pattern. A trivial `grep -rn 'RelationshipStore(.*entity_db)' src scripts | not matching resolve_` check in CI would make this a permanent guard.

None of these block the QA checklist. They are follow-on cleanup candidates.

---

## Issues Found

None blocking.

---

## Verdict

- [x] **PASS** — all five items in the user's QA checklist verified. Path agreement is consistent and enterprise-in-depth. Reported count matches direct probe exactly (59 = 59). Audit artifacts exist and reproduce every cited number. Tabular substrate is wired, executed, and measured on real corpus data. Aggregation claims are scope-disciplined and the discipline is enforced at the code level by the clean-baseline write guard, not just by documentation.

- [ ] CONDITIONAL
- [ ] FAIL

**Lane 2 is cleared for the next slice.** The natural next move is a broader table-pilot slice exercising packing-list / DD250 / spares shapes against real chunks, so the substrate gets family-diverse evidence before any staged promotion.

Signed: Jeremy Randall | HybridRAG_V2 | 2026-04-13 MDT
