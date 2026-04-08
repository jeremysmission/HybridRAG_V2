# Golden Eval Traceability Report

**Date:** 2026-04-08 MDT
**Author:** Jeremy Randall (CoPilot+)

---

## Golden Eval Source Files

The 25 original golden eval queries (GQ-001 through GQ-025) trace to 5 curated test documents:

| File | Path | Content | Queries Served |
|------|------|---------|---------------|
| maintenance_report_sample.txt | data/source/ | Thule + Riverside site visit reports | GQ-001 through GQ-010 |
| email_chain_messy.txt | data/source/ | RE:RE:RE email chain with CH3 noise workaround | GQ-018 |
| spreadsheet_fragment.txt | data/source/ | PO tracking spreadsheet (tabular data) | GQ-011, GQ-014, GQ-020 |
| test_document.txt | data/source/ | General maintenance summary | GQ-022, GQ-024 |
| messy_desktop_log.txt | data/source/ | Desktop log with mixed content | GQ-019 |

These 5 files are the primary fact sources. The remaining golden queries (GQ-012, GQ-013, GQ-015, GQ-016, GQ-017, GQ-021, GQ-023) use facts that appear across multiple files or in the entity store.

## role_corpus_golden (14 files)

The `data/source/role_corpus_golden/` directory contains 14 curated files covering all 3 personas:

| Persona | Files |
|---------|-------|
| Program Manager | PM_Milestone_Plan.docx, PM_Risk_Register.pdf |
| Logistics | Logistics_Spare_Parts.xlsx, Logistics_Shipping_Constraints.txt |
| Field Engineer | Field_Deployment_Guide.docx, Field_Troubleshooting.pdf, Engineer_Calibration_Guide.pdf, Engineer_System_Spec.docx |
| Supporting | CAD_Revision_History.pptx, CAD_Tolerance_Spec.docx, Cyber_Incident_Response.pdf, Cyber_Vulnerability_Report.docx, SysAdmin_Access_Matrix.json, SysAdmin_Network_Config.docx |

These files are NOT the source for golden eval queries. They are persona-coverage test data for format parsing and corpus diversity testing. They are chunked and indexed in LanceDB (part of the 17,707-chunk store) but golden eval facts don't trace to them.

## Traceability Gap

**Finding:** Golden eval queries do not trace to the `role_corpus_golden/` files. This is by design -- the golden queries were authored against the 5 simpler test documents that contain the IGS maintenance scenario facts (Thule, Riverside, Cedar Ridge sites, specific parts, POs, contacts).

**Action:** No change needed for demo. The golden eval proves the query pipeline works. The role_corpus_golden files prove format diversity. Both are valid testing vectors but serve different purposes.

**Future:** When Forge S5 delivers the full corpus, new golden queries should be authored against real production documents, not synthetic test files.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
