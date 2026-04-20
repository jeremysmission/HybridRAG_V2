# Aggregation Backend Accuracy Report

**Truth pack:** `tests\aggregation_benchmark\failure_truth_pack_2026-04-18.json`
**Substrate:** {'total_events': 35649, 'with_part_number': 3017, 'with_system': 35649, 'with_site': 10831, 'with_year': 19740, 'distinct_parts': 900, 'distinct_systems': 2, 'distinct_sites': 22}
**Run at:** 2026-04-19 20:28:28 MDT

## Summary

- **Pass rate:** 39/50 (78.0%)
- **Latency p50:** 21 ms
- **Latency max:** 116 ms
- **Tier distribution:** {'GREEN': 26, 'YELLOW': 4, 'RED': 14, 'PASSTHROUGH': 6}

## Per-Question Results

| ID | Expected | Actual | Pass | Top-3 / Per-Year | Latency | Notes |
|----|----------|--------|------|------------------|---------|-------|
| FAIL-AGG-01 | GREEN | GREEN | **PASS** | `EC11612, RFA-4005, SEMS3D-41785` | 41ms | - |
| FAIL-AGG-02 | GREEN | GREEN | **PASS** | `SEMS3D-35674, TA00122` | 38ms | - |
| FAIL-AGG-03 | YELLOW | YELLOW | **PASS** | `2020:SEMS3D-40877, 2021:SEMS3D-35674, 2022:SEMS3D-35674` | 47ms | - |
| FAIL-AGG-04 | GREEN | GREEN | **PASS** | `AS-2023, WSU050, AC-200` | 35ms | - |
| FAIL-AGG-05 | GREEN | GREEN | **PASS** | `IGS-2461, TA00122, RFN-1005` | 17ms | - |
| FAIL-AGG-06 | GREEN | RED | **FAIL** | `-` | 13ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-07 | GREEN | GREEN | **PASS** | `SEMS3D-40877, SEP-2020, SEMS3D-35674` | 57ms | - |
| FAIL-AGG-08 | GREEN | RED | **FAIL** | `-` | 12ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-09 | GREEN | GREEN | **PASS** | `2022:SEMS3D-35674, 2023:AS-2023, 2024:EC11612` | 31ms | - |
| FAIL-AGG-10 | GREEN | GREEN | **PASS** | `2024:EC11612, 2025:GUM-2025, 2026:UR022` | 30ms | - |
| FAIL-AGG-11 | YELLOW | YELLOW | **PASS** | `2022:SEMS3D-35674, 2023:AS-2023, 2024:EC11612` | 63ms | - |
| FAIL-AGG-12 | GREEN | RED | **FAIL** | `-` | 12ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-13 | GREEN | RED | **FAIL** | `-` | 14ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-14 | GREEN | GREEN | **PASS** | `SEMS3D-41158, SEMS3D-41172, LCD8500` | 15ms | - |
| FAIL-AGG-15 | GREEN | GREEN | **PASS** | `SM-219` | 13ms | - |
| FAIL-AGG-16 | GREEN | GREEN | **PASS** | `SEMS3D-41785, SEMS3D-41786, SEMS3D-42184` | 19ms | - |
| FAIL-AGG-17 | GREEN | GREEN | **PASS** | `SEMS3D-35674, SEMS3D-40507, SEMS3D-40536` | 58ms | - |
| FAIL-AGG-18 | GREEN | GREEN | **PASS** | `2020:SEMS3D-40877, 2021:SEMS3D-35674, 2022:SEMS3D-35674` | 36ms | - |
| FAIL-AGG-19 | PASSTHROUGH | PASSTHROUGH | **PASS** | `-` | 0ms | passthrough test |
| FAIL-AGG-20 | PASSTHROUGH | PASSTHROUGH | **PASS** | `-` | 0ms | passthrough test |
| FAIL-AGG-21 | GREEN | GREEN | **PASS** | `ES-4635, ES-6534, ES-3202` | 65ms | - |
| FAIL-AGG-22 | GREEN | GREEN | **PASS** | `RQ-05897, ES-3202, ES-6534` | 28ms | - |
| FAIL-AGG-23 | GREEN | GREEN | **PASS** | `SEMS3D-37635, SEMS3D-37626, SEMS3D-37627` | 25ms | - |
| FAIL-AGG-24 | GREEN | GREEN | **PASS** | `SEMS3D-35674, SEMS3D-36411` | 17ms | - |
| FAIL-AGG-25 | GREEN | GREEN | **PASS** | `SEMS3D-35674, SEMS3D-40331, SEMS3D-40353` | 24ms | - |
| FAIL-AGG-26 | GREEN | GREEN | **PASS** | `SEMS3D-35674, SEMS3D-41888, SEMS3D-41889` | 24ms | - |
| FAIL-AGG-27 | GREEN | GREEN | **PASS** | `SEMS3D-40877, SEP-2020, SEMS3D-39847` | 25ms | - |
| FAIL-AGG-28 | GREEN | GREEN | **PASS** | `SEMS3D-40877, SEP-2020, SEMS3D-35674` | 45ms | - |
| FAIL-AGG-29 | GREEN | GREEN | **PASS** | `2022:SEMS3D-35674, 2023:AS-2023, 2024:EC11612` | 54ms | - |
| FAIL-AGG-30 | GREEN | GREEN | **PASS** | `2017:WES2017, 2018:WES2018, 2019:SEMS3D-38546` | 48ms | - |
| FAIL-AGG-31 | GREEN | RED | **FAIL** | `-` | 12ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-32 | GREEN | RED | **FAIL** | `-` | 11ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-33 | GREEN | RED | **FAIL** | `-` | 11ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-34 | GREEN | RED | **FAIL** | `-` | 10ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-35 | GREEN | RED | **FAIL** | `-` | 11ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-36 | GREEN | GREEN | **PASS** | `2020:SEMS3D-35674, 2021:SEMS3D-35674, 2022:SEMS3D-35674` | 67ms | - |
| FAIL-AGG-37 | GREEN | GREEN | **PASS** | `EC11612, RFA-4005, SEMS3D-41785` | 37ms | - |
| FAIL-AGG-38 | GREEN | GREEN | **PASS** | `AS-2023, WSU050, AC-200` | 32ms | - |
| FAIL-AGG-39 | GREEN | RED | **FAIL** | `-` | 12ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-40 | GREEN | RED | **FAIL** | `-` | 10ms | tier: expected=GREEN actual=RED; expected ranked results but got empty (tier=RED) |
| FAIL-AGG-41 | YELLOW | RED | **PASS** | `-` | 10ms | tier: expected=YELLOW actual=RED |
| FAIL-AGG-42 | YELLOW | YELLOW | **PASS** | `SEMS3D-40877, SEP-2020, SEMS3D-35674` | 46ms | - |
| FAIL-AGG-43 | YELLOW | YELLOW | **PASS** | `2024:EC11612, 2025:GUM-2025, 2026:UR022` | 21ms | - |
| FAIL-AGG-44 | RED | RED | **PASS** | `-` | 14ms | - |
| FAIL-AGG-45 | RED | RED | **PASS** | `-` | 10ms | - |
| FAIL-AGG-46 | GREEN | GREEN | **PASS** | `ES-4635, ES-3202, WES2016` | 116ms | - |
| FAIL-AGG-47 | PASSTHROUGH | PASSTHROUGH | **PASS** | `-` | 0ms | passthrough test |
| FAIL-AGG-48 | PASSTHROUGH | PASSTHROUGH | **PASS** | `-` | 0ms | passthrough test |
| FAIL-AGG-49 | PASSTHROUGH | PASSTHROUGH | **PASS** | `-` | 0ms | passthrough test |
| FAIL-AGG-50 | PASSTHROUGH | PASSTHROUGH | **PASS** | `-` | 0ms | passthrough test |

## Interpretation

- **GREEN expected → YELLOW actual** is acceptable when the substrate has coverage < 80% for a filter axis. These are counted as soft-pass.
- **GREEN expected → RED actual** is a true fail — substrate is missing or filter unresolved.
- **PASSTHROUGH expected → None actual** is the correct behavior for non-aggregation queries.

## Substrate Gaps Detected

- FAIL-AGG-06: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-08: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-12: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-13: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-31: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-32: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-33: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-34: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-35: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-39: 0 rows matched — narrower filter than substrate supports
- FAIL-AGG-40: 0 rows matched — narrower filter than substrate supports

---

Jeremy Randall | CoPilot+ | HybridRAG_V2 | 2026-04-18 MDT