# Sprint Slice — Failure-Rate Aggregation Capability (2026-04-18)

**Owner:** Jeremy Randall (HybridRAG_V2)
**Co-pilot:** CoPilot+
**Repo:** HybridRAG_V2, CorpusForge
**Target demo date:** 2026-05-02
**Sprint parent:** Sprint 3 (Logistics / Failure Substrate Unlocks) + Sprint D (Aggregation / Counting Capability)
**Depends on:** banked 85.75% retrieval baseline, populated `source_metadata` (93,636 rows), entity store with 366,844 relationships

---

## Purpose

Turn grouped/ranked/top-N failure-analysis questions into a demo-safe deliverable.
Example questions the system must answer **exactly**, not narratively:

1. "What were the highest failing part numbers in the NEXION system in 2024?"
2. "What were the highest failing part numbers in the ISTO system in Djibouti from 2022-2025?"
3. "What are the top 5 failure-rate parts ranked each year for the past 7 years?"

These are NOT retrieval questions. They are **grouped aggregation + ranking** questions over an entire corpus-wide population of failure events. Free-form RAG answers them by counting the top-K retrieved chunks, which is structurally wrong and has been audited as a dead pattern in `STATE_SNAPSHOT_2026-04-18.txt`.

---

## Core Architectural Principle

> **Exact counts must come from a deterministic structured substrate. The LLM explains and presents; it never invents the count.**

This mirrors the `aggregation_evidence_contract` commitment already in the backlog and the research consensus (2026 literature — see Sources at end). It is the same pattern that Oracle Inventory, IBM reliability tooling, and enterprise text-to-SQL systems use: structured substrate + SQL aggregation + LLM narration.

### Three evidence tiers (contractual)

| Tier | Meaning | Answer behavior |
|------|---------|-----------------|
| **GREEN** | Deterministic exact count from structured substrate with full numerator + denominator evidence | Return exact number + ranked list + evidence rows |
| **YELLOW** | Bounded-evidence count (numerator populated; denominator partial or absent) | Return floor/ceiling ranges and explicit caveat; no rate unless flagged `rate_unsupported=true` |
| **RED** | Substrate insufficient (missing part_number, year, system, or site keys) | Abstain. Return "insufficient deterministic evidence" + list the missing substrate fields |

---

## What the 3 Target Questions Require

### Question 1 — "Highest failing part numbers in NEXION system in 2024"
| Field | Needed | Source of truth |
|-------|--------|----------------|
| `failure_event` (row-level) | YES | Maintenance / CAP / IGSI / field-failure reports |
| `part_number` | YES | Same row as failure_event, or linkable by failure_id |
| `system` (NEXION canonical) | YES | System alias table (NEXION, Nexion, NXN, etc.) |
| `event_date → year` | YES | Temporal canonicalization (`FY24`, `CY2024`, `2024`, `04/2024` → 2024) |
| GROUP BY + ORDER BY + LIMIT | YES | SQL adapter |

**Answerable as GREEN** once substrate is populated.

### Question 2 — "Highest failing part numbers in ISTO system in Djibouti from 2022-2025"
Adds:
- `site` canonical (Djibouti aliases: DJI, Djibouti AB, Camp Lemonnier, DJB)
- Date-range filter (inclusive 2022 ≤ year ≤ 2025)

**Answerable as GREEN** once substrate is populated + site alias table exists.

### Question 3 — "Top 5 failure-rate parts ranked each year for the past 7 years"
Adds (much harder):
- `numerator` = failure count per part/year (have this if Q1/Q2 work)
- `denominator` = installed-base count per part/year — **this is the gap**
- Per-year ranking (window function / 7 separate queries)

**Answerable as YELLOW** (ranked failure-count list, no true rate) until installed-base denominator source is mapped. **GREEN** only after denominator work lands.

---

## Architecture — What Gets Built

```
User Query: "Top failing parts in NEXION 2024"
    |
    v
[Query Router] ── detects AGGREGATION intent via pattern:
    - "top N", "highest", "rank", "most", "count of", "how many"
    - + GROUP-BY noun ("parts", "failures", "sites", "years")
    |
    v
[Aggregation Parser] ── extracts:
    - metric:      failures | rates | count
    - group_by:    part_number
    - filter:      system=NEXION, year=2024
    - limit:       N (default 5, bounded 1-50)
    - rank_order:  DESC on metric
    |
    v
[Canonical Resolver] ── normalizes filters:
    - NEXION → "NEXION" (canonical)
    - 2024 → integer year
    - Djibouti → "DJI" canonical site
    |
    v
[SQL Adapter] ── runs deterministic query against failure_events table:
    SELECT part_number, COUNT(*) AS failure_count
    FROM failure_events
    WHERE system = 'NEXION' AND event_year = 2024
    GROUP BY part_number
    ORDER BY failure_count DESC
    LIMIT 5
    |
    v
[Evidence Linker] ── for each ranked row, attach 1-3 source chunk_ids
    |
    v
[LLM Presenter] ── GPT-4o / phi4 explains the ranked result using
    the deterministic numbers as input. NEVER computes the count.
    |
    v
[GUI Output] ── shows:
    - GREEN/YELLOW/RED confidence tier badge
    - Ranked table (deterministic)
    - Evidence panel (source rows)
    - "Exact count via deterministic backend" label
```

### New modules / tables required

| Module | Location | Responsibility |
|--------|----------|---------------|
| `failure_events` SQLite table | `data/substrate/failure_events.db` | Row per extracted failure event |
| `installed_base` SQLite table | `data/substrate/installed_base.db` | Row per deployed unit (denominator) |
| `canonical_aliases.yaml` | `config/canonical_aliases.yaml` | System / site / part_number aliases |
| `src/extraction/failure_event_extractor.py` | new | Regex + template + GLiNER hybrid |
| `src/query/aggregation_router.py` | new | Detects AGGREGATION intent + extracts params |
| `src/query/sql_adapter.py` | new | Parameterized SQL over failure/install substrate |
| `src/query/evidence_linker.py` | new | Maps aggregation rows back to source chunks |

All modules are parameterized. No new free-form LLM counting anywhere.

---

## Phased Slice Plan

### SLICE 1 — Truth Pack + Source Family Discovery (2-3 days)
**Owner:** Claude-R3 (already designated per `AGGREGATION_ACTION_ITEMS_2026-04-18.txt`)
**Dependency:** none — can start now

- [ ] Build `failure_analysis_truth_pack_nexion_isto_2026-04-19.json`
  - 20+ audited questions (Q1, Q2, Q3 style) with exact ground truth
  - Each entry labeled GREEN / YELLOW / RED
  - Each entry cites exact source rows
- [ ] Ship `nexion_isto_failure_event_source_map.md`
  - Exact files/folders/templates that carry failure rows
  - Schema fingerprint (column headers, row layout) for each family
- [ ] Identify the 3-5 highest-yield source families for failure events

**Acceptance:** Truth pack audited by second researcher. Source map validates against at least 2 sample files per family.

---

### SLICE 2 — Canonical Alias Tables (1-2 days)
**Owner:** Claude-R3 + first free coder
**Dependency:** Slice 1 source map

- [ ] System aliases: NEXION, ISTO, and any other systems appearing in failure rows
- [ ] Site aliases: Djibouti + top 20 sites from `source_metadata` (`29,659 site tokens`)
- [ ] Year canonicalizer: `FY24`, `CY2024`, `2024`, `04/2024`, `Q1-2024` → `2024`
- [ ] Part-number canonicalizer: collapse whitespace/dash variants (`TC 16-06-23-003` = `TC16-06-23-003` — per CorpusForge marathon finding)
- [ ] Ship as `config/canonical_aliases.yaml`
- [ ] Unit tests: 50 alias cases pass

**Acceptance:** 95%+ alias coverage on truth-pack filter terms. No collisions (no two canonical entries share aliases).

---

### SLICE 3 — Failure-Event Extractor Pilot (3-5 days)
**Owner:** Coder B or first free coder (per backlog AGGREGATION P1)
**Dependency:** Slices 1 + 2

- [ ] Regex-first extractor for 1 source family (highest yield from Slice 1)
- [ ] Emit rows to `data/substrate/failure_events.db` with columns:
  - `chunk_id`, `source_path`, `part_number`, `system`, `site`, `event_date`, `event_year`, `failure_type` (optional), `confidence`, `extraction_method`
- [ ] Path-derived field fallback (when row doesn't carry site/system but folder does)
- [ ] Idempotent — re-running does not duplicate rows
- [ ] QA against truth pack: extractor precision ≥ 0.90, recall ≥ 0.70 on pilot family

**Acceptance:** 1 family extracted, ≥1,000 failure rows populated, precision/recall gated.

---

### SLICE 4 — SQL Adapter + Aggregation Router (2-3 days)
**Owner:** Coder B (claimed: deterministic backend for exact counts)
**Dependency:** Slice 3 substrate

- [ ] `src/query/aggregation_router.py` — detects AGGREGATION intent (pattern matcher; no free-form LLM classification yet, can add later)
- [ ] `src/query/sql_adapter.py` — parameterized query templates:
  - `top_n_by_group`: GROUP BY + ORDER BY + LIMIT
  - `count_by_filter`: WHERE + COUNT(*)
  - `count_by_group_per_year`: window-like ranked output
- [ ] Parameter binding ONLY (no SQL string interpolation — prevents injection)
- [ ] Returns: deterministic result + substrate-coverage metadata (`rows_scanned`, `rows_matched`, `distinct_values`)
- [ ] `UNSUPPORTED` return path when filter keys unresolvable

**Acceptance:** Q1 ("top failing parts in NEXION 2024") returns exact ranked list from Slice 3 substrate. Q2 likewise. Q3 returns YELLOW (failure counts, no rates).

---

### SLICE 5 — Evidence Linker + GUI Surface (2 days)
**Owner:** Coder A (after current product P0s — per backlog)
**Dependency:** Slice 4

- [ ] `src/query/evidence_linker.py` — maps each aggregated row to 1-3 source chunks
- [ ] GUI:
  - Confidence tier badge (GREEN/YELLOW/RED)
  - Ranked result table (part_number, count, evidence chunk link)
  - "Deterministic backend count" framing label
  - Expandable evidence panel with source chunks
- [ ] LLM call path: builds explanatory narrative from the deterministic rows — never re-derives count
- [ ] Stub-safe behavior: if SQL returns empty, GUI shows "No failure events matched these filters" with substrate-coverage stats

**Acceptance:** Jeremy asks Q1 in GUI → deterministic ranked list displays with GREEN tier + evidence. Same for Q2.

---

### SLICE 6 — Installed-Base Denominator (3-5 days, post-demo acceptable)
**Owner:** Claude-R3 (per backlog AGGREGATION P1 rate denominator)
**Dependency:** Slice 1 source-family knowledge

- [ ] Identify installed-base sources (deployment manifests, site population records)
- [ ] `data/substrate/installed_base.db` populated with `(part_number, site, year, qty_deployed)` rows
- [ ] SQL adapter gains `failure_rate_by_group` template: `failures / installed_base`
- [ ] Q3 is upgradable from YELLOW → GREEN once denominator coverage passes a threshold

**Acceptance:** Q3 returns GREEN for the years/parts where denominator exists; YELLOW elsewhere with explicit "installed-base coverage: X%" disclosure.

---

### SLICE 7 — Multi-Family Extractor Expansion (1-2 weeks, post-demo)
**Owner:** Coder B / Claude-R3 rotation
**Dependency:** Slices 3 + 4 proven

- [ ] Extend extractor to families 2-5 from Slice 1 source map
- [ ] Backfill `failure_events.db` from all identified families
- [ ] Re-run truth pack; expand from 20 → 50+ questions
- [ ] Add family-coverage metric to GUI (`failure events from N of M known families`)

**Acceptance:** ≥80% truth-pack GREEN pass rate across expanded question set.

---

## Acceptance — End-to-End Demo Criteria

A failure-aggregation question is demo-ready when:

1. Router detects AGGREGATION intent
2. Canonical resolver normalizes all filter terms (system, site, year, part)
3. SQL adapter returns exact result with `rows_matched > 0`
4. Evidence linker attaches ≥1 source chunk per ranked row
5. GUI displays GREEN tier badge + ranked table + evidence panel
6. LLM narrative contains ONLY the deterministic numbers (gated by evidence-attribution check)
7. Same question, same corpus state, returns the same answer **100% of the time** (determinism test)

---

## Explicit Anti-Patterns (do NOT do)

Per `STATE_SNAPSHOT_2026-04-18.txt` and `AGGREGATION_ACTION_ITEMS_2026-04-18.txt`:

- Do NOT inject aggregated-metadata rows into the vector candidate pool (regressed, reverted)
- Do NOT subtractively narrow retrieval by metadata (regressed, reverted)
- Do NOT let LLM count chunks in top-K and call it a corpus-wide total
- Do NOT claim rate without denominator source audit
- Do NOT collapse table/row counting into chunk/entity counting (per `COUNTING_AND_AGGREGATION_WEB_FINDINGS_2026-04-15.md`)
- Do NOT use free-form first-number scraping as a benchmark signal
- Do NOT reopen temporal full-400 lane as part of this slice

---

## Demo-Safe Query Pack (GREEN only at demo time)

Before 2026-05-02 demo, deliver `aggregation_demo_pack.md` containing:

- 5-10 GREEN questions (exact counts, exact rankings, proven substrate)
- Each question rehearsed on both V2 (GPU 0) and V2_Dev (GPU 1) lanes with identical results
- Fallback narration for each: "This system deterministically counts failure events from X source families covering Y% of the corpus"

If Q3 denominator slice does not land in time, demote to: "Top 5 failing parts ranked each year for the past 7 years" (counts, not rates). This is still a visually strong demo.

---

## Success Metric

By 2026-04-25 (7 days):
- Slices 1-4 complete
- Q1 + Q2 return GREEN in GUI with evidence
- Truth pack shows ≥85% GREEN pass rate on Q1/Q2-style questions

By 2026-05-02 (demo):
- Slice 5 GUI surface complete
- ≥8 GREEN demo questions rehearsed
- Q3 returns YELLOW with clear disclosure (GREEN if Slice 6 lands)
- Determinism test passes (same q / same state / same answer, 10 runs)

---

## Integration Points With Existing System

| Existing module | Change |
|----------------|--------|
| `src/query/query_router.py` | Add AGGREGATION branch that hands off to new `aggregation_router.py` before standard vector/entity path |
| `src/query/crag_verifier.py` | Skip verifier for AGGREGATION (per backlog research note — CRAG verifier gap). Aggregation has its own substrate-based verification |
| `src/query/context_builder.py` | When result is deterministic-aggregation, context is the ranked table + evidence chunks — no fusion/rerank needed |
| `src/store/retrieval_metadata_store.py` | No change (source_metadata remains retrieval-facing, not aggregation substrate) |
| Eval harness | Add `aggregation_backend_accuracy.md` track (exact-count pass/fail, off-by-one, unsupported rate) |

---

## Sources (2026 research alignment)

- [Aggregation Queries over Unstructured Text: Benchmark and Agentic Method](https://arxiv.org/html/2602.01355v1) — confirms LLM top-K counting is structurally wrong for corpus-wide aggregates
- [Structure Augmented Generation: Bridging Structured and Unstructured Data for Enhanced RAG Systems](https://www.meibel.ai/post/structure-augmented-generation-bridging-structured-and-unstructured-data-for-enhanced-rag-systems) — the SAG pattern this slice adopts
- [Building Cost-Efficient Agentic RAG on Long-Text Documents in SQL Tables](https://towardsdatascience.com/building-cost-efficient-agentic-rag-on-long-text-documents-in-sql-tables/) — SQL-substrate + LLM narration pattern
- [CSR-RAG: An Efficient Retrieval System for Text-to-SQL on the Enterprise Scale](https://www.arxiv.org/pdf/2601.06564) — 2026 enterprise text-to-SQL retrieval
- [TableRAG: A Retrieval Augmented Generation Framework for Heterogeneous Document Reasoning](https://arxiv.org/html/2506.10380v1) — keep table/row counting distinct
- [Leveraging Failure Modes and Effect Analysis for Technical Language Processing](https://www.mdpi.com/2504-4990/7/2/42) — FMEA-guided NER for failure extraction
- [Natural Language Processing of Maintenance Records Data](https://www.diva-portal.org/smash/get/diva2:975548/FULLTEXT01.pdf) — maintenance record extraction patterns
- Prior local research: `COUNTING_AND_AGGREGATION_WEB_FINDINGS_2026-04-15.md` (mmRAG, MEBench, Counting-Stars, Infini-gram mini)

---

## Backlog Alignment

This slice satisfies / unblocks the following backlog items from `BacklogWork_2026_17_4.txt`:

- AGGREGATION P0: deterministic failure-analysis truth pack (NEXION/ISTO) — **Slice 1**
- AGGREGATION P0: smallest deterministic substrate for NEXION failures — **Slices 1-3**
- AGGREGATION P1: narrow deterministic backend pilot — **Slices 3-4**
- AGGREGATION P1: denominator sources for true failure rates — **Slice 6**
- AGGREGATION P1: QA gate for failure-analysis pilot — **QA gates Slices 3-5**
- AGGREGATION P1: deterministic backend path for exact counts — **Slice 4 (already claimed by Coder B)**
- AGGREGATION P1: UI/API framing for count answers — **Slice 5 (designated for Coder A)**

No new work is outside backlog scope. This slice **sequences** the already-designated tasks into a deliverable.

---

Jeremy Randall | CoPilot+ | HybridRAG_V2 | 2026-04-18 MDT
