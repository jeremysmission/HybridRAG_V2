# Vendor Family Map — 2026-04-19

**Author:** Miner-Agent | no lane | 2026-04-19 MDT
**Corpus:** `E:\CorpusTransfr\file_state.sqlite3` (214,751 files) + `relationships.sqlite3` (224,814 rows)
**Companion JSON:** `docs/vendor_family_map_2026-04-19.json`

---

## Executive Summary

The corpus contains **370 distinct vendor names** extracted from PO folder naming conventions, covering **2,847 PO-associated files**. The richest vendor-interaction families are quotes (1,755), proposals (409), catalogs (154), and warranty docs (152). The relationships database adds 4,834 `MANUFACTURED_BY` and 26,337 `SHIPPED_TO` entries but these are noisy from automated extraction. The PO folder pattern is the cleanest vendor source for a future `vendor_directory` substrate.

---

## Top Vendors by PO File Count

| Vendor | PO files | Notes |
|--------|--------:|-------|
| Safety Climbing Gear-Fall Protection | 81 | Product description, not vendor |
| PCPC | 67 | PC parts vendor |
| Cable RG-213 | 46 | Product, not vendor |
| Server-UPS-KVM | 44 | Product category |
| LDI (Lowell Digisonde International) | 43 | Primary equipment manufacturer |
| Grainger | 39 | Industrial supply vendor |
| Newark | 35 | Electronics supplier |
| TESSCO | 21 | Telecom equipment |
| Arrow Moving & Storage | 19 | Logistics/shipping |
| Stresscon-Concrete Structures | 19 | Construction |
| Staples | 17 | Office supplies |
| CDW | 15 | IT equipment vendor |
| Sterling | 15 | Equipment vendor |

---

## Vendor-Related File Patterns

| Family | Count | Description |
|--------|------:|-------------|
| quote | 1,755 | Price quotes and vendor quotes |
| proposal | 409 | Vendor proposals |
| catalog | 154 | Product catalogs |
| warranty | 152 | Warranty documentation |
| vendor_folder | 136 | Vendor-tagged folders/files |
| subcontractor | 52 | Subcontractor SOWs and docs |
| supplier | 31 | Supplier documentation |
| sole_source | 21 | Sole source justifications |
| rma_real | 15 | Return Merchandise Authorization |

---

## Recommendations

A `vendor_directory` substrate is low-priority for the May 2 demo but would enable Q-DEMO-E (replacement cost) and Q-DEMO-F (most expensive items) with vendor attribution. The cleanest path:

1. Extract vendor names from PO folder patterns (already 370 names)
2. Normalize product-description entries vs real vendor names
3. Cross-reference with `po_pricing.vendor` field (7,006 rows already populated)
4. The po_pricing substrate already has vendor data — a separate vendor map is enrichment, not prerequisite

---

Miner-Agent | no lane | 2026-04-19 MDT
