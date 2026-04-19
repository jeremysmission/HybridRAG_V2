# Sprint Slice: Aggregation Capability (Failure Events -> Top-N SQL)

**Owner:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-18 MDT
**Demo target:** 2026-05-02 (14 days)
**Lane:** B (Entity Enrichment) -- spans Sprints 2-3 of `SPRINT_PLAN_NEXT_5_2026-04-16.md`

---

## Goal

Answer analytical top-N questions against the legacy corpus with cited evidence:

- "What were the highest failing part numbers in the monitoring systems in 2024?"
- "What were the highest failing part #s in the legacy monitoring systems in Djibouti from 2022-2025?"
- "What are the top 5 failure rate parts ranked each year for the past 7 years?"

These are group-by-count-rank queries. Pure vector RAG cannot answer them reliably --
you cannot retrieve an aggregate. AGGREGATE PASS on the 400-pack is currently **56%**
(worst query type, per R3 routing confusion matrix analysis). This slice is the biggest
remaining product-truth lever.

## Why 14 days is feasible (this is NOT greenfield)

Most of the scaffolding already exists:

| Existing surface | What it gives us |
|------------------|------------------|
| `scripts/v1_reference/service_event_extractor.py:58-86` | V1 `service_events` schema: report_date_iso, report_year, site_canonical, part_number, failure_mode, action_type, installed_part_number, removed_part_number, chunk_id |
| `src/extraction/entity_extractor.py:1097-1360` | Event block parser already emits FAILED_AT / REPLACED_AT / INSTALLED_AT relationships |
| `config/extraction_schema_v1.yaml:29-57` | FAILED_AT / REPLACED_AT / CONSUMED_AT predicates already declared |
| `config/domain_vocab.yaml` (R3 backfill) | 158 acronyms, 21 sites, 57 CDRL codes, 5 programs |
| `src/store/retrieval_metadata_store.py` (93,636 rows) | source_metadata with site_token, cdrl_code, document_category, contract_number |
| `src/store/entity_store.py:318-365` | `aggregate_entity()` GROUP BY scaffold |
| R3 CDRL heat map | A027 = 96.7% of CDRL chunks (3.4M/3.5M) -- the natural focus slice |

What is actually missing: the `failure_events` table, the `system` dimension,
a multi-dim SQL aggregation API (system + site + year_range + top_k), router wire-up,
canonical part-number normalization, and a gold aggregation eval pack.

## Architecture

```
User query
    |
    v
[Query Router -- GPT-4o] classifies AGGREGATE + detects "failing/top/highest/most/worst"
    |                                     sub-intent: failure_rank
    v
[Text-to-parameterized-SQL path (NEW)] -- NOT free-form SQL generation
    |   extracts filters: system, site, year_range, top_k
    v
aggregate_failures(system?, site?, year_range?, top_k=10)
    |
    v
[SQLite failure_events table (NEW)] indexed on (system, year) and (site_canonical, year)
    |
    v
ranked rows with sample chunk_ids
    |
    v
[Generator -- GPT-4o] formats numbered list + [HIGH]/[PARTIAL] citations
    |
    v
Honest abstention if 0 rows: "Structured failure data for <filter> not present in extracted records"
```

Design choice: **parameterized API, not free-form text-to-SQL.** LlamaIndex
NLSQLTableQueryEngine style is tempting but opens hallucinated-column and
injection risks. A narrow, typed API gives us deterministic behavior and
honest abstention for 14 days to demo. (Simpler is better.)

---

## Slices

### Slice 0: Gold aggregation eval pack -- P0 -- Day 1

**File:** `tests/golden_eval/golden_aggregation_top_n_2026-04-18.json`
**Owner:** R3
**Target:** 30 top-N questions across three tiers.

- Tier 1 (easy, 10 q): single system, single year, parts already in domain_vocab
- Tier 2 (stress, 12 q): multi-year ranges, cross-site grouping, 5+ systems
- Tier 3 (negative, 8 q): out-of-scope systems, years with no data, abstention
  cases ("top parts for system ZEBRA in 1999")

Gold answers are **ranked lists** (top 5 or 10) with exact part numbers + counts.
Mined from the 3.4M CDRL A027 chunks plus the logistics family tables already
at 9,133 rows.

Acceptance: manifest loads, tier distribution matches, each gold answer has
at least one source chunk_id cited.

### Slice 1: `failure_events` table schema -- P0 -- Day 2

**New file:** `src/store/failure_events_store.py`

```sql
CREATE TABLE failure_events (
    id INTEGER PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    part_number TEXT NOT NULL,
    part_number_canonical TEXT,
    system TEXT,
    system_canonical TEXT,
    site TEXT,
    site_canonical TEXT,
    report_date_iso TEXT,          -- YYYY-MM-DD
    report_year INTEGER,
    failure_mode TEXT,
    action_type TEXT,              -- failed | replaced | repaired | removed
    confidence REAL,               -- 0.0-1.0
    extraction_method TEXT,        -- tier1_regex | tier2_block | tier3_llm
    created_at TEXT
);
CREATE INDEX idx_fe_system_year ON failure_events(system_canonical, report_year);
CREATE INDEX idx_fe_site_year ON failure_events(site_canonical, report_year);
CREATE INDEX idx_fe_part ON failure_events(part_number_canonical);
```

Migration does not touch `entities` or `extracted_tables`. Additive only.

### Slice 2: Finish the extractor (wire event parser to new table) -- P0 -- Days 3-5

Extend `src/extraction/entity_extractor.py:1097-1360` to emit failure_event
rows alongside the existing FAILED_AT / REPLACED_AT relationship emission.

Add the `system` dimension via three signals, in order:

1. **Path-derived** (strongest per R3's 100% path-taxonomy-loss finding):
   folder-name match against `domain_vocab.programs` (currently 5 entries --
   expand to cover named systems in the demo questions).
2. **CDRL -> system map** (new section in `domain_vocab.yaml`): many CDRLs
   belong to a specific program. Derive from path + existing CDRL heat map.
3. **In-chunk acronym match**: fall back to acronym dictionary (158 entries).

Focus pass 1 on CDRL A027 chunks (3.4M, 96.7% of all CDRL). Skip the rest
until recall is measured on the gold pack.

Acceptance: **greater than or equal to 50K failure_event rows** from the A027 slice, with
per-row `system` populated at >= 80% and `site_canonical` >= 95% (R3 already
showed acronym expansion is necessary but not sufficient alone -- this is why
path + CDRL map come first).

### Slice 3: Canonical normalization -- P0 -- Days 3-5 (parallel with Slice 2)

Seed a canonical parts list from the top-1000 most-frequent part-number
patterns in the corpus (one-shot mining job over the existing chunk store).

At write time, use `rapidfuzz` (already in waiver set) to map raw -> canonical
at threshold 0.9. Log misses to `failure_events_unnormalized.jsonl` for later
review.

Sites via `domain_vocab.sites` aliases (21 entries). Systems via the expanded
`domain_vocab.programs` + CDRL map from Slice 2.

Acceptance: >= 95% of inserted rows have non-null canonical part, site, and
system. Un-normalized log has < 5% of total rows.

### Slice 4: Aggregate SQL API -- P0 -- Day 6

Add to `failure_events_store.py`:

```python
def aggregate_failures(
    system: Optional[str] = None,
    site: Optional[str] = None,
    year_range: Optional[Tuple[int, int]] = None,
    group_by: List[str] = ("part_number_canonical",),
    top_k: int = 10,
) -> List[FailureRankRow]:
    ...
```

Each returned row:
```
{
    "part_number": "ARC-4471",
    "count": 47,
    "systems": ["monitoring system"],
    "sites": ["Djibouti", "Thule"],
    "years": [2022, 2023, 2024, 2025],
    "sample_chunk_ids": ["...", "...", "..."],  # top 3 for citation
}
```

Tests in `tests/test_failure_events_aggregate.py` covering the three demo
questions verbatim plus negative cases.

Acceptance: SQL returns correctly ranked results on hand-crafted fixtures.
p50 latency under 500ms for the three demo queries against the extracted data.

### Slice 5: Router + generator wire-up -- P0 -- Days 7-8

- `src/query/query_router.py`: add `failure_rank` sub-intent under AGGREGATE.
  Keywords: failing, failure, highest, top, most, worst, rank, ranked.
  Router extracts filters (system / site / year_range) into a typed struct.
- `src/query/entity_retriever.py:109-124`: route `failure_rank` to
  `failure_events_store.aggregate_failures(...)` instead of vector + reranker.
- `src/query/generator.py`: new prompt template for structured-ranked answers.
  Template format:
  > Top N parts by failure count for <filter>:
  > 1. PART-1234 -- 47 failures (2022-2024, sites: Djibouti, Thule) [HIGH]
  > 2. PART-5678 -- 31 failures ...
  > Sources: chunk_1, chunk_2, chunk_3 ...

Fallback: if SQL returns 0 rows, emit honest abstention rather than falling
back to vector RAG (which will confabulate a ranking). Message:
"No structured failure records match <filter>. Closest semantic evidence: ..."
(Sample 3 chunks from the existing hybrid retriever for context.)

### Slice 6: A/B test against 400-pack + new top-N pack -- P0 -- Day 9

| Metric | Pre-change | Target |
|--------|-----------|--------|
| 400-pack AGGREGATE PASS | 56% | >= 75% |
| New top-N gold pack PASS | n/a | >= 70% |
| 400-pack overall retrieval PASS | 85.75% | no regression (stay >= 85%) |
| p50 latency on SQL path | n/a | < 3s end-to-end |

Run on both V2 (GPU 0) and V2_Dev (GPU 1) lanes for cross-validation,
per existing A/B discipline.

### Slice 7: Demo rehearsal for the 3 example queries -- P0 -- Day 10

Run each demo question end-to-end. Screenshot the full answer + citations.
Verify every citation links back to a real chunk_id with real date + site
metadata. Add to `docs/DEMO_SCRIPT_2026-05-02.md`.

Acceptance: all 3 queries return sane ranked lists with clickable chunk
evidence. Honest abstention verified for a 4th adversarial query
("top failing parts for <system that doesn't exist>").

### Slice 8 (P1, optional): Materialized rollup views -- Days 11-12

Precompute `(system_canonical, report_year, part_number_canonical, count)`
into a small SQLite materialized view. Adds value **only** if Slice 4 p50
exceeds 1s. Skip if already sub-second.

### Slice 9 (P1, optional): Tier 3 stronger-model extraction pass -- Days 13-14

For chunks that pass the Tier 1 classifier but fail strict regex, send to
the existing free overnight stronger-model lane (per memory: Max-plan
hardtail lane is zero marginal cost). Only trigger if Slice 2 extraction
recall on the gold pack is below 70%.

---

## Acceptance (must all pass before demo)

1. Three demo queries return correctly ranked lists with working citations.
2. 400-pack AGGREGATE PASS >= 75% (up from 56%).
3. New aggregation gold pack PASS >= 70%.
4. No regression: 400-pack overall retrieval PASS stays >= 85%.
5. p50 latency on SQL path < 3s end-to-end.
6. Honest abstention verified on Tier 3 negative cases (no confabulated rankings).

## The real tradeoff

**Extraction recall is the ceiling.** If the extractor misses 30% of failure
events, the rankings undercount. But: rankings remain *directionally correct*
for the common parts that dominate the tail (which is what a demo audience
asks about), and we get *honest abstention* instead of vector-RAG
confabulation on the long tail. Recall is lifted post-demo by Slice 9.

The alternative -- free-form text-to-SQL generation -- has a higher theoretical
ceiling (BIRD benchmark ~80% on clean schemas) but drops to 58-64% under
enterprise realism with messy schemas (Promethium 2025). For 14 days with
noisy OCR, the narrow parameterized API is the safer bet.

## Out of scope (intentional)

- Real-time rollup recalculation on ingest (batch-only for demo)
- Cross-document relationship chains (separate aggregation gauntlet work)
- is_answerable label backfill (MEGA-14, blocked separately)
- Free-form text-to-SQL with arbitrary generated columns (simpler is better)

## Dependencies and coordination

- **Coder A:** do NOT touch the scorer or reranker. 85.75% baseline is stable.
- **Coder B:** owns Slices 1-7. Temporal-canonicalization A/B can run in
  parallel (shares path-derived date work but different table).
- **R3:** Slice 0 gold pack, Slice 6 A/B audit, metadata-backfill diagnostic
  in parallel.
- **QA:** Slice 6 A/B after Day 9, Slice 7 demo rehearsal witness.
- **Hardware:** V2 on GPU 0, V2_Dev on GPU 1 for cross-validation. Workstation
  hardware only -- no primary workstation dependency.

## References (research-first per memory)

- TAG (Stanford/Berkeley, arxiv 2408.14717, CIDR 2025): conceptual anchor for
  semantic + structured query routing. Hand-written TAG hit 55% on TAG-Bench
  vs < 20% for Text2SQL-only and vanilla RAG.
- LlamaIndex SQLAutoVectorQueryEngine (Jerry Liu, 2023): the canonical hybrid
  SQL + vector pattern we are mirroring.
- BIRD leaderboard (Apr 2026): CoPilot+ 3.5 Sonnet 78.2%, GPT-4o 81.95% dev --
  but Promethium enterprise reports 58-64% under dirty-schema conditions.
- LazyGraphRAG (Microsoft, Nov 2024): considered and rejected for this slice --
  summary-based, does not do numeric top-N well.
- V1 `scripts/v1_reference/service_event_extractor.py:58-86`: the in-repo schema template.
- R3 finding: 100% metadata loss during chunking -> path derivation is the
  right lever for `system` dimension.

## Sprint plan mapping

- Slices 0-2 land in **Sprint 2** (retrieval gap, 75% target).
- Slices 3-7 land in **Sprint 3** (entity at scale, 80% target).
- Slices 8-9 land in **Sprint 4** if needed (demo hardening).

---

Jeremy Randall | HybridRAG_V2 | 2026-04-18 MDT
