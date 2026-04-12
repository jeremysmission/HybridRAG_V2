# Canary Injection Methodology — Aggregation Validation Design

**Author:** Task #18 analysis reviewer  
**Repo:** `C:\HybridRAG_V2`  
**Task:** #18  
**Scope:** Design-only methodology for canary-backed aggregation validation in V2  
**Status:** No code, no corpus edits, no store writes in this task

---

## Executive Summary

V2 should adopt a **transparent, isolated, deterministic canary pack** for aggregation validation, but it should not pretend that canaries alone make polluted corpus-wide counts trustworthy. The right design is a **frozen real baseline + deterministic canary delta + three narrow real-scoped manual counts**, with the audience told explicitly that two demo questions are validation controls and three are real-data checks. The canary namespace, folder layout, verification path, and pre-demo script all need to be deterministic and auditable so Task #18 becomes a repeatable proof mechanism, not a one-off demo trick.

---

## Why This Exists

V1 died on aggregation credibility. V2 already has strong evidence for large-corpus retrieval, but the current overnight state still rates aggregation honesty as RED because:

- `PART` and `PO` are still polluted in the live Tier 1 store.
- relationships are still sparse.
- retrieval success can hide structured-answer weakness.

This methodology is the design answer to the user’s explicit requirement:

> We need verifiable aggregation answers, or we need to drop canaries in to validate aggregation.

The design goal is not “make the demo look good.” The design goal is:

1. prove the aggregation path with known answers,
2. prove that demo claims are defensible,
3. separate synthetic validation from real-data claims cleanly,
4. give a future implementer a spec that can be built without redesign.

---

## Read-Only Local Foundation

These current V2 facts shaped the design:

- [V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md](./V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md) rated aggregation credibility **RED** because current entity-backed counts are not yet trustworthy.
- [CRASH_RECOVERY_2026-04-12.md](./CRASH_RECOVERY_2026-04-12.md) records the live Tier 1 store at **8,017,607 entities**, with `PART` roughly **90% polluted** and `PO` roughly **98% polluted**.
- [PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md](./PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md) documents entity contamination and already uses a RAGAS-compatible, anchor-mined query schema worth reusing for canary queries.
- `src/store/lance_store.py::verify_ingest_completeness()` provides a cheap and explicit ingest-integrity check, which is necessary but not sufficient for canary truth.
- `scripts/mine_query_anchors.py` already embodies the project’s preferred pattern: real or synthetic queries should be grounded to inspectable anchors, not invented loosely.

### Local Collision Check That Changed The Design

The sample brief suggested `CAN-*` style IDs. I checked the live read-only entity store before locking the namespace.

Observed on `entities.sqlite3`:

- `CAN-%` is **not** clean.
- Existing `PART` entities include real tokens such as `CAN-2005`, `CAN-2004`, `CAN-1210`, `CAN-1209`, and `CAN-1208`.
- Safer extractor-compatible identifiers with **zero current collisions** in the live read-only store include:
  - exact labeled SAP-style PO values `9001000001` through `9001000012`
  - `QZ-%` part identifiers
  - exact site names `Validation Alpha Site` through `Validation Echo Site` when emitted through `Site:` or `Location:` labels
  - `VALCAN*` for document IDs, filenames, and visible markers

**Decision:** do **not** use `CAN-*` as the main synthetic entity namespace. Also do **not** assume a collision-clean namespace is automatically extractor-compatible. In the authored pack, `VALCAN` remains the document-level namespace, while primary `PO` / `PART` / `SITE` values are shaped to match the current Tier 1 extractor.

---

## Research Foundation

This section records the external research that supports the methodology choices.

### Finding R1 — Known ground-truth context matters more than synthetic volume

Red Hat’s 2026 RAG evaluation guidance recommends grounded synthetic data where the **ground-truth context is known** before running downstream evaluation. That aligns directly with the canary design here: every canary record must be authored with a pre-known answer and supporting context, not inferred after the fact.

Source note: Used Red Hat Developer synthetic-data RAG evaluation article `https://developers.redhat.com/articles/2026/02/23/synthetic-data-rag-evaluation-why-your-rag-system-needs-better-testing` via cached lines noting that known ground-truth context enables true retrieval and generation evaluation, not proxy judgment (checked 2026-04-12).

### Finding R2 — Separate retrieval evaluation from answer evaluation

Haystack’s evaluation guidance still recommends separating the pipeline under test from the evaluation pipeline so results can be stored and scored independently. For V2, that implies the canary validator should not depend only on the natural-language answer string; it should also check support evidence and deterministic SQL-side counts.

Source note: Used Haystack statistical evaluation guidance `https://docs.haystack.deepset.ai/v2.3/docs/statistical-evaluation` on comparing predictions against ground truth labels and separating evaluation from production runs (checked 2026-04-12).

### Finding R3 — Persona + query-style coverage is the right generation pattern

RAGAS’s current test-generation guidance still frames synthetic set creation around document nodes, personas, and query styles. That supports making the canary pack multi-persona and multi-difficulty rather than a single flat spreadsheet of easy count questions.

Source note: Used RAGAS custom single-hop and knowledge-graph test generation guidance `https://docs.ragas.io/en/v0.2.7/howtos/customizations/testgenerator/_testgen-custom-single-hop/` on combining node, persona, query style, and query length (checked 2026-04-12).

### Finding R4 — Difficulty should be explicit, not implicit

LiveRAG’s 2025 benchmark release explicitly tracks **difficulty** and supporting claims for synthetic RAG questions. That supports the design decision to label canary queries as easy, medium, or hard and to keep the hard ones in rehearsal even if only the easier two make it into the live demo.

Source note: Used LiveRAG benchmark paper `https://arxiv.org/abs/2511.14531` on synthetic questions with ground-truth answers, supporting claims, and estimated difficulty/discriminability (checked 2026-04-12).

### Finding R5 — Synthetic enterprise benchmarks need realistic structure and answerability boundaries

The enterprise and heterogeneous-document benchmarking work reviewed for this task emphasizes realistic source structure, mixed text/table corpora, and explicit evaluation rather than intuition. V2’s canary pack should therefore look like real `.xlsx`, `.docx`, `.pdf`, and `.txt` artifacts, but it must remain visibly synthetic and isolated.

Source note: Used current text-and-table retrieval benchmark `https://arxiv.org/abs/2604.01733` emphasizing heterogeneous documents and explicit retrieval/generation evaluation (checked 2026-04-12).

### Finding R6 — A single poisoned text can meaningfully affect a RAG system

Recent RAG poisoning research shows that even a **single poisoned text** can compromise outcomes under realistic conditions. That is the strongest research argument for keeping canaries in an isolated namespace and making inclusion/exclusion explicit rather than hidden.

Source note: Used `Practical Poisoning Attacks against Retrieval-Augmented Generation` `https://arxiv.org/abs/2504.03957`, which reports practical attacks where a single injected text can have high impact (checked 2026-04-12).

### Finding R7 — Public-sector trust argues for transparent disclosure, not sleight of hand

The GPAI/OECD algorithmic-transparency report frames transparency as enabling monitoring, testing, critique, evaluation, trust, and accountability. For a procurement-sensitive or government audience, that leans toward **telling the truth about validation controls** rather than quietly blending canaries into the corpus.

Source note: Used GPAI/OECD transparency report `https://wp.oecd.ai/app/uploads/2025/05/algorithmic-transparency-in-the-public-sector.pdf` on transparency as a capacity to obtain information, monitor, test, critique, and evaluate systems to foster trust and accountability (checked 2026-04-12).

### Finding R8 — Agency-defined evaluation data and portability matter in government AI

The White House procurement memo keeps pointing agencies toward independent evaluation, portability, and avoiding hidden lock-in. A canary pack that lives in repo, is reproducible, and is disclosed as a validation control fits that logic better than an undocumented demo-only trick.

Source note: Used White House M-25-22 `https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf` on evaluation, portability, and explicit acquisition controls (checked 2026-04-12).

### Finding R9 — Enterprise demos should use fixed known-good modules and rehearsed fallback

The overnight demo-pattern research already established that enterprise demos should be modular, canary-driven, and failure-rehearsed. That means the canary queries belong in the live demo only if they are:

- independently proven ahead of time,
- clearly narrated,
- paired with fallback language.

Source note: Reused the approved demo research memo [DEMO_DAY_RESEARCH_2026-04-12.md](./DEMO_DAY_RESEARCH_2026-04-12.md), which cites Great Demo, Guideflow, Storylane, OECD, GSA, Microsoft, and AWS sources (checked 2026-04-12).

---

## Design Principles

The methodology below follows seven principles.

### Principle 1 — Isolate synthetic validation from the real corpus

Canaries must live under a dedicated subtree and namespace. No silent blend-in.

### Principle 2 — Make the synthetic namespace collision-resistant

The namespace must be checked against the live store before finalization. `CAN-*` is rejected because it already collides.

### Principle 3 — Make every canary answer hand-authored before injection

The correct answer must be known at author time, not inferred from model output.

### Principle 4 — Use deterministic document generation

The same seed must produce the same files, same field values, same counts, and, as far as possible, stable chunk layout.

### Principle 5 — Pair synthetic canary proof with narrow real-data proof

Canaries prove the aggregation path. Narrow real-scoped counts prove the demo is not only synthetic.

### Principle 6 — Freeze real baselines before claiming corpus-wide totals

Canaries do not magically make a polluted real baseline trustworthy. Corpus-wide claims require a frozen verified real baseline plus a known synthetic delta.

### Principle 7 — Validate through both the query pipeline and independent store checks

The query pipeline proves operator-visible behavior. Independent SQL/Lance checks prove the data landed correctly.

---

## Recommended Namespace And Folder Layout

### Recommended root

```
E:\CorpusTransfr\verified\IGS\_VALCAN_2026\
```

### Recommended internal layout

```
_VALCAN_2026\
  00_README\
  10_PROGRAM_MANAGEMENT\
  20_LOGISTICS\
  30_FIELD_ENGINEERING\
  40_CYBERSECURITY\
  50_CROSS_ROLE\
```

### Required visible marker inside every document

```
[CANARY-VALIDATION-DOCUMENT-DO-NOT-USE-IN-PRODUCTION]
```

### Required metadata block inside every document

Every canary file should begin with a small deterministic metadata block:

```text
[CANARY-VALIDATION-DOCUMENT-DO-NOT-USE-IN-PRODUCTION]
Canary Namespace: VALCAN-2026
Canary Document ID: VALDOC-###
Canary Bundle: <persona bundle>
Synthetic Owner: Jane Canary
Production Use: prohibited
```

### Required filename convention

Include `valcanary` in every filename so operators can isolate the pack with simple path or glob filters. In the authoritative Forge repo at `C:\CorpusForge`, the active nightly-delta path already includes `nightly_delta.canary_globs` with a broad `*canary*` pattern, so `valcanary_*` would be surfaced by that nightly-delta scan path today. This is config-grounded coverage through the existing broad glob, not a dedicated explicit `valcanary_*` rule.

Example:

```text
valcanary_po_register_q2_2024.xlsx
valcanary_msr_alpha_2024_03_12.docx
valcanary_acas_rollup_q3_2024.pdf
```

### Why this path and naming

- leading underscore keeps the subtree visually separate,
- `valcanary` is both a human-readable operator filter token and a match for the current authoritative nightly-delta broad glob `*canary*`,
- extractor-compatible `PO` / `PART` / `SITE` values are clean in the live store,
- the visible marker gives operators a searchable proof handle.

---

## The Canary Fact Model

The canary pack should encode one fixed synthetic world. The documents differ by format and viewpoint, but they all refer to the same controlled facts.

### Core entities

#### Sites

| Code | Meaning |
|---|---|
| `Validation Alpha Site` | synthetic site 1 |
| `Validation Bravo Site` | synthetic site 2 |
| `Validation Charlie Site` | synthetic site 3 |
| `Validation Delta Site` | synthetic site 4 |
| `Validation Echo Site` | synthetic site 5 |

#### People

| Name | Role |
|---|---|
| Jane Canary | Program Manager |
| Morgan Ledger | Contracts / cost tracking |
| John Testsubject | Logistics lead |
| Pat Validation | Field engineer |
| Riley Audit | Cybersecurity lead |

#### Contracts

| ID | Role |
|---|---|
| `VALCON-2024-0001` | sustainment / PM / logistics umbrella contract |
| `VALCON-2024-0002` | cybersecurity support and remediation |

#### Purchase orders

Twelve synthetic POs:

| ID | Status | Site | Quarter | Value |
|---|---|---|---|---:|
| `PO 9001000001` | OPEN | Validation Alpha Site | Q1 2024 | 18,400 |
| `PO 9001000002` | OPEN | Validation Bravo Site | Q2 2024 | 72,000 |
| `PO 9001000003` | CLOSED | Validation Alpha Site | Q2 2024 | 15,300 |
| `PO 9001000004` | OPEN | Validation Charlie Site | Q2 2024 | 58,700 |
| `PO 9001000005` | CLOSED | Validation Delta Site | Q2 2024 | 8,900 |
| `PO 9001000006` | OPEN | Validation Echo Site | Q3 2024 | 44,500 |
| `PO 9001000007` | OPEN | Validation Bravo Site | Q3 2024 | 63,000 |
| `PO 9001000008` | CLOSED | Validation Charlie Site | Q2 2024 | 91,000 |
| `PO 9001000009` | OPEN | Validation Alpha Site | Q4 2024 | 109,000 |
| `PO 9001000010` | CLOSED | Validation Echo Site | Q1 2024 | 12,600 |
| `PO 9001000011` | OPEN | Validation Delta Site | Q4 2024 | 32,200 |
| `PO 9001000012` | OPEN | Validation Charlie Site | Q2 2024 | 27,800 |

Deterministic canary facts from that table:

- total validation POs = **12**
- open validation POs = **8**
- closed validation POs = **4**
- Q2 2024 validation POs over $50,000 = **3** (`0002`, `0004`, `0008`)
- total open validation PO value = **$425,600**

#### Part numbers

Sixteen synthetic parts:

| ID | Short label |
|---|---|
| `QZ-3001` | coax assembly |
| `QZ-3002` | low-loss coax |
| `QZ-3003` | UPS module |
| `QZ-3004` | GPS antenna |
| `QZ-3005` | KVM switch |
| `QZ-3006` | cooling fan |
| `QZ-3007` | battery unit |
| `QZ-3008` | power supply |
| `QZ-3009` | surge filter |
| `QZ-3010` | patch cable |
| `QZ-3011` | pre-amplifier |
| `QZ-3012` | RF coupler |
| `QZ-3013` | network card |
| `QZ-3014` | optical transceiver |
| `QZ-3015` | UPS management card |
| `QZ-3016` | edge router |

#### Service events

Eleven validation service events:

- four lightning-related events in 2024,
- three power-quality events,
- two routine maintenance visits,
- one calibration-only visit,
- one network remediation event.

Hard-query deterministic facts:

- lightning-related service events in 2024 = **4**
- distinct parts failed during those lightning events = **5**
- sites affected by those lightning events = **3**
- affected parts =  
  `QZ-3003`  
  `QZ-3004`  
  `QZ-3006`  
  `QZ-3009`  
  `QZ-3015`

#### Program-management deliverables

Twelve validation deliverables exist in the status register. Four are late:

- `VAL-A009-MSR-Q4`
- `VAL-A031-IMS-REV-B`
- `VAL-A055-INVENTORY-ROLLUP`
- `VAL-A027-POAM-UPDATE-Q4`

#### Cyber findings

Validation cybersecurity facts:

- ACAS findings total = **26**
- open ACAS findings = **11**
- Critical/High findings = **7**
- STIG checklist items tracked = **18**
- open STIG items = **6**
- POA&M open items = **4**
- overdue POA&M items = **2**
- named directives in the synthetic directive pack = **5**

#### Calibration facts

- calibration records in synthetic pack = **8**
- completed calibrations = **5**
- overdue calibrations = **3**

#### Shipment facts

- shipments total = **9**
- shipments to `Validation Alpha Site` = **4**
- OCONUS shipments requiring customs/export packet = **3**

---

## Canary Corpus Specification — 40 Documents

The pack should contain exactly **40 files**. That is big enough to cover all five personas and difficulty tiers, but small enough to inspect manually.

### 00_README bundle

| Doc ID | Filename | Format | Purpose | Key facts |
|---|---|---|---|---|
| VALDOC-001 | `valcanary_README.txt` | `.txt` | human-readable explanation and visible canary marker | namespace, purpose, warning |
| VALDOC-002 | `valcanary_ground_truth_index.xlsx` | `.xlsx` | machine-readable fact index for implementation and rehearsal | all expected totals, query IDs, evidence IDs |
| VALDOC-003 | `valcanary_source_manifest.txt` | `.txt` | deterministic source manifest for generated files | list of 40 docs, bundle names, hashes after generation |

### 10_PROGRAM_MANAGEMENT bundle

| Doc ID | Filename | Format | Purpose | Key facts |
|---|---|---|---|---|
| VALDOC-004 | `valcanary_contract_master_2024.pdf` | `.pdf` | contract summary for PM framing | 2 contracts, 5 sites, 12 deliverables |
| VALDOC-005 | `valcanary_cdrl_status_register_q4_2024.xlsx` | `.xlsx` | canonical PM status table | 12 deliverables, 4 late |
| VALDOC-006 | `valcanary_integrated_master_schedule_q4_2024.xlsx` | `.xlsx` | schedule milestones and slips | 8 milestones, 3 slipped |
| VALDOC-007 | `valcanary_pmr_brief_q4_2024.docx` | `.docx` | PM narrative briefing | references late deliverables and cost variance |
| VALDOC-008 | `valcanary_weekly_variance_report_2024w40.txt` | `.txt` | simple text artifact for date-based retrieval | cost variance and staffing pressure |
| VALDOC-009 | `valcanary_budget_rollup_fy2024.xlsx` | `.xlsx` | PM cost roll-up | budget plan vs actuals |
| VALDOC-010 | `valcanary_contract_risk_register_q4_2024.xlsx` | `.xlsx` | risk register | schedule risk, staffing risk, late deliverables |
| VALDOC-011 | `valcanary_cdrl_a009_delivery_memo.docx` | `.docx` | document-level proof for one late CDRL | `VAL-A009-MSR-Q4` late |

### 20_LOGISTICS bundle

| Doc ID | Filename | Format | Purpose | Key facts |
|---|---|---|---|---|
| VALDOC-012 | `valcanary_po_register_2024.xlsx` | `.xlsx` | canonical PO table | 12 POs, 8 open, open total $425,600 |
| VALDOC-013 | `valcanary_po_receipts_2024.xlsx` | `.xlsx` | receipt confirmation view | 4 closed POs received |
| VALDOC-014 | `valcanary_parts_master_list.xlsx` | `.xlsx` | master parts list | 16 unique part numbers |
| VALDOC-015 | `valcanary_shipment_manifest_q1_q2_2024.xlsx` | `.xlsx` | shipment counts by site and date | 9 shipments, 4 to ALPHA |
| VALDOC-016 | `valcanary_customs_export_packet_alpha_bravo.pdf` | `.pdf` | customs/export paperwork proof | 3 OCONUS customs-linked shipments |
| VALDOC-017 | `valcanary_calibration_due_register_2024.xlsx` | `.xlsx` | calibration aggregation | 8 records, 3 overdue |
| VALDOC-018 | `valcanary_calibration_completion_report_2024.docx` | `.docx` | narrative calibration summary | 5 completed calibrations |
| VALDOC-019 | `valcanary_vendor_quote_summary_q2_2024.pdf` | `.pdf` | medium-difficulty procurement cross-check | high-value Q2 POs |
| VALDOC-020 | `valcanary_receiving_exception_log.txt` | `.txt` | text-only mismatch artifact | references delayed shipments and one open PO |
| VALDOC-021 | `valcanary_oconus_shipment_crosswalk.xlsx` | `.xlsx` | shipment-to-PO linkage | ties 3 export-controlled shipments to POs |

### 30_FIELD_ENGINEERING bundle

| Doc ID | Filename | Format | Purpose | Key facts |
|---|---|---|---|---|
| VALDOC-022 | `valcanary_service_event_tracker_2024.xlsx` | `.xlsx` | canonical field-event table | 11 service events, 4 lightning-related |
| VALDOC-023 | `valcanary_msr_alpha_2024_03_12.docx` | `.docx` | site-specific MSR | lightning event, replaced parts |
| VALDOC-024 | `valcanary_msr_bravo_2024_05_18.docx` | `.docx` | site-specific MSR | lightning event, site BRAVO |
| VALDOC-025 | `valcanary_msr_charlie_2024_06_30.docx` | `.docx` | site-specific MSR | lightning event, site CHARLIE |
| VALDOC-026 | `valcanary_msr_delta_2024_08_22.docx` | `.docx` | site-specific MSR | non-lightning maintenance |
| VALDOC-027 | `valcanary_failure_mode_summary_2024.pdf` | `.pdf` | fault-mode aggregation | 5 distinct parts failed during lightning events |
| VALDOC-028 | `valcanary_corrective_action_crosswalk.xlsx` | `.xlsx` | event-to-part-to-CAP linkage | ties failures to service events and parts |
| VALDOC-029 | `valcanary_site_visit_rollup_2024.txt` | `.txt` | site visit aggregation text | references all five sites and visit counts |

### 40_CYBERSECURITY bundle

| Doc ID | Filename | Format | Purpose | Key facts |
|---|---|---|---|---|
| VALDOC-030 | `valcanary_acas_rollup_q2_2024_alpha.pdf` | `.pdf` | ACAS scan summary | ACAS findings for ALPHA |
| VALDOC-031 | `valcanary_acas_rollup_q3_2024_bravo.pdf` | `.pdf` | ACAS scan summary | ACAS findings for BRAVO |
| VALDOC-032 | `valcanary_stig_checklist_rollup_2024.xlsx` | `.xlsx` | STIG aggregation | 18 items, 6 open |
| VALDOC-033 | `valcanary_poam_register_q4_2024.xlsx` | `.xlsx` | POA&M aggregation | 4 open, 2 overdue |
| VALDOC-034 | `valcanary_monthly_cyber_audit_summary_2024.docx` | `.docx` | narrative cyber summary | links ACAS, STIG, POA&M |
| VALDOC-035 | `valcanary_vulnerability_exception_memo.pdf` | `.pdf` | exception handling artifact | references overdue POA&M items |
| VALDOC-036 | `valcanary_baseline_inventory_for_scans.xlsx` | `.xlsx` | scan target inventory | asset/site mapping for cyber scans |
| VALDOC-037 | `valcanary_named_directives_reference.txt` | `.txt` | fixed directive set | 5 named directives |

### 50_CROSS_ROLE bundle

| Doc ID | Filename | Format | Purpose | Key facts |
|---|---|---|---|---|
| VALDOC-038 | `valcanary_site_registry.xlsx` | `.xlsx` | site identity crosswalk | 5 sites, owning teams, system types |
| VALDOC-039 | `valcanary_part_failure_to_po_crosswalk.xlsx` | `.xlsx` | joins parts, events, and POs | enables hard aggregation query |
| VALDOC-040 | `valcanary_readiness_dashboard_q4_2024.pdf` | `.pdf` | executive roll-up for cross-role queries | summarizes PM, logistics, field, and cyber metrics |

### Format mix

The 40 documents intentionally cover the formats most relevant to current V2 ingest patterns:

- `.xlsx`: 18
- `.docx`: 8
- `.pdf`: 8
- `.txt`: 6

This is close enough to the real corpus shape to test parse, chunk, embed, and retrieval behavior without recreating production noise.

---

## Difficulty Tiers

Every canary query should be tagged by difficulty.

### Easy

Single-attribute counts or lists against one dominant document family.

Examples:

- “How many shipments were sent to `Validation Alpha Site`?”
- “How many calibration records are overdue?”

### Medium

Two-attribute filters or cross-document confirmations.

Examples:

- “List all validation POs over $50,000 issued in Q2 2024.”
- “How many open POA&M items are overdue?”

### Hard

Three-attribute or cross-role counts that require linking multiple documents.

Examples:

- “How many distinct parts failed during lightning strikes in 2024?”
- “Which validation sites had both late deliverables and open POA&M items?”

### Why this matters

The live demo should only use a subset of the canary pack. The full validation script should run all easy, medium, and hard scenarios before rehearsal.

---

## The Five Demo Queries

The demo strategy decided earlier in the session was:

- 2 canary-backed aggregation queries
- 3 real-scoped aggregation queries
- every answer defensible

This methodology adopts that structure, with one important correction:

> The two canary-backed live queries should be **canary-only** in the live demo unless a frozen verified real baseline exists.  
> If the team later wants “real corpus + canary delta” totals, it must freeze the real baseline before the rehearsal and publish the arithmetic.

### Query 1 — Canary-backed logistics proof

| Field | Specification |
|---|---|
| Query text | `How many open validation purchase orders exist across all validation sites, and what is their total value?` |
| Persona | Logistics Lead |
| Difficulty | Easy |
| Expected query_type | `AGGREGATE` |
| Expected answer | `8 open validation POs totaling $425,600.` |
| Ground-truth source | Synthetic canary fact table; primary evidence in `valcanary_po_register_2024.xlsx` plus `valcanary_po_receipts_2024.xlsx`. |
| V2 query path | Router should classify `AGGREGATE`; primary answer path should be entity-store aggregation over `PO` plus status/value fields, with vector context merged by `pipeline._handle_structured()`. |
| Demo narration suggestion | `This first question is a validation control. We injected a small synthetic procurement pack with pre-known counts so we can prove the aggregation path is doing arithmetic, not improv.` |
| Failure recovery plan | If the answer is wrong, switch immediately to the validation table slide or proof artifact showing the 12 POs and 8 open statuses, state that the pipeline failed the control, and do not continue with corpus-wide aggregation claims. |

### Query 2 — Canary-backed cross-role hard proof

| Field | Specification |
|---|---|
| Query text | `How many distinct validation part numbers failed during lightning-related service events in 2024, and at which validation sites did those failures occur?` |
| Persona | Aggregation / Cross-role |
| Difficulty | Hard |
| Expected query_type | `AGGREGATE` |
| Expected answer | `5 distinct parts failed during 4 lightning-related service events across 3 validation sites: Validation Alpha Site, Validation Bravo Site, and Validation Charlie Site.` |
| Ground-truth source | Synthetic canary fact table; evidence in `valcanary_service_event_tracker_2024.xlsx`, `valcanary_failure_mode_summary_2024.pdf`, and `valcanary_part_failure_to_po_crosswalk.xlsx`. |
| V2 query path | Router should classify `AGGREGATE`; answer should come from entity-store aggregation and/or table query with vector context merged. Future implementation may need a specific aggregate helper if generic aggregation does not link events to failure modes cleanly. |
| Demo narration suggestion | `This is the harder control. It crosses date, failure mode, and distinct-part counting. If the system gets this right, we know the structured path is handling more than a single spreadsheet total.` |
| Failure recovery plan | Fall back to the crosswalk worksheet and enumerate the 4 lightning events and 5 parts manually. Narration: `This is why we run validation controls first: when a hard aggregate misses, we show the evidence and keep the trust boundary intact.` |

### Query 3 — Real-scoped PM proof

| Field | Specification |
|---|---|
| Query text | `How many monthly actuals workbooks are filed in the 2024 FEP reference set?` |
| Persona | Program Manager |
| Difficulty | Easy |
| Expected query_type | `AGGREGATE` |
| Expected answer | `12 workbooks.` |
| Ground-truth source | Manual count against the narrow real subtree `10.0 Program Management/1.0 FEP/Reference/2024 NN Monthly Actuals.xlsx`; design-time expectation is one workbook per month. |
| V2 query path | Router should classify `AGGREGATE`; answer may come from vector retrieval plus structured count if future metadata promotes file-level counts cleanly. |
| Demo narration suggestion | `This is a real-data count, but it is intentionally narrow. We picked a one-year subtree where a human can verify the answer before rehearsal.` |
| Failure recovery plan | If V2 misses, show the frozen manual evidence list of the 12 monthly files and frame the miss as a retrieval/aggregation issue in a narrow verified lane, then move on. |

### Query 4 — Real-scoped field-engineering proof

| Field | Specification |
|---|---|
| Query text | `How many site-specific Maintenance Service Report folders are filed under A002?` |
| Persona | Field Engineer |
| Difficulty | Easy |
| Expected query_type | `AGGREGATE` |
| Expected answer | `21 site-specific MSR folders.` |
| Ground-truth source | Real corpus folder structure already documented in `PQ-103` rationale and reference context for the A002 CDRL subtree. |
| V2 query path | Router should classify `AGGREGATE`; answer can be satisfied via retrieval over the A002 folder family and later strengthened by metadata or file-count indexing. |
| Demo narration suggestion | `This is a real structured count over a single deliverable family, not a synthetic control. The point is that we can prove one real aggregation lane without claiming the whole corpus is clean yet.` |
| Failure recovery plan | Show the A002 folder list used in manual ground truth and state that the real-data proof lane stays narrow by design. |

### Query 5 — Real-scoped cyber proof

| Field | Specification |
|---|---|
| Query text | `How many named cybersecurity directives are in the current directive reference set?` |
| Persona | Network Admin / Cybersecurity |
| Difficulty | Easy |
| Expected query_type | `AGGREGATE` |
| Expected answer | `5 named directives.` |
| Ground-truth source | Manual count on the narrow directive reference set already identified in the production-eval rationale: Apache Log4j, Samba Wanna-Cry, SPARTAN VIPER VMware, PKI, and VPN Laptop directives. |
| V2 query path | Router should classify `AGGREGATE`; vector retrieval may currently be the dominant proof path, with explicit file-list evidence backing the count. |
| Demo narration suggestion | `This is the same pattern as the PM example: a real, bounded aggregation question with a human-verified answer.` |
| Failure recovery plan | Show the frozen directive list and explain that this query was intentionally chosen because the answer can be manually audited from a small real subset. |

### Important note on “corpus-wide” claims

If the coordinator insists on live totals like:

- `How many purchase orders exist in the corpus?`
- `How many unique part numbers exist across all sites?`

then the live answer must be expressed as:

```text
frozen_real_baseline + deterministic_canary_delta
```

Example:

```text
Open POs in demo corpus = B_PO_OPEN + 7
```

Where:

- `B_PO_OPEN` is the frozen manually verified real baseline captured in a pre-demo evidence packet after regex cleanup,
- `7` is the deterministic canary delta from the validation pack.

Until that baseline is frozen, do **not** present a whole-corpus total as “provable” just because canaries exist.

---

## Disclosure Strategy Recommendation

### Recommendation: Option A — Transparent disclosure

Tell the audience, briefly and plainly:

> `We injected a small validation pack with known answers so we can prove the aggregation path before we show real scoped counts. Two questions are validation controls; the next three are real-data checks.`

### Why transparent disclosure is the better choice

1. **Public-sector trust dynamics favor testability and accountability.**  
   The transparency literature used in the overnight memo explicitly links transparency with the ability to monitor, test, critique, and evaluate systems to foster trust and accountability.

2. **The audience is procurement-sensitive, not benchmark-naive.**  
   A hidden synthetic pack is more likely to be interpreted as sleight of hand if discovered.

3. **The mixed structure is already honest and strong.**  
   Two synthetic controls prove arithmetic. Three real-scoped queries prove the team is not hiding behind synthetic data.

4. **Transparent controls fit the enterprise demo pattern better than “ask me anything.”**  
   The current demo research already concluded that modular known-good controls beat improvisation.

Source note: Used the approved demo research memo plus GPAI/OECD transparency research and White House M-25-22 procurement framing (checked 2026-04-12).

### How to phrase it on stage

Recommended phrasing:

`Before we make any corpus-wide aggregation claim, we run two validation controls. They use synthetic records with known answers so we can prove the count path. Then we switch to three real-data counts that were manually verified in narrow subtrees.`

### What not to say

- `These are fake demo records.`
- `We hid some test documents in the corpus.`
- `Trust us, they don’t matter.`

### Why Option B is rejected

Visual blend-in raises the risk of:

- looking deceptive if discovered,
- contaminating production-style imports accidentally,
- making debugging harder,
- undermining the exact trust story the user is trying to preserve after V1.

---

## Injection Workflow

This workflow is designed to fit the current V2 + CorpusForge architecture with minimal new concepts.

### Step 0 — Freeze the real baseline

This is mandatory before any “real corpus + canary delta” claim.

Inputs:

- cleaned real entity store after Task #16
- frozen query pack
- manual evidence for the three real-scoped queries

Output:

- `canary_baseline_evidence_YYYYMMDD.md`
- a small table of baseline real counts to be used in live arithmetic, if any corpus-wide totals are shown

### Step 1 — Generate the canary files deterministically

A future script, not implemented here, writes the 40 files into:

```
E:\CorpusTransfr\verified\IGS\_VALCAN_2026\
```

### Step 2 — Include or exclude canaries at the source-root level

#### Recommended primary toggle

Use **folder-scope inclusion/exclusion**, not skip/defer policy.

Why:

- skip/defer is for format classes, not scenario state,
- folder inclusion is more operator-visible,
- the canary subtree is a business-state toggle, not a parser toggle.

Recommended behavior:

- **demo run:** include `_VALCAN_2026`
- **normal production run:** omit `_VALCAN_2026`

#### Recommended secondary safety net

Use the existing V2 import-side filter as the last guard:

```text
--exclude-source-glob "*_VALCAN_2026*"
--exclude-source-glob "*valcanary*"
```

This already fits `scripts/import_embedengine.py` and is recorded in import artifacts.

Source note: Local V2 import path already exposes `--exclude-source-glob`, and current runbooks explicitly document canaries and filters as visible operator artifacts.

### Step 3 — Run Forge and import normally

No special-case parser behavior is needed. The documents are intentionally standard `.xlsx`, `.docx`, `.pdf`, and `.txt`.

### Step 4 — Verify ingest integrity

Use `LanceStore.verify_ingest_completeness()` exactly as today to confirm:

- attempted rows,
- inserted rows,
- net delta,
- manifest delta

The canary design depends on this check being clean before any answer is trusted.

### Step 5 — Verify canary landing

Run three independent checks before every rehearsal:

1. **file-level landing**  
   confirm 40 canary source files exist in the imported dataset

2. **chunk-level landing**  
   confirm the canary marker returns the expected distinct `source_path` set in LanceDB

3. **entity-level landing**  
   confirm expected canary entity counts and sample values are present in `entities.sqlite3`

### Step 6 — Run the query validator

`scripts/validate_canary_aggregation.py` runs the canary and real-scoped query pack, reports pass/fail, and blocks rehearsal if any control fails.

---

## Verification Queries — Read-Only Proof Step

These are design examples, not implemented code.

### 1. Entity-store canary file presence

```sql
SELECT COUNT(DISTINCT source_path) AS canary_files_with_entities
FROM entities
WHERE source_path LIKE '%\\_VALCAN_2026\\%';
```

Expected:

- not all 40 files may produce entities,
- but the count should match the authored expectation from the canary manifest,
- any unexplained drop is a rehearsal blocker.

### 2. Canary PO count

```sql
SELECT COUNT(DISTINCT text) AS canary_pos
FROM entities
WHERE entity_type = 'PO'
  AND source_path LIKE '%\\_VALCAN_2026\\%'
  AND text IN (
    '9001000001', '9001000002', '9001000003', '9001000004',
    '9001000005', '9001000006', '9001000007', '9001000008',
    '9001000009', '9001000010', '9001000011', '9001000012'
  );
```

Expected:

```text
12
```

### 3. Canary open PO value cross-check

This one is likely easier against a deterministic table export or validation manifest than raw entity rows. The implementation should either:

- read `valcanary_ground_truth_index.xlsx`, or
- query a generated CSV/JSON sidecar derived from the same deterministic source data.

### 4. LanceDB canary marker presence

Python sketch:

```python
from src.store.lance_store import LanceStore

s = LanceStore("data/index/lancedb")
rows = s._table.search(
    "[CANARY-VALIDATION-DOCUMENT-DO-NOT-USE-IN-PRODUCTION]",
    query_type="fts",
).limit(5000).to_list()
paths = sorted({r.get("source_path", "") for r in rows})
print(len(paths))
```

Expected:

- distinct source paths should match the authored marker-bearing file count,
- any missing bundle is a blocker.

### 5. Hard-query evidence check

Example SQL against a generated crosswalk or extracted table rows:

```sql
SELECT COUNT(DISTINCT part_number)
FROM canary_failure_crosswalk
WHERE event_year = 2024
  AND failure_cause = 'LIGHTNING';
```

Expected:

```text
5
```

### Why independent proof matters

The validator must not rely on the same natural-language answer path it is testing. That is why store-level proof and query-level proof both exist.

---

## Reproducible Generation Script Spec

This is the spec for a future generator, not an implementation.

### Proposed path

```
scripts/generate_canary_corpus.py
```

### Inputs

- fixed seed, default `20260412`
- output root, default `E:\CorpusTransfr\verified\IGS\_VALCAN_2026\`
- optional `--overwrite`

### Outputs

- 40 files in the deterministic layout
- `canary_manifest.json`
- `canary_ground_truth.json`
- stable hash report for all generated files

### Determinism requirements

The script must:

1. write the same filenames every time,
2. write the same body text every time,
3. write the same spreadsheet row order every time,
4. write the same document metadata every time,
5. strip or freeze creation timestamps in generated Office/PDF artifacts,
6. emit a manifest with per-file SHA-256 hashes.

### Chunk stability requirements

Absolute chunk-ID stability across parser/library upgrades may be unrealistic. The design therefore defines two levels:

- **required:** stable file contents and stable authored facts
- **best effort:** stable chunk boundaries under the current parser/chunker settings

The validator should key off:

- file hashes,
- source paths,
- fact values,

not only chunk IDs.

### Template strategy

Use deterministic templates per format:

- `.xlsx` generated from fixed worksheet schema and ordered rows
- `.docx` generated from fixed template skeleton with static core properties
- `.pdf` generated from fixed template with scrubbed metadata
- `.txt` generated directly from static formatted text

### Authoring strategy

The generator should define one canonical in-memory fact model and render each document from that fact model. No hand-maintained duplicated values.

Why:

- one source of truth,
- exact arithmetic consistency,
- easier regeneration after changes.

---

## Validation Script Spec — `scripts/validate_canary_aggregation.py`

This is a design spec only.

### Purpose

Run a fixed known-answer query pack against the V2 query pipeline and compare the outputs against hand-authored expected answers and independent store-side truth.

### Inputs

- V2 config / runtime environment
- canary ground-truth file
- optional baseline evidence file for real+delta totals
- query pack file containing:
  - the two canary-backed demo queries,
  - the three real-scoped demo queries,
  - optional rehearsal-only medium/hard canary queries

### Behavior

1. open the V2 query pipeline in read-only mode,
2. run each query once,
3. record:
   - returned answer text,
   - returned query path/query type if available,
   - cited sources,
   - latency,
4. compare the answer to expected truth using:
   - exact numeric comparison for counts/totals,
   - exact-set comparison for fixed lists,
   - substring/evidence assertions for supporting text,
5. print a one-line result per query,
6. exit `0` only if all queries pass.

### Output format

Human-readable tabular output, one line per query:

```text
PASS | VALCAN-Q001 | AGGREGATE | expected=8 open POs / got=8 | delta=0 | 842 ms
FAIL | VALCAN-Q002 | AGGREGATE | expected=5 distinct parts / got=4 | delta=-1 | 911 ms
PASS | REAL-Q003 | AGGREGATE | expected=12 monthly files / got=12 | delta=0 | 603 ms
```

### Exit codes

- `0` = all pass
- `1` = any fail

### Idempotence requirement

The validator must:

- write no store data,
- mutate no config,
- regenerate nothing,
- be safe before every rehearsal.

### Delta analysis rules

When a query fails, print:

- expected value,
- observed value,
- numeric delta,
- missing/extra items for list questions,
- whether the wrong answer appears to be:
  - routing failure,
  - retrieval miss,
  - entity-store mismatch,
  - answer-formatting issue.

### Optional evidence artifacts

The script may also write:

- `docs/evidence/canary_validation_<timestamp>.md`
- `docs/evidence/canary_validation_<timestamp>.json`

But that is an implementation choice, not a requirement for the first pass.

---

## Recommended Implementation Sequence For Future Sprints

### Sprint A — Fact model and generator

- build deterministic fact model
- generate 40 files
- generate manifest and ground-truth JSON
- prove file-hash stability across reruns

### Sprint B — CorpusForge inclusion/exclusion path

- prove `_VALCAN_2026` can be included or omitted cleanly
- document the current nightly-delta broad-glob coverage for `valcanary_*`, and add a dedicated explicit rule only if the team wants narrower/clearer separation than the existing `*canary*` match
- prove import-side `--exclude-source-glob` safety net

### Sprint C — Store-side verification

- implement the read-only verification helper
- confirm:
  - file landing,
  - chunk landing,
  - entity landing,
  - arithmetic truth

### Sprint D — Query validator

- implement `scripts/validate_canary_aggregation.py`
- wire pass/fail output
- add rehearsal documentation

### Sprint E — Demo packet

- publish the five-query demo sheet
- publish frozen real baseline evidence
- publish operator narration and failure-recovery script

---

## What Future Sprints Need To Do To Implement This

| Step | Deliverable | Owner type |
|---|---|---|
| 1 | deterministic canary fact model | implementation agent |
| 2 | canary generator script + templates | implementation agent |
| 3 | canary manifest and ground-truth files | implementation agent |
| 4 | import/exclusion runbook update | docs/operator agent |
| 5 | read-only validation helper | implementation agent |
| 6 | query validator script | implementation agent |
| 7 | demo evidence packet with frozen baseline | coordinator + QA |

### Minimum acceptance criteria

- 40 deterministic files generated
- zero namespace collisions against current live store
- canary inclusion/exclusion is explicit and reversible
- independent proof queries match authored facts
- validator returns pass/fail cleanly
- operator can explain synthetic controls without sounding evasive

---

## Open Questions That Need User Judgment

### 1. Should the live demo use canary-only aggregation or real-baseline-plus-delta aggregation?

My recommendation is canary-only until Task #16 cleanup and a frozen real baseline exist.

### 2. How much of the canary pack should be visible to the audience?

I recommend one sentence of transparent disclosure, not a long benchmark lecture.

### 3. Does the user want the canary subtree kept inside the main corpus tree or parked adjacent to it?

Inside the main corpus tree is operationally simpler. Adjacent is safer against accidental production inclusion.

### 4. Should the validation pack be regenerated for each rehearsal or versioned and frozen?

I recommend versioned and frozen, regenerated only when the fact model changes.

### 5. Should corpus-wide total claims be allowed on May 2 if the regex cleanup lands late?

My recommendation is no. Use canary-only plus narrow real-scoped counts instead.

### 6. Does the coordinator want one hard canary in the live demo or reserve hard canaries for rehearsal only?

My recommendation is one hard canary at most, and only after two easier wins.

---

## Final Recommendation

Implement a **40-document `VALCAN` canary pack** in an isolated `_VALCAN_2026` subtree, disclose it transparently, and use it to validate the aggregation path with two known-answer demo controls. Pair that with three narrow real-scoped aggregation questions whose answers are frozen and manually verified before rehearsal. Do **not** claim that canaries alone make whole-corpus totals trustworthy; corpus-wide arithmetic only becomes defensible when a cleaned real baseline is frozen and then incremented by a deterministic canary delta.
