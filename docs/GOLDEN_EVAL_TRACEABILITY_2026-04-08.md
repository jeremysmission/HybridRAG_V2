# Golden Eval Traceability Report

**Date:** 2026-04-11 MDT
**Author:** Jeremy Randall (CoPilot+)
**Scope:** `tests/golden_eval/production_queries_2026-04-11.json`

---

## Purpose

This pack is organized around the 5 real demo personas. Each persona block contains 5 queries, and each query maps to a real production corpus family and a specific routing type.

The traceability goal is simple: every `PQ-###` in the JSON pack must be traceable to the exact question text, type, and corpus family shown below.

---

## Query-Type Distribution

| Type | Count |
|------|-------|
| SEMANTIC | 5 |
| ENTITY | 4 |
| TABULAR | 6 |
| AGGREGATE | 4 |
| COMPLEX | 6 |

---

## Persona Maps

### Program Manager

| ID | Type | Query | Corpus family |
|----|------|-------|---------------|
| PQ-001 | TABULAR | Which CDRL deliverables in A001, A009, and A031 have the latest status updates? | CDRLs - 1.5 enterprise program CDRLS |
| PQ-002 | SEMANTIC | What schedule milestones and slips are shown in the latest PMR and Integrated Master Schedule? | Program Management - 6.0 PMR + CDRL A031 IMS |
| PQ-003 | TABULAR | How do the current FEP actuals compare to the funding plan and LDI burn-rate by OY3? | Program Management - 1.0 FEP + LDI budget/hours spreadsheets |
| PQ-004 | ENTITY | What is the latest PMR briefing file name for the enterprise program program? | Program Management - 6.0 PMR |
| PQ-005 | COMPLEX | What staffing, suborganization, and budget risks are flagged across the latest PM brief and variance reports? | Follow-on materials + PMR/SubK Slides + Weekly Variance Reports + FEP |

### Logistics Lead

| ID | Type | Query | Corpus family |
|----|------|-------|---------------|
| PQ-006 | TABULAR | What purchase orders are currently open and which vendors or CLINs are still outstanding? | Logistics / Procurement - open purchases |
| PQ-007 | ENTITY | Which site is named on the latest hand-carry packing list? | Logistics / Shipments - hand-carry packing list |
| PQ-008 | TABULAR | What parts are on the recommended spares list and what are their part numbers, quantities, and OEMs? | Logistics / Parts - Recommended Spares Parts List |
| PQ-009 | SEMANTIC | Which equipment is due for calibration next, and what do the calibration audit folders show? | Logistics / Calibration - yearly folders and calibration PDF |
| PQ-010 | COMPLEX | Which OCONUS shipments also required customs or export-control paperwork, and what did they contain? | Shipments + Disposition + EEMS + DD250 records |

### Field Engineer

| ID | Type | Query | Corpus family |
|----|------|-------|---------------|
| PQ-011 | AGGREGATE | What parts have the highest failure rates across all sites based on the Part Failure Tracker and corrective action folders? | Part Failure Tracker + A001 CAP folders + Failure Summary DID |
| PQ-012 | AGGREGATE | What Maintenance Service Reports have been filed across all monitoring system sites, and what maintenance actions and part replacements do they document? | CDRL A002 MSR folders |
| PQ-013 | SEMANTIC | What site outages have been caused by power failures, UPS issues, or environmental damage, and what were the return-to-service procedures? | Site Outages Analysis + power-repair artifacts |
| PQ-014 | ENTITY | Which site is associated with the latest Awase Okinawa installation package? | Awase Okinawa install folders + A006/A007 artifacts |
| PQ-015 | COMPLEX | What installation acceptance tests were performed at the Awase Okinawa install, and what does the Site Installation Plan say about the phases? | Awase install folders + A003 SIP + A006/A007 artifacts |

### Network Admin / Cybersecurity

| ID | Type | Query | Corpus family |
|----|------|-------|---------------|
| PQ-016 | SEMANTIC | What ACAS scan results, SCAP scan results, and STIG review findings are documented for ISTO and monitoring system systems? | A027 DAA Accreditation Support Data + STIG review + CT&E-ST&E folders |
| PQ-017 | ENTITY | What system name is listed on the latest RMF Security Plan? | A027 RMF Security Plan / Security Authorization Package |
| PQ-018 | SEMANTIC | What security events and cyber incidents have been documented, including the Fairford Russian event and the Alpena PPTP buffer overflow? | Security Events archive |
| PQ-019 | TABULAR | What ATO re-authorization packages have been submitted and what system changes triggered them? | ATO-ATC package changes + A027 authorization artifacts |
| PQ-020 | COMPLEX | What monthly continuous monitoring audit results are documented for 2024, and what cybersecurity directives are active? | Monthly audits archive + directive set |

### Aggregation / Cross-role

| ID | Type | Query | Corpus family |
|----|------|-------|---------------|
| PQ-021 | AGGREGATE | How many monitoring system and ISTO sites are there, where are they located, and which ones have had installations or maintenance visits in the last three years? | monitoring system Sites + ISTO sites + Site Visits + MSR folders |
| PQ-022 | COMPLEX | Which sites have had Corrective Action Plans filed, what incident numbers and failure types were involved, and what parts were consumed? | A001 CAP folders + Part Failure Tracker + MSRs + spares lists |
| PQ-023 | TABULAR | How many open purchase orders exist across all procurement records, what parts have been received versus outstanding, and what is the total CLIN coverage? | Procurement open/received folders + iBuy GL lists + A014 BOM |
| PQ-024 | AGGREGATE | Summarize all shipment activity, parts disposition, and calibration actions across fiscal years 2022 through 2026. | Shipments + Disposition + Calibration + AssetSmart snapshots |
| PQ-025 | COMPLEX | Give me a cross-program risk summary: what CDRLs are overdue, what ATO packages are pending, what cybersecurity directives remain active, and what parts have recurring failures? | CDRLs + ATO packages + directives + Part Failure Tracker + PMR + FEP |

---

## Traceability Notes

The JSON pack keeps the existing field structure:

- `id`
- `query`
- `expected_facts`
- `expected_confidence`
- `query_type`
- `persona`
- `document_family`
- `production_rationale`

The key correction is that the traceability now mirrors the JSON exactly, query by query, instead of describing a different conceptual mapping.

---

## Acceptance Rule

The pack is aligned when:

- Every persona block contains exactly 5 queries.
- The query-type distribution includes semantic, entity, tabular, aggregate, and complex coverage.
- Every query traces to a real production corpus family.
- The markdown matches the JSON IDs, query text, and type assignments exactly.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-11 MDT
