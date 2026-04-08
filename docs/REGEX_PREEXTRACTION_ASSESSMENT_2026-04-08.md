# Regex Pre-Extraction Assessment — Porting V1 to V2

**Date:** 2026-04-08 MDT
**Author:** Jeremy Randall (CoPilot+)
**Problem:** GLiNER extraction at 1 chunk/sec CPU = 312K chunks would take 87 hours

---

## V1 Regex Extraction Coverage

V1's `service_event_extractor.py` + `structured_report_utils.py` use 12 compiled regex patterns to extract entities at near-zero cost. Here's what they cover mapped to V2 entity types:

### Direct Mapping (V1 regex -> V2 entity type)

| V1 Pattern | Extracts | V2 Type | Speed |
|-----------|----------|---------|-------|
| `Part#:`, `Component:` field labels | Part numbers, component names | PART | Instant |
| `SN[-: ]?[A-Za-z0-9-]+` | Serial numbers | PART | Instant |
| `qty[:=]?\s*(\d+)` | Quantities | PART (metadata) | Instant |
| `[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}` | Email addresses | CONTACT | Instant |
| `\+?\d[\d(). -]{6,}\d` | Phone numbers | CONTACT | Instant |
| `((?:19\|20)\d{2})` | Years | DATE | Instant |
| `FSR\|UMR\|IR\|ASV\|RTS-[A-Za-z0-9_-]+` | Report IDs | PO (mapped) | Instant |
| `Site:`, `Location:` field labels | Site names | SITE | Instant |
| `Point of Contact:`, `POC:` field labels | Contact names | PERSON | Instant |
| `Action:`, `Failure Mode:`, `Condition:` | Maintenance actions | PART (context) | Instant |
| Power/lightning keyword matching | Event classification | (metadata) | Instant |
| Issue category inference | Issue types | (metadata) | Instant |

### Coverage Estimate

| Entity Type | V2 Count | Regex Coverable | GLiNER Needed For |
|------------|----------|----------------|-------------------|
| PART (13,543) | ~60-70% | Part numbers, serials, quantities | Complex part descriptions |
| CONTACT (9,342) | ~80-90% | Emails, phone numbers | Name-only contacts |
| DATE (7,110) | ~70-80% | Explicit dates and years | Relative dates ("last month") |
| PO (1,033) | ~90%+ | PO-XXXX, FSR/UMR report IDs | Free-text PO references |
| SITE (2,136) | ~50-60% | Labeled fields, known vocabulary | Unlabeled site mentions |
| PERSON (2,230) | ~30-40% | POC/technician labeled fields | Names in prose |
| ORG (5,587) | ~20-30% | Known org names | Novel organizations |
| **Overall** | **~60-65%** | | |

### Recommended Strategy: Two-Pass Extraction

**Pass 1: Regex (fast, ~100K chunks/sec)**
- Port V1 patterns to V2 `scripts/regex_preextract.py`
- Run against all 312K chunks — takes ~3 seconds
- Produces PART, CONTACT, DATE, PO entities at high precision
- Stores in `entities.sqlite3` with `extraction_method='regex'`

**Pass 2: GLiNER (slow, ~1 chunk/sec CPU or faster on GPU)**
- Only runs on chunks NOT fully covered by regex pass
- Handles PERSON, ORG, complex relationships
- Priority: chunks with zero regex entities (likely narrative text)
- Can be batched overnight

### What to Port

The V1 code is 1,942 lines across 3 files. The core portable pieces are:

1. **`_FIELD_VALUE_RE`** — extracts `Label: Value` pairs from report format text
2. **`_EVENT_LABELS`** — maps 20+ field label variants to canonical fields
3. **`_SERIAL_RE`** — serial number extraction
4. **`_QTY_RE`** — quantity extraction
5. **`_EMAIL_RE`** — email extraction
6. **`_PHONE_RE`** — phone extraction
7. **`_REPORT_ID_RE`** — report ID (FSR/UMR/IR/ASV/RTS) extraction
8. **`_YEAR_RE`** / **`_YEAR_RANGE_RE`** — date/year extraction
9. **`_iter_event_blocks`** — splits chunks into maintenance event blocks
10. **`_normalize_event_row`** — normalizes extracted fields

### What NOT to Port

- `document_catalog_extractor.py` — V1-specific catalog structure
- `structured_report_utils.py` site canonicalization (US states, countries) — overkill for V2, use config vocabulary instead
- V1 SQLite schema (`service_events` table) — V2 uses its own entity schema

### Implementation Plan

1. Create `scripts/regex_preextract.py` — reads chunks from LanceDB, runs regex patterns, inserts into entity store
2. Add `extraction_method` column to entity store (or use context field) to distinguish regex vs GLiNER entities
3. Run on all 49,750 current chunks as proof of concept
4. When 312K field_engineer export arrives, run regex first, then selective GLiNER

### Time Estimates

| Corpus | Regex Pass | GLiNER (CPU, all) | GLiNER (GPU, all) | Regex + selective GLiNER |
|--------|-----------|-------------------|-------------------|-------------------------|
| 49,750 | ~1 sec | ~14 hours | ~30 min (est.) | ~1 sec + ~5 min |
| 312,000 | ~3 sec | ~87 hours | ~3 hours (est.) | ~3 sec + ~30 min |

### V1 Reference Files (copied to V2)

Located at `scripts/v1_reference/`:
- `service_event_extractor.py` (801 lines)
- `structured_report_utils.py` (642 lines)
- `document_catalog_extractor.py` (499 lines)

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
