# Installed-Base Family Map — 2026-04-19

**Author:** Miner-Agent | no lane | 2026-04-19 MDT
**Corpus:** `E:\CorpusTransfr\verified\IGS` (214,751 files, deduplicated)
**Metadata source:** `E:\CorpusTransfr\file_state.sqlite3`
**Companion JSON:** `docs/installed_base_family_map_2026-04-19.json`

---

## Executive Summary

The corpus contains **11,534 files** matching installed-base patterns across **20 family categories**. The strongest extraction targets for Agent-C's `installed_base` substrate are:

1. **Site Inventory Report xlsx** (86 files) — structured tabular, per-site, date-stamped. Highest ROI.
2. **As-built drawings/docs** (4,188 files) — deployment anchor records. 1,030 PDFs, 349 xlsx.
3. **Installation summary docs** (456 files) — capture install events per site.
4. **Acceptance test plans** (357 files) — bookend deployment dates.
5. **Spares inventory** (14 targeted files) — per-site spare-kit snapshots.

**System coverage:** NEXION 96,974 (45%) | ISTO 33,407 (16%) | SCINDA 762 (<1%) | untagged 83,608 (39%)

**Date range:** 2000–2026 (27 years of file-date evidence in paths)

**Sites with installed-base docs:** 27 sites have at least 1 inventory/as-built file. Lualualei (335), Guam (132), and Vandenberg (107) have the richest coverage.

---

## Per-Pattern Table

| # | Family | Count | Ext filter | Notes |
|---|--------|------:|------------|-------|
| 1 | `inventory_broad` | 1,870 | all | All inventory-tagged documents |
| 2 | `site_inventory_all` | 594 | all | Site inventory docs (PDF, photos, xlsx) |
| 3 | `site_inventory_xlsx` | **86** | .xlsx | **HIGHEST YIELD** — tabular, extractable |
| 4 | `spares_inventory` | 14 | all | Per-site spares snapshots |
| 5 | `as_built_all` | 4,188 | all | As-built drawings and documents |
| 6 | `as_built_pdf` | 1,030 | .pdf | As-built PDFs |
| 7 | `as_built_xlsx` | 349 | .xlsx | As-built spreadsheets |
| 8 | `installation_summary` | 456 | all | Install summary documentation |
| 9 | `acceptance_test` | 357 | all | Acceptance test plans/procedures |
| 10 | `equipment_list_docs` | 1,630 | all | Equipment lists and packing lists |
| 11 | `calibration_records` | 782 | all | Calibration records |
| 12 | `dd250_transfer` | 54 | all | DD250 transfer forms |
| 13 | `test_cards` | 324 | all | Pre/post deployment test cards |
| 14 | `serial_number` | 69 | all | Serial number photos/docs |
| 15 | `config_baseline` | 6 | all | Configuration baseline drawings |
| 16 | `bill_of_materials` | 35 | all | BOM / PBOM |
| 17 | `deployment_docs` | 40 | all | Deployment documentation |
| 18 | `commissioning` | 59 | all | Commissioning/decommissioning |
| 19 | `nomenclature` | 15 | all | Nomenclature sheets |
| 20 | `asset_tag` | 5 | all | Asset tag photos |

---

## Site Installed-Base Coverage

Sites with highest installed-base document counts (inventory + as-built + spares + install summary + equipment):

| Site | IB docs | Total files |
|------|--------:|------------:|
| Lualualei | 335 | 4,850 |
| Guam | 132 | 10,122 |
| Vandenberg | 107 | 16,231 |
| San Vito | 72 | 9,047 |
| Eielson | 69 | 5,173 |
| Eglin | 66 | 3,297 |
| Thule | 64 | 1,453 |
| UAE | 63 | 560 |
| Ascension | 42 | 15,650 |
| Alpena | 41 | 6,055 |
| Fairford | 33 | 7,489 |
| Learmonth | 32 | 11,872 |
| Eareckson | 19 | 1,923 |
| Wake | 14 | 2,181 |
| Kwajalein | 13 | 1,244 |
| Misawa | 12 | 1,204 |
| Curacao | 10 | 1,892 |
| Singapore | 6 | 796 |
| Azores | 2 | 559 |
| Awase (Okinawa JP) | 1 | 392 |
| Diego Garcia | 1 | 730 |
| Djibouti | 1 | 145 |
| Niger | 1 | 122 |

---

## Recommendations for Agent-C's Extractor Regex Set

### Tier 1 — Start here (structured, highest confidence)

1. **`Site Inventory Report_*.xlsx`**
   - Regex: `Site.Inventory.Report.*\.xlsx$`
   - Expected: ~86 files, tabular with `part_number`, `qty_installed`, `qty_spare`, `site`, `date`
   - Path carries site name and visit date

2. **As-built xlsx spreadsheets**
   - Regex: `[Aa]s[-_][Bb]uilt.*\.xlsx$`
   - Expected: ~349 files, structured deployment records
   - Path carries site and install date

### Tier 2 — High value, needs template detection

3. **`Spares Inventory (SITE)_(DATE).pdf`**
   - Regex: `Spares.Inventory.*\.(pdf|xlsx)$`
   - Expected: ~14 files, per-site spare-kit snapshots
   - Dates and sites extractable from filename

4. **Installation Summary Documents**
   - Regex: `Installation.Summary.*(Report|Documentation).*\.(pdf|docx)$`
   - Expected: ~456 files, install event records
   - Site and system extractable from parent path

### Tier 3 — Supporting evidence, lower structure

5. **Acceptance Test Plans** — bookend deployment dates
6. **DD250 Transfer Forms** — government acceptance records
7. **Equipment Packing Lists** — what was shipped per install
8. **Calibration Records** — confirm equipment was operational at site
9. **Bill of Materials / PBOM** — part-level cost/inventory baseline

### Recommended Extractor Configuration

```yaml
installed_base_families:
  - name: site_inventory_xlsx
    path_regex: "Site.Inventory.*\\.xlsx$"
    priority: 1
    extraction_method: tabular_xlsx
  - name: as_built_xlsx
    path_regex: "[Aa]s[-_][Bb]uilt.*\\.xlsx$"
    priority: 2
    extraction_method: tabular_xlsx
  - name: spares_inventory
    path_regex: "Spares.Inventory.*\\.(pdf|xlsx)$"
    priority: 3
    extraction_method: filename_metadata + tabular_xlsx
  - name: install_summary
    path_regex: "Installation.Summary.*(Report|Doc).*\\.(pdf|docx)$"
    priority: 4
    extraction_method: header_parse
  - name: acceptance_test
    path_regex: "Acceptance.Test.*\\.(pdf|docx)$"
    priority: 5
    extraction_method: header_parse
```

---

## Gaps / Outliers / Anomalies

1. **No dedicated "installed_base" named folder exists.** The data is distributed across Site Visits, Install folders, and Logistics. Agent-C must mine across folder boundaries.

2. **Lualualei dominance** (335 IB docs) is disproportionate. Investigate whether this reflects genuine coverage depth or folder duplication.

3. **Djibouti/Niger/Diego Garcia** have only 1 IB doc each despite having operational sites. These are gap sites where installed-base counts will be zero — Q3 rate calculations should degrade to YELLOW for these.

4. **ISTO installed-base files are sparse.** Most as-built and inventory docs are NEXION-tagged. ISTO rate denominators will have weaker confidence.

5. **Date extraction from paths is reliable** — the `YYYY-MM-DD thru MM-DD` folder pattern appears consistently in Site Visits. Agent-C can extract `snapshot_date` from this pattern with high confidence.

6. **All 214,751 files in file_state have status="duplicate"** — this is the Forge dedup state, not an error. The files exist and are accessible on E:.

7. **Original paths reference `C:/Users/randaje/Documents/HybridRAG3/data/source/verified/IGS/`** — Agent-C's extractor should normalize these to the current E: location or work from the path patterns (not absolute paths).

8. **C: drive is 100% full** — this output was written but any large extraction work on C: will fail. Flag for Coordinator.

---

Miner-Agent | no lane | 2026-04-19 MDT
