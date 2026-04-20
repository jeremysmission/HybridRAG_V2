# PO-Pricing Date Coverage Diagnostic — 2026-04-19

**Author:** Miner-Agent | no lane | 2026-04-19 MDT
**Diagnosis:** `extractor_missing_pattern` (NOT genuine absence)
**Companion JSON:** `docs/po_pricing_date_coverage_2026-04-19.json`

---

## Executive Summary

Agent-B's po_pricing populate produced a date range of 2015-10-29 to 2022-02-28, missing 2023-2025 entirely. **The gap is an extractor pattern issue, not a data absence.** The corpus contains 371 PO-family files with 2023-2025 path dates, and the retrieval metadata has 47 rows with extracted `po_number` for those years. The root cause is a structural shift in the corpus: older PO data (2015-2019) lives under `zzSEMS ARCHIVE/005_ILS/Purchases/` with YYYY-MM-DD path dates, while newer data (2020-2025) migrated to `5.0 Logistics/Procurement/` and `10.0 Program Management/` with different date embedding patterns that the extractor doesn't parse into `po_date`.

---

## Per-Year PO-Family Document Counts

| Year | File count | Note |
|------|----------:|------|
| 2015 | 1,210 | Archive era (bulk) |
| 2016 | 378 | |
| 2017 | 1,319 | |
| 2018 | **2,331** | Peak — most active procurement year |
| 2019 | 657 | |
| 2020 | 64 | Sharp drop — folder structure shift begins |
| 2021 | 46 | |
| 2022 | 57 | Agent-B populate ends here (2022-02-28) |
| 2023 | **66** | Data exists but extractor misses dates |
| 2024 | **141** | 12 monthly PR & PO xlsx + contracts |
| 2025 | **164** | Active procurement, growing |

---

## 2023-2025 Breakdown by Family

| Family | 2023 | 2024 | 2025 | Total |
|--------|-----:|-----:|-----:|------:|
| contract_path | 18 | 59 | 73 | 150 |
| vendor_invoice | 11 | 43 | 28 | 82 |
| po_token_path | 14 | 17 | 24 | 55 |
| procurement_dir | 20 | 15 | 25 | 60 |
| pr_and_po_xlsx | 6 | 19 | 8 | 33 |
| purchases_dir | 3 | 7 | 14 | 24 |
| **Total** | **72** | **160** | **172** | **404** |

---

## Root Cause: Folder Structure + Date Format Shift

### Old pattern (2015-2019, well-captured):
```
zzSEMS ARCHIVE/005_ILS/Purchases/2-Received/1-Received/
  WX29 (PO 7000372377)(Newark)(RG-58 Cable)($388.24)Rcvd 2019-04-08/
    PO 7000372377.pdf
```
- PO number in folder: `PO 7000372377`
- Date in folder: `Rcvd 2019-04-08` (YYYY-MM-DD, easy regex)
- Price in folder: `$388.24`
- All metadata is path-extractable

### New pattern (2020-2025, missed):
```
5.0 Logistics/Procurement/002 - Received/
  NEXION Sustainment OY1 (1 Aug 23 - 31 Jul 24)/
    PO - 5000453984, PR 3000037430 Item Description.pdf
```
- PO number in filename: `PO - 5000453984` (dash-separated, new 5xxx format)
- Date in FOLDER: `1 Aug 23 - 31 Jul 24` (natural language, not YYYY-MM-DD)
- No price in path
- Requires different date parsing regex

### Monthly PR & PO spreadsheets (highest value, not captured):
```
10.0 Program Management/1.0 FEP/Matl/
  2024 01 PR & PO_1.xlsx
  2024 02 PR & PO_1.xlsx
  ...
  2024 12 PR & PO_1.xlsx
  2025.02 PR & PO_R2_1.xlsx
```
- 12 monthly structured xlsx files for 2024
- 3+ files for 2025
- These contain tabular PO data with dates inside the spreadsheet
- The extractor likely processes them but can't extract `po_date` from the content

### PO Number Format Shift
| Era | Format | Example |
|-----|--------|---------|
| Pre-2020 | 70xx/72xx/75xx (10-digit) | 7000342321, 7200753121 |
| Post-2020 | 50xx/53xx (9-10 digit) | 5000453984, 5300168054 |

---

## Recommendation for Agent-B

### Pattern additions needed (priority order):

1. **Date regex for new procurement folders:**
   - Current: expects `YYYY-MM-DD` or `Rcvd YYYY-MM-DD` in path
   - Add: `(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4})` for `1 Aug 23` format
   - Add: `(\d{4})\s+(\d{2})\s+PR\s*&\s*PO` for `2024 01 PR & PO` filename format

2. **PO number regex for new format:**
   - Current: likely matches `PO\s+\d{10}` (old 7xxx format)
   - Add: `PO\s*-\s*\d{10}` for the `PO - 5000453984` dash-separated format
   - Add: `PO\s*-\s*\d{9}` for 9-digit variants

3. **Path filter for new procurement folders:**
   - Add: `5.0 Logistics/Procurement/002 - Received/` as a high-priority scan path
   - Add: `10.0 Program Management/1.0 FEP/Matl/` for monthly PR & PO xlsx
   - Add: `10.0 Program Management/#GSA_OASIS/` for contracts and invoices

4. **Contract period to po_date mapping:**
   - Folders like `NEXION Sustainment OY1 (1 Aug 23 - 31 Jul 24)` contain the contract period
   - Map `start_date` of the period as the `po_date` for docs under that folder

### No action needed (confirm):
- The `source_metadata.po_number` extraction already captures new 5xxx PO numbers (47 rows for 2023-2025)
- The chunk scanning pipeline processes these files
- The issue is specifically `po_date` extraction, not PO detection

---

## Verification Query

After fixing the date patterns, Agent-B can verify with:
```sql
SELECT strftime('%Y', po_date) as yr, COUNT(*) FROM po_pricing
WHERE po_date IS NOT NULL
GROUP BY yr ORDER BY yr;
```
Expected: rows for 2023, 2024, 2025 should appear.

---

Miner-Agent | no lane | 2026-04-19 MDT
