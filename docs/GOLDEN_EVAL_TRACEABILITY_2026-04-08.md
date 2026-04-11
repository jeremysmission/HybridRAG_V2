# Golden Eval Traceability Report

**Date:** 2026-04-11 MDT
**Author:** Jeremy Randall (CoPilot+)
**Scope:** `tests/golden_eval/production_queries_2026-04-11.json`

---

## Purpose

This query pack is organized around the 5 real demo personas, not topic buckets. Each block contains 5 queries and maps to one user role that will actually exercise the system during the demo.

The pack is grounded in real production corpus families and identifiers from the HybridRAG V2 production import. The goal is traceability from demo user intent to corpus families, not synthetic fixture coverage.

---

## Persona Coverage

| Persona | Query IDs | Primary Intent |
|---------|-----------|----------------|
| Program Manager | PQ-001 through PQ-005 | Contract status, CDRL deliverables, schedule milestones, cost tracking, staffing/TO status |
| Logistics Lead | PQ-006 through PQ-010 | Parts inventory, PO tracking, shipment status, calibration schedules, EEMS records |
| Field Engineer | PQ-011 through PQ-015 | Repair procedures, failure modes, equipment manuals, site visit reports, maintenance actions |
| Network Admin / Cybersecurity | PQ-016 through PQ-020 | ACAS scan results, STIG checklists, RMF package status, POA&M tracking, network configuration docs |
| Aggregation / Cross-role | PQ-021 through PQ-025 | Cross-family questions that require combining results across multiple document families |

---

## Query Block Mapping

### Program Manager

- `PQ-001` traces to follow-on contract planning, Sources Sought, and RFI materials.
- `PQ-002` traces to the CDRL tree and deliverable status folders.
- `PQ-003` traces to PMR schedule-performance and milestone briefing materials.
- `PQ-004` traces to FEP, ITD Actuals, and CEAC financial artifacts.
- `PQ-005` traces to PMR status briefs and suborganization slides that capture staffing or task-order context.

### Logistics Lead

- `PQ-006` traces to procurement spreadsheets with open purchase order and vendor fields.
- `PQ-007` traces to the spares inventory workbook and related parts references.
- `PQ-008` traces to shipment, hand-carry, and packing-list documents for OCONUS movement.
- `PQ-009` traces to yearly calibration folders and the calibration reference PDF.
- `PQ-010` traces to EEMS, jurisdiction, classification, and JCR material.

### Field Engineer

- `PQ-011` traces to Thule installation documents and site engineering artifacts.
- `PQ-012` traces to site outage analysis and root-cause writeups.
- `PQ-013` traces to COTS manuals and hardware maintenance references.
- `PQ-014` traces to Guam and Alpena site visit reports and site-selection records.
- `PQ-015` traces to the Part Failure Tracker and related maintenance records.

### Network Admin / Cybersecurity

- `PQ-016` traces to ACAS scan artifacts and scan guidance references.
- `PQ-017` traces to the STIG review spreadsheet and waiver or finding records.
- `PQ-018` traces to ATO and RMF package-change artifacts.
- `PQ-019` traces to the IAVM tracker and POA&M-style remediation status.
- `PQ-020` traces to the monitoring system authorization boundary PDF and network diagram folder.

### Aggregation / Cross-role

- `PQ-021` requires consolidation across procurement and site folders to count open POs and recurring vendors.
- `PQ-022` spans PM, logistics, and engineering deliverables due in the same quarter.
- `PQ-023` spans outage history across site visits and maintenance records.
- `PQ-024` joins site visit records with shipments, calibration actions, and deliverables.
- `PQ-025` correlates failures, part replacements, and corrective actions across time and across document families.

---

## Traceability Notes

The query pack keeps the same JSON field structure as the previous pack:

- `id`
- `query`
- `expected_facts`
- `expected_confidence`
- `query_type`
- `persona`
- `document_family`
- `production_rationale`

The only structural change is the intentional reorganization around the 5 demo personas. That change is required so QA can validate the pack against the actual people who will demo the system, rather than against topic buckets.

---

## Acceptance Rule

The pack is considered aligned when:

- Every persona block contains exactly 5 queries.
- Each query maps to a real production corpus family.
- Aggregation queries require evidence across more than one family.
- The rationale document explains the persona mapping without relying on synthetic fixtures.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-11 MDT
