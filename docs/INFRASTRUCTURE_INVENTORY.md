# HybridRAG V2 — Infrastructure Inventory

**Purpose:** what exists in this codebase, organized by capability. Read this BEFORE dispatching anyone to build something — high chance it's already here.

**Last updated:** 2026-04-20

---

## Why this doc exists

On 2026-04-20 the team nearly rebuilt three things that already existed (`tabular_substrate.py`, `entity_store.TableRow`, the eval GUI panels). This inventory is the durable fix. Future maintainers: scan here first.

When you add new capability, append to the relevant section here in the SAME PR. If you delete capability, mark it removed.

---

## 1. Substrate Stores (`src/store/`)

| Store | File | What it holds | Key API |
|-------|------|---------------|---------|
| Entity / TableRow | `src/store/entity_store.py` | Generic entities + table rows of any kind. Has `Entity`, `TableRow`, `EntityResult`, `TableResult` classes. | `insert_entities`, `insert_table_rows`, `lookup_entities`, `query_tables`, `aggregate_entity`, `count_entities`, `count_table_rows`, `entity_type_summary` |
| Failure events | `src/store/failure_events_store.py` | Specialized substrate for failure events (system, site, part, year, source attribution). UNIQUE on (source_path, chunk_id, part_number). | `top_n_parts`, `top_n_parts_per_year`, `evidence_for_part` |
| PO pricing | `src/store/po_pricing_store.py` | Deterministic procurement / price substrate for replacement-cost and vendor-spend queries. | `top_vendors_by_spend`, `replacement_cost`, `po_line_lookup` |
| Installed base | `src/store/installed_base_store.py` | Deterministic denominator substrate for installed parts, site history, and rate-normalized methods. Current landed populate: `40,599` rows. | `insert_rows`, `site_history`, `vendor_aggregation`, `installed_count` |
| MSR | `src/store/msr_substrate.py` | Maintenance site visit / ASV / RTS substrate for visit-completion rollups. | `insert_asv_rows`, `insert_rts_rows`, `completions_per_site_per_year` |
| Relationship | `src/store/relationship_store.py` | Entity-entity relationships for graph-style retrieval | (see file) |
| Retrieval metadata | `src/store/retrieval_metadata_store.py` | Metadata for retrieved chunks | (see file) |
| Vector | `src/store/vector_store.py` | Vector embeddings (abstract layer) | (see file) |
| LanceDB | `src/store/lance_store.py` | LanceDB-backed vector store implementation | (see file) |

**Architectural note:** V2 root has unified entity_store with generic TableRow. Lane clones built standalone substrate files (po_pricing.sqlite3, installed_base.sqlite3) for clean ownership during sprint. Post-demo: consider consolidating into entity_store.TableRow with `table_kind` column.

---

## 2. Extractors (`src/extraction/`)

| Extractor | File | What it extracts | Notes |
|-----------|------|------------------|-------|
| Entity | `src/extraction/entity_extractor.py` | Generic entity extraction from chunks | |
| Failure events | `src/extraction/failure_event_extractor.py` | Failure events with system/site/year/part attribution. Path-derived + chunk-derived passes. | `_SYSTEM_PATTERNS`, `_PART_FALSE_POSITIVE_PREFIXES` |
| **Tabular substrate** | `src/extraction/tabular_substrate.py` (660 lines) | **Logistics-first table extraction. 7 family detectors, 6 row-extractor methods.** | **CHECK BEFORE BUILDING ANY NEW TABULAR PARSER.** See section below. |
| Quality gate | `src/extraction/quality_gate.py` | Quality gating logic (likely tier-related) | |

**Lane-specific add-ons (do NOT exist in V2 root):**
- `po_event_extractor.py` — V2_Dev, Lane 2
- `installed_base_xlsx_parser.py` — V2_Dev2, Lane 3 (in flight)

### `tabular_substrate.py` — what's in it (CRITICAL — check before adding tabular extraction)

**Family detectors:**
```python
LOGISTICS_TABLE_SOURCE_HINTS: dict[str, tuple[str, ...]] = {
    "packing_list": ("packing list", "packing slip"),
    "bom": ("bom", "bill of material", "bill of materials"),
    "received_po": ("pr & po", "pr&po", "space report", "received", "procurement", "rcvd"),
    "dd250": ("dd250", "dd 250"),
    "calibration": ("calibration",),
    "spares_report": ("spare", "inventory"),
}
LOGISTICS_FAMILY_PRIORITY: tuple[str, ...] = (
    "packing_list", "bom", "received_po", "dd250", "calibration",
    "spares_report", "spreadsheet",
)
```

Functions: `detect_logistics_table_families(source_path, text)` → set of family hints; `pick_primary_logistics_family(families)` → single family per priority.

**`DeterministicTableExtractor` class — extraction methods:**
- `_extract_pipe_joined_kv_rows`
- `_extract_markdown_tables`
- `_extract_bracket_row_tables`
- `_extract_key_value_tables`
- `_extract_calibration_projection_table`
- `_extract_inventory_rows` ← **likely covers Site Inventory Reports**

Storage target: `entity_store.TableRow` via `insert_table_rows`.

**Before building a new extractor:**
1. Could `_extract_inventory_rows` or another method already do this?
2. Could you ADD a new family to `LOGISTICS_TABLE_SOURCE_HINTS` and reuse the existing extractors?
3. If you really need new logic, add a new method to `DeterministicTableExtractor` rather than a parallel parser.

---

## 3. Aggregation Executor (`src/query/`)

`src/query/aggregation_executor.py` — deterministic Structure-Augmented Generation (SAG) executor.

**Capabilities:**
- `detect_aggregation_intent(query)` → intent or None
- `parse_top_n(query)`, `parse_year_range(query)` → query parameters
- `try_execute(query)` → `AggregationResult` with tier, context_text, sql
- Fail-closed alias gate (returns None when canonical config missing)
- Unresolved-reference RED guard (Antarctica/GOTHAM hallucination prevention)
- `_PO_LOGISTICS_TRIGGERS` + `_PO_LOGISTICS_AXIS` regex for fail-closed PO guard

**Cross-substrate executor surface now live in root:**
- failure top-N / failure counts
- vendor aggregation
- site history
- failure-rate helpers backed by installed base
- MSR ASV / RTS site-year rollups
- inventory / replacement-cost query families via pricing + installed-base inputs

**`AliasTables` class:**
- Loads from `config/canonical_aliases.yaml`
- `has_systems_configured()`, `_detect_unresolved_system_reference()`, `_detect_unresolved_site_reference()`

**Pipeline integration:** `src/query/pipeline.py` calls aggregation_executor BEFORE the regular RAG router; if aggregation returns non-RED, that's the answer.

---

## 4. Vocabulary Infrastructure (`src/vocab/` + `config/vocab_packs/`)

### Loader
`src/vocab/pack_loader.py` — loads + queries vocab packs. Use for column-header resolution, entity recognition, alias lookup.

### Vocab packs available
| Pack | File | Lines | Coverage |
|------|------|-------|----------|
| Government forms | `config/vocab_packs/government_forms.yaml` | 207 | DD Forms 1149, 250, 1348, etc. with canonical, aliases, form_number, common_fields |
| Program management terms | `config/vocab_packs/program_management_terms.yaml` | 353 | Program management + industry acronyms (GFE, COTS, GOTS, MPLM, FEP, etc.) |
| Domain vocab | `config/domain_vocab.yaml` | 286 | General domain terminology |
| Site vocabulary | `config/site_vocabulary.yaml` | (check) | Site-related terms |
| Extraction schema v1 | `config/extraction_schema_v1.yaml` | (check) | Extraction schema reference |
| Canonical aliases | `config/canonical_aliases.yaml` | (check) | Systems (NEXION, ISTO) + 22 sites with canonical + aliases |

### Vocab CLI tools
- `scripts/vocab_validation_lookup_cli_2026-04-15.py` — validate vocab pack lookups
- `scripts/vocab_deterministic_tagging_cli_2026-04-15.py` — deterministic tagging using packs
- `scripts/vocab_pack_report_2026-04-15.py` — pack reporting

**Before hardcoding column synonyms or entity names:** call `pack_loader` against the appropriate pack. This is the portability principle.

---

## 5. GUI Panels (`src/gui/`)

### Main app panels (`src/gui/panels/`)
| Panel | File | Purpose |
|-------|------|---------|
| Query | `query_panel.py` | Main query interface |
| Entity | `entity_panel.py` | Entity browser |
| History | `history_panel.py` | Query history |
| Settings | `settings_panel.py` | Settings + model selector |
| Regression | `regression_panel.py` | Regression test harness |
| Status bar | `status_bar.py` | Status bar |
| Nav bar | `nav_bar.py` | Navigation |
| Panel registry | `panel_registry.py` | Panel registration |

### Eval panels (`src/gui/eval_panels/`)
| Panel | File | Purpose |
|-------|------|---------|
| Aggregation | `aggregation_panel.py` (343 lines) | Aggregation query GUI |
| Count | `count_panel.py` (391 lines) | Count query GUI |
| Compare | `compare_panel.py` (630 lines) | A/B comparison GUI |
| RAGAS | `ragas_panel.py` | RAGAS evaluation GUI |
| History | `history_panel.py` | Eval history |
| Launch | `launch_panel.py` | Eval launcher |
| Overview | `overview_panel.py` | Eval overview |
| Results | `results_panel.py` | Results viewer |
| Runner | `runner.py` | Generic runner |
| Benchmark runners | `benchmark_runners.py` | Generic benchmark runner module |

**Before building new GUI surfaces:** check the panel folder. The aggregation/count/compare panels are likely the demo-day UI — polish, don't rebuild.

---

## 6. Scripts (`scripts/`)

### Populate scripts
| Script | Substrate | Notes |
|--------|-----------|-------|
| `populate_failure_events.py` | failure_events | Path-derived + chunk-derived passes |
| `populate_po_pricing.py` | po_pricing | V2_Dev only |
| `populate_installed_base.py` | installed_base | V2_Dev2 only |

### Benchmark / eval runners
| Script | What it runs |
|--------|--------------|
| `run_aggregation_benchmark_2026_04_15.py` | Aggregation benchmark (older variant) |
| `run_failure_aggregation_benchmark.py` | Failure aggregation truth pack |
| `run_tabular_eval.py` (204 lines) | Tabular evaluation |
| `run_ragas_eval.py` | RAGAS metrics on 400-query pack |
| `run_production_eval.py` | Production eval |
| `run_golden_eval.py` | Golden set eval |
| `run_full_import_and_extract.py` | Full pipeline runner |
| `run_tier1_clean_launcher.py` | Tier 1 clean rerun launcher |
| `run_tier1_shadow_slice.py` | Tier 1 shadow slice |

### Diagnostic / lifecycle
| Script | Purpose |
|--------|---------|
| `boot.py` | Pipeline assembly + sanity printout |
| `reconcile_raw_vs_substrate.py` | Reconcile raw corpus vs substrate counts |
| `sanitize_before_push.py` | Remote-push sanitization gate |

**Before building a new benchmark/eval runner:** model on `run_failure_aggregation_benchmark.py` and `run_tabular_eval.py`. Same shape, swap truth pack and substrate.

---

## 7. Tools (`tools/`)

| Tool | Purpose |
|------|---------|
| `tools/qa/gui_button_smash_harness.py` | 4-tier GUI smash harness (A=scripted, B=smart monkey, C=dumb monkey, D=human checklist) |
| `tools/qa/_v2_panel_helpers.py` | Tab helpers for ttk.Notebook |
| `tools/gui_evidence_capture.py` | GUI evidence capture |
| `tools/gui_e2e/run.py` | GUI E2E click-all |
| `tools/gui_import_extract_evidence_capture.py` | Import/extract evidence capture |

---

## 8. Truth packs (`tests/aggregation_benchmark/`)

| File | Items | Coverage |
|------|-------|----------|
| `failure_truth_pack_2026-04-18.json` | 50 | Failure aggregation queries (Q1/Q2/Q3 + variants) |
| `po_pricing_truth_pack_2026-04-19.json` | 25 | PO queries (Q-DEMO-A/B/C/E/F variants) — Agent-B v1 |
| `po_pricing_truth_pack_v2_2026-04-19.json` | 40 | Agent-B's expanded v2 |
| `inventory_truth_pack_2026-04-19.json` | 25 | Q-DEMO-D inventory queries — Agent-D |
| `failure_truth_pack_2026-04-19.json` (in flight) | target 100 | Miner self-review of FAIL-AGG-51..100 candidates |

**Before building a new truth pack:** check if you can extend an existing one with new items (continue the FAIL-AGG-N IDs).

---

## 9. Mining outputs / family maps (`docs/`)

| File | What it documents |
|------|-------------------|
| `docs/installed_base_family_map_2026-04-19.json` + `.md` | Miner's installed_base family scan (recommended regex set) |
| `docs/po_pricing_family_scan_2026-04-19.json` | Agent-B's PO family scan (430K files, 19,719 hits) |
| `docs/po_pricing_date_coverage_2026-04-19.json` + `.md` | Miner's date-gap diagnosis (extractor_missing_pattern, 2024 monthly PR & PO files) |
| `docs/xlsx_validation_site_inventory_2026-04-19.json` | Miner's Site Inventory template scan (2 templates, universal PART NUMBER + QPA/QTY) |
| `docs/xlsx_validation_as_built_2026-04-19.json` | Miner's As-Built template scan (3 groups, 1 matters) |
| `docs/installed_base_denominator_scouting_2026-04-19.md` | Lane 3 architecture scouting |
| `po_lifecycle_source_scouting_2026-04-19.md` (top-level) | Lane 2 PO source-family scouting |
| `docs/aggregation_evidence_contract.md` | GREEN/YELLOW/RED tier doctrine |
| `docs/capability_roadmap_2026-04-20.md` | Five-pillar forward roadmap after the merged push |
| `docs/competitive_benchmark_2026-04-20.md` | External-analysis synthesis of the near-term quality/perception gaps |

**Before mining a new family:** check if the family was already mapped. Build on the existing map.

---

## 10. Corpus paths

`E:\CorpusTransfr\` (USB, READ-ONLY) — raw 700GB corpus, atomic-copied via CorpusForge for full metadata preservation.

Known landmarks:
- `E:\CorpusTransfr\verified\IGS\5.0 Logistics\` — entire logistics section, bounded universe
  - `IPT Slides - Site Inventories\<site>\` — per-site inventory xlsx (10 sites visible: Curacao, Eglin, Fairford, Kwaj, Learmonth, Misawa, Niger, Okinawa, Vandenberg, Wake)
  - `Procurement\` — `001 - Open Purchases\`, `002 - Received\`, `011 - Subcontracts PRs\`, `iBuy GL List.xlsx`
  - `Shipments\<year>\` — year-organized 2022-2026 (the 2023-2025 date data Agent-B's extractor needs)
  - `NEXION BOM\` — Installation Master Lists per site, plus 2025-dated estimates
  - `GFE - Warehouse Property Book\`, `Audits\`, `Calibration\`, `Disposition\`, `EEMS\`, `HAZMAT\`, etc.
- `E:\CorpusTransfr\verified\IGS\` parent has 25+ sections (1.0 IGS DM, 1.5 IGS CDRLS, 2.0, 2.5, 3.0, etc.) — explore for MSR / failure / engineering data
- Per-site folders at IGS root: `! Site Visits\`, `# NEXION Sites\`, `# ISTO Sites\` — likely hold MSRs + failure records

`E:\CorpusIndexEmbeddingsOnly\` (USB, READ-ONLY) — deduped chunks index (LanceDB). Use for distinct-content counting + semantic retrieval. Lossy — can miss specific items vs raw corpus.

`E:\` is READ-ONLY. Writes go to `C:\` only. `D:\` (USB, 1.4 TB free) available for heavy mining staging.

---

## 11. Cross-references — "if you need X, look at Y"

| Need | Look at |
|------|---------|
| Build a new tabular extractor | `src/extraction/tabular_substrate.py` first |
| Store generic table rows | `entity_store.TableRow` + `insert_table_rows` |
| Detect logistics doc type | `tabular_substrate.detect_logistics_table_families` |
| Recognize column headers (PART NUMBER variants) | `pack_loader` against `domain_vocab.yaml` |
| Recognize DD Forms / CDRL / industry acronyms | `pack_loader` against `government_forms.yaml` + `program_management_terms.yaml` |
| Add a new aggregation query type | `src/query/aggregation_executor.py` — extend `try_execute` + intent detection |
| Build a new benchmark | model on `scripts/run_failure_aggregation_benchmark.py` |
| Add a GUI surface | check `src/gui/eval_panels/` and `src/gui/panels/` first |
| Capture GUI evidence | `tools/gui_evidence_capture.py`, `tools/qa/gui_button_smash_harness.py` |
| Mine corpus for a new family | check `docs/*_family_map_*.json` and Miner's outputs first |
| Add canonical alias for system/site | edit `config/canonical_aliases.yaml` (data-driven, no code change) |
| Add industry term | add to appropriate `config/vocab_packs/<pack>.yaml` |
| Validate substrate vs corpus | `scripts/reconcile_raw_vs_substrate.py` |
| Run all tests | `.venv\Scripts\python.exe -m pytest tests/ -q` |

---

## 12. Delivery patterns worth reusing

| Pattern | What it is | File path / anchor | When to reuse | Origin |
|---------|------------|--------------------|---------------|--------|
| SAG deterministic substrate | Exact counts and rankings come from a structured substrate; the LLM presents, it does not compute. | `src/query/aggregation_executor.py`, `docs/aggregation_evidence_contract.md` | Any query that counts, ranks, groups, or compares | Failure aggregation sprint slice |
| CRAG fail-closed-to-AMBIGUOUS / RED | Unresolved filters or hostile input must downgrade instead of widening silently. | `src/query/aggregation_executor.py` unresolved-filter guards | Any deterministic executor with canonical filter inputs | Aggregation QA hardening |
| 5-gate BANKED promotion | Capability is not banked until truth pack, wiring, adversarial, provenance, and QA gates all pass. | `docs/qa/SPRINT_SLICE_AGGREGATION_QA_REPORT_2026-04-19.md` and the promotion flow in the main war room | Any future substrate or executor landing | Aggregation delivery process |
| Multi-agent triangulation | Cross-model review plus live runtime verification beats single-lane certainty. | `docs/lessons_learned_2026-04-20.md` | Push gates, regression diagnosis, risky promotions | 2026-04-20 merged push |

---

## 13. What does NOT exist yet (real gaps)

- Comparative / time-windowed aggregation executor family beyond the current landed top-N and cross-sub slices
- Program-level portfolio / health rollup executor and benchmark pack
- Shipment / in-transit visibility substrate
- Deterministic maintenance x logistics join executor (`failure_events` + `po_pricing` + `installed_base` + `msr_substrate`)
- Schema discovery tool for new corpora (post-demo capability)
- Forward-resilience test suite parity across all substrates (better in some lanes than others, not yet uniform)
- Embedding-based column-header fuzzy matcher (currently config-only via vocab packs; embedding similarity is post-demo upgrade)
- Sanitizer staging-mode workflow encoded in code rather than operator memory

---

## Maintenance protocol

When you ship NEW capability that other agents might want to leverage:
1. Add a row to the relevant section of this doc IN THE SAME PR
2. If you remove capability, mark as removed
3. Don't let this doc go stale — it's the anti-duplication safeguard

Maintainers should run a quick scan against this doc before drafting any "build new X" dispatch. If X is here, redirect to "extend Y" instead.
