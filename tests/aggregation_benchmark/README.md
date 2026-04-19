# Aggregation Benchmarks

This folder contains two **distinct** aggregation benchmarks that exercise
different layers of the V2 query stack. They share a folder but intentionally
do **not** share a schema — each is coupled to its own runner.

Do not merge them. Each benchmark answers a different question.

---

## 1. `aggregation_seed_manifest_2026-04-15.json`  (frozen count benchmark)

**Purpose.** Score an answer's exact numeric value against a manually-
established ground-truth count for a specific corpus slice. Answers the
question: *given this well-defined slice of the corpus, is the system
returning the correct integer?*

**Schema.**
```json
{
  "benchmark_id": "aggregation_benchmark_2026-04-15",
  "items": [
    {
      "id": "AGG-001",
      "family": "confabulation",
      "question": "How many files are in ...",
      "answer_kind": "exact_count",
      "expected_answer": 76,
      "scope_rule": "...",
      "dedup_rule": "...",
      "counting_note": "...",
      "source_reference": "...",
      "evidence_notes": "..."
    }
  ]
}
```

**Runner.** `scripts/run_aggregation_benchmark_2026_04_15.py`

**Gate.** All items must pass (`pass_rule: all_items_pass`). Single-number
correctness only.

**Scope.** Pre-existing V2 benchmark, unchanged by the failure-aggregation
slice.

---

## 2. `failure_truth_pack_2026-04-18.json`  (tier + filter-parsing benchmark)

**Purpose.** Score the deterministic failure-aggregation backend's ability to
(a) detect aggregation intent, (b) parse filter axes from natural language,
(c) return the correct evidence tier per the `aggregation_evidence_contract`,
and (d) produce a non-empty ranked result when GREEN. Answers the question:
*given these natural-language failure-aggregation queries, does the backend
route correctly and return the right contract tier?*

**Schema.**
```json
{
  "truth_pack_id": "failure_aggregation_truth_pack_2026-04-18",
  "items": [
    {
      "id": "FAIL-AGG-01",
      "query": "What were the highest failing part numbers in the monitoring systems in 2024?",
      "tier_expected": "GREEN",
      "expected_shape": "top_n_by_part",
      "expected_filters": { "system": "monitoring system", "year_from": 2024, "year_to": 2024 },
      "expected_params": { "top_n": 5 },
      "ground_truth_sql": "SELECT part_number, COUNT(*) ... GROUP BY part_number ORDER BY ... LIMIT 5",
      "requires_chunk_pass": true,
      "requires_denominator": false
    }
  ]
}
```

**Runner.** `scripts/run_failure_aggregation_benchmark.py`

**Gate.** Per-item pass requires:
- Tier match (soft: GREEN expected → GREEN or YELLOW accepted when substrate
  coverage drives YELLOW; hard FAIL only for RED or parse miss)
- Filter match (expected_filters subset matches parsed_params)
- Parameter match (expected_params subset matches parsed_params)
- Result presence when GREEN expected (non-empty ranked_rows or per_year_rows)

**Scope.** New in the 2026-04-18 failure-aggregation slice.

---

## Why not merge?

The two benchmarks answer orthogonal questions:

| Dimension | Frozen count benchmark | Failure truth pack |
|-----------|-----------------------|--------------------|
| Signal | Exact numeric correctness | Intent + filter + tier correctness |
| Scope boundary | Filesystem slice | Natural-language axis parsing |
| Ground truth source | Manifest + filesystem count | Substrate SQL + alias table |
| Gate rule | all_items_pass (strict) | Per-item tier/filter/result (soft GREEN→YELLOW) |
| Failure mode caught | LLM fabricated numeric answer | Router misrestricted, filter unresolved, substrate coverage gap |

Merging them would force either:
- Scoring the tier benchmark on exact numeric match (losing tier semantics), OR
- Scoring the count benchmark on tier match (losing integer discipline).

Both benchmarks are small, cheap, and complementary. Keep them separate.

---

## Adding new items

- To add an **exact-count** question with a known integer answer, append to
  `aggregation_seed_manifest_2026-04-15.json` and increment the `AGG-NNN` id.
  The gate is strict (`all_items_pass`), so only add items with verified
  ground truth.

- To add a **failure-aggregation natural-language** question, append to
  `failure_truth_pack_2026-04-18.json` using the `FAIL-AGG-NN` id scheme.
  Include `tier_expected`, `expected_filters`, `expected_params` at minimum.
  Narrow filters (e.g., site + year + system all together) can legitimately
  return RED on a small substrate — mark those with a note in the item.

---

Jeremy Randall | CoPilot+ | HybridRAG_V2 | 2026-04-19 MDT
