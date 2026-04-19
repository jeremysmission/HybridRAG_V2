# Aggregation Evidence Contract

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-18 MDT
**Backlog item:** AGGREGATION P0 — Define and document the aggregation split
**Applies to:** every aggregation-shaped query (top-N, count, rate, rank, list-all)

---

## Purpose

Before an aggregation answer leaves the system, it must be classified into one of **three contract tiers**. The tier determines what the answer is allowed to assert, what evidence it must carry, and what the UI displays.

This contract is the counterweight to the 2026 literature consensus: `Aggregation Queries over Unstructured Text` ([arXiv 2602.01355](https://arxiv.org/html/2602.01355v1)) showed free-form LLM counting over top-K retrieved chunks is structurally wrong for corpus-wide aggregates. The contract prevents that failure mode from ever reaching a user.

---

## The three tiers

### GREEN — Exact Deterministic Count

**Definition.** A parameterized SQL query against a structured substrate returns the exact count/ranking. The LLM narrates the numbers; it never computes them.

**Required conditions (ALL must hold):**
1. The query's filter axes (system, site, year, part_number, etc.) all resolve to canonical values via `config/canonical_aliases.yaml` or in-code canonicalizers.
2. Every filter axis has substrate coverage ≥ 80% for the requested slice.
3. The substrate used is a deterministic table (`failure_events`, `source_metadata`, `extracted_tables`) — never a vector-retrieved chunk set.
4. No rate/ratio is being computed unless BOTH numerator and denominator substrates exist.
5. The answer includes ≥ 1 source-path evidence row per top result.

**UI badge:** `GREEN — deterministic backend count`

**Allowed assertions:**
- "The top 5 failing parts in NEXION in 2024 were: 1. `EC11612` (4 failures), 2. …"
- "`ARC-4471` has 23 failure events recorded across the corpus."
- "12 deliverables were filed under CDRL A027 in FY2024."

**Forbidden assertions at GREEN:**
- Any count computed by the LLM rather than returned by SQL.
- Any rate/ratio without an installed-base denominator substrate.
- Any count over chunks-retrieved-by-vector-search.

---

### YELLOW — Bounded-Evidence Count

**Definition.** The deterministic substrate can partially answer the question. We return what's known with explicit disclosure of what's missing.

**Triggers YELLOW when ANY of:**
- The question asks for a rate/ratio, but only the numerator substrate is populated (no installed-base / denominator yet).
- Filter axis coverage is < 80% for one or more axes (some part_numbers / years / sites not extracted).
- Only `part_number=''` rows match — we have failure events but can't attribute them to specific parts.
- The aggregation crosses a known-incomplete source family (e.g., a family we've mapped but not yet extracted).

**UI badge:** `YELLOW — bounded-evidence count (caveats below)`

**Required output:**
- The best deterministic answer we can produce (e.g., counts without the rate).
- Explicit caveat text: "Failure rate requires installed-base denominator (not yet populated) — showing failure counts only."
- Substrate coverage stats: "Part-number coverage: 8.4% (3,025 of 37,148 events). Coverage for this slice: X events / Y with part_number."
- Specific gap that would move this to GREEN: "Upgrade to GREEN by (a) running Pass 2 chunk extraction, (b) populating `installed_base` table."

**Allowed assertions:**
- "In 2024, the top failure-COUNT parts in NEXION were X, Y, Z. (Failure-rate requires denominator — unavailable.)"
- "Based on the ~30% of chunks with part_number extraction, top failing parts are: …"

**Forbidden assertions at YELLOW:**
- Calling the answer "exact" or "complete" or "definitive."
- Presenting a rate/ratio as a number when only the numerator is known.
- Suppressing the coverage caveat.

---

### RED — Substrate Insufficient / UNSUPPORTED

**Definition.** The substrate cannot support a deterministic answer. The system abstains.

**Triggers RED when ANY of:**
- Filter axis is unresolvable (e.g., "top failing parts in SYSTEMX" where SYSTEMX has no canonical alias).
- Substrate returns 0 matching rows for the requested filters.
- A required axis has < 10% coverage.
- The substrate file is missing or empty.

**UI badge:** `RED — insufficient deterministic evidence`

**Required output:**
- Explicit abstention text: "I cannot answer this deterministically. Reason: [specific gap]."
- What would fix it: "Need substrate population for: installed_base, or alias entry for SYSTEMX, or Pass 2 chunk extraction."
- Optionally: fall through to standard RAG with a flag `deterministic_unavailable=true` so the LLM answer carries appropriate hedging.

**Allowed fallbacks:**
- Passing through to standard RAG, with the LLM warned that this is a quantitative question and it should hedge with phrases like "based on what the retrieved documents mention" rather than stating exact counts.
- Returning UNSUPPORTED with the filter parsing results so the user can refine.

**Forbidden at RED:**
- LLM making up a number by counting top-K retrieved chunks.
- Pretending GREEN or YELLOW when substrate is empty.
- Silent fallback with no hedging signal.

---

## Decision flow (canonical)

```
Query arrives
    |
    v
Is the query aggregation-shaped? (trigger + axis match)
    |── NO → fall through to standard RAG (not subject to this contract)
    |── YES → continue
    v
Parse filter axes (system, site, year, part_number, top_n, per_year, is_rate)
    |
    v
Canonicalize each axis via alias table
    |
    v
Any axis unresolvable?
    |── YES → RED (UNSUPPORTED)
    |── NO → continue
    v
Run parameterized SQL against substrate
    |
    v
rows_matched == 0?
    |── YES → RED
    |── NO → continue
    v
Is this a rate query AND denominator substrate missing?
    |── YES → YELLOW (return counts with rate-unsupported disclaimer)
    |── NO → continue
    v
Is any axis coverage < 80% for the matched slice?
    |── YES → YELLOW (return results with coverage caveat)
    |── NO → continue
    v
GREEN — return ranked result with evidence, no caveats
```

---

## Where this is enforced in code

| Layer | File | Responsibility |
|-------|------|----------------|
| Intent detection | `src/query/aggregation_executor.py::detect_aggregation_intent` | Is this an aggregation query at all? |
| Alias resolution | `AliasTables.resolve_system/resolve_site` | Canonicalize filter axes. Unresolvable → RED signal. |
| Filter parsing | `parse_top_n`, `parse_year_range` | Extract top_n + year_from/year_to. Unparseable → fall through. |
| SQL execution | `FailureEventsStore.top_n_parts`, `top_n_parts_per_year` | Parameterized queries only. Empty result → RED signal. |
| Tier decision | `AggregationExecutor.execute` | Compose final tier (GREEN / YELLOW / RED). |
| Evidence linking | `FailureEventsStore.evidence_for_part` | Attach source-path provenance per top result. |
| Rendering | `_render_top_n`, `_render_per_year` | Produce markdown with tier badge + caveat + coverage footer. |
| Pipeline gate | `QueryPipeline.query` | Run executor BEFORE router. Skip agg path on RED (fall through to RAG). |

---

## Cross-tier rules

1. **Tier never silently upgrades.** GREEN requires all conditions. Any deficiency → YELLOW or RED. A result cannot be auto-promoted.
2. **LLM narrates, never computes.** Regardless of tier, the LLM receives the deterministic rows as input and narrates. It is never asked to count chunks.
3. **Caveats are non-removable.** A YELLOW answer must display its caveat in the UI. The LLM is not permitted to strip it during narration.
4. **Source-path evidence is mandatory at GREEN.** Without ≥ 1 source-path per top result, the tier drops to YELLOW (evidence-coverage gate).
5. **No rate without denominator — ever.** Even if 99% of numerator coverage exists, rate is YELLOW until installed_base substrate is populated.
6. **Determinism is a gate.** Same query × same substrate × same config MUST return same answer across 10 runs. If not, bug. Not YELLOW — bug.

---

## Examples against current substrate (2026-04-18 coverage snapshot)

**Substrate state:**
- `failure_events.sqlite3`: 37,148 events, 3,025 with part_number (8.1%), 36,807 with system, 10,882 with site, 20,642 with year
- `installed_base.sqlite3`: does not exist

| Query | Parses to | Tier | Reason |
|-------|-----------|------|--------|
| "Top 5 failing parts in NEXION in 2024" | sys=NEXION, year=2024-2024 | **GREEN** | All axes resolved; SQL returns ≥ 1 row with part_number |
| "Top 5 failing parts in NEXION in Djibouti in 2024" | sys=NEXION, site=djibouti, year=2024-2024 | **GREEN** if ≥ 1 row matches, else **RED** | Narrower filter may produce 0 rows |
| "Top 5 failure **rate** parts each year × 7 years" | per_year=true, is_rate=true, year=2019-2025 | **YELLOW** | `installed_base` doesn't exist → no rate possible |
| "Top failing parts in SYSTEMX in 2024" | sys=unresolved, year=2024 | **RED** | SYSTEMX not in `canonical_aliases.yaml` |
| "How many NEXION parts total?" (retrieval count) | NOT an aggregation axis shape | **PASSTHROUGH** | Falls through to standard RAG |

---

## Change management

- New system/site aliases are added to `config/canonical_aliases.yaml` — no code change required.
- New tier rules (e.g., a new YELLOW trigger) require code change in `aggregation_executor.py::execute` AND a new entry in this contract.
- Coverage thresholds (80% / 10%) are configurable. Any change must be justified against the truth pack (coverage drop should not turn GREEN answers into YELLOW without a recorded reason).

---

## Sources

- [Aggregation Queries over Unstructured Text: Benchmark and Agentic Method](https://arxiv.org/html/2602.01355v1) — RAG top-K counting is structurally wrong
- [Structure Augmented Generation: Bridging Structured and Unstructured for RAG](https://www.meibel.ai/post/structure-augmented-generation-bridging-structured-and-unstructured-data-for-enhanced-rag-systems) — SAG pattern adopted here
- [CSR-RAG: Enterprise-Scale Text-to-SQL Retrieval](https://www.arxiv.org/pdf/2601.06564)
- Prior internal: `HYBRIDRAG_LOCAL_ONLY\COUNTING_AND_AGGREGATION_WEB_FINDINGS_2026-04-15.md` — MEBench EA-F1 for evidence-attribution scoring

---

Jeremy Randall | CoPilot+ | HybridRAG_V2 | 2026-04-18 MDT
