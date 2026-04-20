# Litmus NEXION BOM Ground Truth

**Author:** Miner-Agent | no lane | 2026-04-20 MDT
**JSON:** `docs/litmus_nexion_bom_2026-04-20.json`

---

## Summary

- **6 xlsx files** parsed from `5.0 Logistics/NEXION BOM/`
- **2,320 total data rows** with valid part numbers
- **1,282 distinct parts** across all BOMs
- Date range: Nov 2023 (Installation Master List) through Jun 2025 (Estimates)

## Key Files

| File | Sheet | Rows | Distinct parts | Headers |
|------|-------|-----:|---------------:|---------|
| Azores Installation Master List (2023-11-02) | PART DETAIL | 497 | 497 | PART NUMBER, HWCI, SYSTEM, SUB-SYSTEM |
| Azores Installation Master List (2023-11-02) | PART DETAIL (2) | 499 | 498 | PART NUMBER, HWCI, SYSTEM, SUB-SYSTEM |
| Azores Installation Master List (2023-11-02) | NEXION Installation List | 448 | 395 | Qty, PART NUMBER, NOMENCLATURE |
| NEXION Estimates (2025-06-25) | Materials | 445 | 333 | PART NUMBER, QTY., DESCRIPTION, MANUFACTURER |
| NEXION Estimates (2025-06-25) | Tools & Test Equipment | 39 | 33 | QTY., PART NUMBER, DESCRIPTION |
| Azores Parts List (2024-02-22) | Sheet1 | 382 | 297 | ON-HAND, EBOM, PRICE, QTY., PART NUMBER |

## Agent-C Cross-Reference Value

The 1,282 distinct parts from NEXION BOMs can validate Agent-C's installed_base extraction. If Agent-C's extractor finds a part_number that doesn't appear in any BOM, it's either an ISTO part, a consumable, or a false positive. The Azores Installation Master List is the most complete single-site reference.

The NEXION Estimates (2025) file includes PRICE column — potential cross-reference for Agent-B's po_pricing.

---

Miner-Agent | no lane | 2026-04-20 MDT
