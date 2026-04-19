# May 2 Demo Query Binder — 2026-04-12

**Purpose:** Detailed evidence binder for the safe demo pack.
**Use:** Pair this with `docs/MAY2_DEMO_QUERY_PACK_2026-04-12.md`.
**Rule:** Retrieval-first queries are live-safe. Narrow real-scoped counts and canary controls are conditional.

## Core Safe Set

### `PQ-101`

- Query text: `What is the latest enterprise program weekly hours variance for fiscal year 2024?`
- Persona: `Program Manager`
- Safety class: `retrieval-first safe`
- Why it is safe: One dated spreadsheet family, one latest-file target, and a clean path under weekly variance reports.
- What it proves: V2 can retrieve a real PM spreadsheet artifact, not just narrative docs.
- Expected family: `Program Management`
- Expected supporting files / paths:
  - `10.0 Program Management/2.0 Weekly Variance Reports/2024/2024-12/2024-12-31 enterprise program Weekly Hours Variance.xlsx`
- Operator fallback if the system misses: Pivot to the dated weekly variance folder and restate that the latest filed weekly workbook is the target artifact.
- Fallback narration: `This is a direct spreadsheet lookup, so I am going straight to the filed weekly variance workbook.`

### `PQ-104`

- Query text: `What is the enterprise program Integrated Master Schedule deliverable and where is it tracked?`
- Persona: `Program Manager`
- Safety class: `retrieval-first safe`
- Why it is safe: A031 is a clear CDRL family with multiple anchored IMS deliverables.
- What it proves: V2 can explain contract/deliverable structure and locate the right family.
- Expected family: `CDRLs`
- Expected supporting files / paths:
  - `1.0 enterprise program DM - Restricted/OASIS/A031 - Integrated Master Schedule (IMS)/2023/Deliverables Report IGSI-153 enterprise program IMS_06_20_23 (A031).pdf`
  - `1.0 enterprise program DM - Restricted/OASIS/A031 - Integrated Master Schedule (IMS)/2023/Deliverables Report IGSI-1149 enterprise program IMS_11_29_23 (A031).pdf`
- Operator fallback if the system misses: Show the A031 folder family and answer from the deliverable naming convention.
- Fallback narration: `The safe answer here is the A031 family itself, even if the first pass wording is weak.`

### `PQ-113`

- Query text: `What is purchase order 5000585586 and what did it order?`
- Persona: `Logistics Lead`
- Safety class: `retrieval-first safe`
- Why it is safe: Exact SAP-style PO token with a confirmed procurement folder and matching packing list.
- What it proves: V2 can do exact-identifier retrieval on real logistics records.
- Expected family: `Logistics`
- Expected supporting files / paths:
  - `5.0 Logistics/Procurement/002 - Received/monitoring system Sustainment OY2 (1 Aug 24 - 31 Jul 25)/PO - 5000585586, PR 3000133844 Pulling Tape LLL monitoring system(GRAINGER)($598.00)/`
- Operator fallback if the system misses: Search the exact PO token in the procurement subtree and show the procurement folder name.
- Fallback narration: `This is an exact-token procurement lookup, so I will trust the folder name over a weak generated answer.`

### `PQ-115`

- Query text: `Which Tripp Lite power cord part number is used for legacy monitoring systems?`
- Persona: `Logistics Lead`
- Safety class: `retrieval-first safe`
- Why it is safe: Exact part number embedded in the folder name; clean physical-part anchor.
- What it proves: V2 can retrieve real parts-reference data from downloaded logistics catalogs.
- Expected family: `Logistics`
- Expected supporting files / paths:
  - `5.0 Logistics/Parts (Downloaded Information)/legacy monitoring system Parts/Power Cord (Tripp Lite PN P007-003)(CDW PN 3349509)(3 Foot_5-15P to C12_15A_14 AWG)/`
- Operator fallback if the system misses: Show the folder name with `P007-003` and read the part number directly.
- Fallback narration: `This is a clean part-number family, so the folder name itself is valid evidence.`

### `PQ-122`

- Query text: `What recommended spares parts list exists and what fields does it track?`
- Persona: `Logistics Lead`
- Safety class: `retrieval-first safe`
- Why it is safe: Canonical spreadsheet family with repeated snapshots and known fields.
- What it proves: V2 can surface spreadsheet structure, not only file existence.
- Expected family: `Logistics`
- Expected supporting files / paths:
  - `5.0 Logistics/Parts (Downloaded Information)/Recommended Spares Parts List (2018-06-26).xlsx`
  - `5.0 Logistics/Parts (Downloaded Information)/Recommended Spares Parts List (2018-06-27).xlsx`
  - `zzSEMS ARCHIVE/005_ILS/Spares/Recommended Spares Parts List.xlsx`
- Operator fallback if the system misses: Open the recommended spares list family and restate the known field set from the binder.
- Fallback narration: `If the answer is thin, I will anchor on the spreadsheet family and its known columns.`

### `PQ-129`

- Query text: `What site outages have been analyzed in the Systems Engineering folder?`
- Persona: `Field Engineer`
- Safety class: `retrieval-first safe`
- Why it is safe: Stable engineering subtree with a live folder plus archived outage metrics.
- What it proves: V2 can navigate engineering analysis families across current and archived material.
- Expected family: `Systems Engineering`
- Expected supporting files / paths:
  - `6.0 Systems_Engineering/3_Site Outages Analysis/`
  - `6.0 Systems_Engineering/3_Site Outages Analysis/Outage Analysis for IPT Slides/zArchive/IGS-Outage-Analysis_2025-12-01.xlsx`
  - `6.0 Systems_Engineering/3_Site Outages Analysis/z_Archive/OutageMetrics/CumulativeOutageFiles/2021/CumulativeOutagesDec2021.xlsx`
- Operator fallback if the system misses: Show the Systems Engineering outage-analysis subtree and explain that the family, not one row, is the proof.
- Fallback narration: `This question is about the analysis family, so the folder tree is sufficient evidence if the summary is weak.`

### `PQ-130`

- Query text: `What is the Corrective Action Plan for Fairford monitoring system incident IGSI-1811?`
- Persona: `Field Engineer`
- Safety class: `retrieval-first safe`
- Why it is safe: Exact incident ID and one confirmed CAP file.
- What it proves: V2 can retrieve incident-specific engineering records.
- Expected family: `CDRLs`
- Expected supporting files / paths:
  - `1.5 enterprise program CDRLS/A001 - Corrective Action Plan (CAP)/47QFRA22F0009_IGSI-1811_Corrective_Action_Plan_Fairford-NEXION_2024-06-05.docx`
- Operator fallback if the system misses: Search `IGSI-1811` directly and show the CAP document name.
- Fallback narration: `This is a single-incident retrieval, so the incident ID is the anchor.`

### `PQ-136`

- Query text: `What ACAS scan results are documented for the legacy monitoring systems under CDRL A027?`
- Persona: `Cybersecurity / Network Admin`
- Safety class: `retrieval-first safe`
- Why it is safe: Clear A027 ACAS deliverable family with both CDRL and continuous-monitoring evidence.
- What it proves: V2 can retrieve cyber compliance artifacts from the A027 subtree.
- Expected family: `CDRLs`
- Expected supporting files / paths:
  - `1.5 enterprise program CDRLS/A027 - DAA Accreditation Support Data (ACAS Scan Results)/2023/2023-May/Deliverables Report IGSI-966 legacy monitoring system DAA Accreditation Support Data (ACAS San Results) (A027)/legacy monitoring system Scan Report 2023-May.xlsx`
  - `1.0 enterprise program DM - Restricted/SEMS3D/A027 - Cybersecurity/A027 - WX29 OY2-4 Continuous Monitoring/legacy monitoring system/Monthly Scans-POAMS/2021/2021-Jun - SEMS3D-41845/SEMS3D-41845.zip`
- Operator fallback if the system misses: Pivot to the A027 ACAS subtree and name the confirmed IGSI-966 scan report.
- Fallback narration: `The live-safe proof here is the A027 ACAS family itself.`

### `PQ-141`

- Query text: `What Apache Log4j directive has been issued for enterprise program systems?`
- Persona: `Cybersecurity / Network Admin`
- Safety class: `retrieval-first safe`
- Why it is safe: Exact directive identifier and one unambiguous folder.
- What it proves: V2 can answer exact-token cyber directive questions quickly and clearly.
- Expected family: `Cybersecurity`
- Expected supporting files / paths:
  - `3.0 Cybersecurity/Directives/MTO 2021-350-001 Apache Log4j/`
- Operator fallback if the system misses: Search the exact directive ID `MTO 2021-350-001` and show the directive folder.
- Fallback narration: `This is an exact directive lookup, so the directive ID is the proof handle.`

### `BND-001`

- Query text: `What maintenance was performed at Fort Wainwright in 2024?`
- Persona: `Boundary`
- Safety class: `refusal / boundary-setting safe`
- Why it is safe: Known out-of-corpus query from the earlier demo script.
- What it proves: The operator will not treat unsupported answers as authoritative.
- Expected family: `None / out of corpus`
- Expected supporting files / paths:
  - none
- Operator fallback if the system misses: State manually that Fort Wainwright is outside the validated corpus lane and move on.
- Fallback narration: `This is outside the corpus, so refusal is the correct behavior.`

## Optional Stretch Set

### `PQ-103`

- Query text: `Which CDRL is A002 and what maintenance service reports have been submitted under it?`
- Persona: `Program Manager`
- Safety class: `retrieval-first safe`
- Why it is safe: Exact CDRL code with a known A002 folder and 21 site subfolders.
- What it proves: Contract code to deliverable-family mapping.
- Expected family: `CDRLs`
- Expected supporting files / paths:
  - `1.5 enterprise program CDRLS/A002 - Maintenance Service Report (MSR)/`
- Operator fallback if the system misses: Show the A002 folder name and explain that A002 is the MSR family.
- Fallback narration: `Even if the system stumbles, A002 itself is a clean directory-level anchor.`

### `PQ-110`

- Query text: `What is the LDI suborganization 2024 budget for ORG enterprise program and how is it organized by option year?`
- Persona: `Program Manager`
- Safety class: `retrieval-first safe`
- Why it is safe: Confirmed spreadsheet family with dated budget files.
- What it proves: V2 can retrieve deeper PM budget artifacts, not just top-level status files.
- Expected family: `Program Management`
- Expected supporting files / paths:
  - `10.0 Program Management/LDI/Budget ORG 2024 HOURS, 20240507, April to December.xlsx`
  - `10.0 Program Management/LDI/Copy of Budget ORG 2024 HOURS 20240110 rev1.xlsx`
  - `10.0 Program Management/LDI/Copy of ORG enterprise program for 20240801 to 20250731 - Proposed Budget.xlsx`
- Operator fallback if the system misses: Move to the dated LDI budget family and point out the option-year budget files.
- Fallback narration: `This is a deeper PM spreadsheet lane, so I will fall back to the budget family if needed.`

### `PQ-112`

- Query text: `What pre-amplifier parts are used in the legacy monitoring systems and what are their specifications?`
- Persona: `Logistics Lead`
- Safety class: `retrieval-first safe`
- Why it is safe: Uses confirmed physical part numbers, not polluted PART aggregates.
- What it proves: V2 can surface technical specification content from parts catalogs.
- Expected family: `Logistics`
- Expected supporting files / paths:
  - `5.0 Logistics/Parts (Downloaded Information)/legacy monitoring system Parts/Pre-Amplifier (P240-260VDG)(P240-270VDG)/`
- Operator fallback if the system misses: State the two part numbers directly and show the pre-amplifier folder.
- Fallback narration: `This stays safe because the parts are clean folder anchors, not live aggregate counts.`

### `PQ-128`

- Query text: `What maintenance actions are documented in the Thule monitoring system Maintenance Service Reports?`
- Persona: `Field Engineer`
- Safety class: `retrieval-first safe`
- Why it is safe: One site, one MSR family, confirmed in both CDRL and OASIS trees.
- What it proves: V2 can summarize site-specific maintenance history from MSRs.
- Expected family: `CDRLs`
- Expected supporting files / paths:
  - `1.5 enterprise program CDRLS/A002 - Maintenance Service Report (MSR)/Thule-monitoring system/`
  - `1.0 enterprise program DM - Restricted/OASIS/A002 - Maintenance Service Report (MSR)/Thule/`
- Operator fallback if the system misses: Show the Thule MSR subtree and answer from the known site-specific family.
- Fallback narration: `The safe anchor is the Thule MSR family, not a free-form summary.`

### `PQ-138`

- Query text: `What is the System Authorization Boundary for monitoring system defined in SEMP?`
- Persona: `Cybersecurity / Network Admin`
- Safety class: `retrieval-first safe`
- Why it is safe: Exact document title with one clear file path.
- What it proves: V2 can retrieve cyber architecture boundary documents, not just scans and directives.
- Expected family: `Cybersecurity`
- Expected supporting files / paths:
  - `3.0 Cybersecurity/monitoring systems Authorization Boundary SEMP 2024-8-28.pdf`
- Operator fallback if the system misses: Search the exact file title and use the document name as the answer handle.
- Fallback narration: `This is document-title retrieval, so the file name is enough to keep the answer honest.`

### `PQ-142`

- Query text: `What STIG reviews have been filed and when?`
- Persona: `Cybersecurity / Network Admin`
- Safety class: `retrieval-first safe`
- Why it is safe: One confirmed STIG review spreadsheet with a clear date prefix.
- What it proves: V2 can retrieve cyber tabular artifacts, not only semantic PDFs.
- Expected family: `Cybersecurity`
- Expected supporting files / paths:
  - `3.0 Cybersecurity/111023_STIG_Review.xlsx`
- Operator fallback if the system misses: Show the dated STIG review spreadsheet and call out the `111023` date token.
- Fallback narration: `This is a one-file tabular query, so I can safely anchor on the worksheet itself.`

### `PQ-395`

- Query text: `How many Monthly Actuals spreadsheets are filed for calendar year 2024?`
- Persona: `Program Manager`
- Safety class: `narrow real-scoped count safe`
- Why it is safe: One recurring file family with exactly twelve month-stamped files and explicit anchor evidence.
- What it proves: A narrow real count can be defended without claiming broad aggregation is solved.
- Expected family: `Program Management`
- Expected supporting files / paths:
  - `10.0 Program Management/1.0 FEP/Reference/2024 01 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 02 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 03 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 04 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 05 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 06 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 07 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 08 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 09 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 10 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 11 Monthly Actuals.xlsx`
  - `10.0 Program Management/1.0 FEP/Reference/2024 12 Monthly Actuals.xlsx`
- Operator fallback if the system misses: Use the frozen 12-file evidence list and state that the count is manually bound to one file family.
- Fallback narration: `This is a narrow real count over one recurring folder family, so I will use the frozen list if the live answer is weak.`

### `PQ-146`

- Query text: `How many site-specific Maintenance Service Report folders exist across both legacy monitoring system and monitoring system?`
- Persona: `Aggregation / Cross-role`
- Safety class: `narrow real-scoped count safe`
- Why it is safe: Single A002 subtree with a manually enumerable folder list; still conditional because it is a live count claim.
- What it proves: One defensible real structured count over a known deliverable family.
- Expected family: `CDRLs`
- Expected supporting files / paths:
  - `1.5 enterprise program CDRLS/A002 - Maintenance Service Report (MSR)/`
- Operator fallback if the system misses: Show the frozen A002 site-folder list and stop at the manual count.
- Fallback narration: `This count is narrow because it stays inside one A002 folder tree.`

### `REAL-Q005`

- Query text: `How many named cybersecurity directives are in the current directive reference set?`
- Persona: `Cybersecurity / Network Admin`
- Safety class: `narrow real-scoped count safe`
- Why it is safe: The current methodology already names the five directives; the operator can freeze that list before rehearsal.
- What it proves: A narrow cyber count can be defended without claiming broad cyber aggregation.
- Expected family: `Cybersecurity`
- Expected supporting files / paths:
  - `3.0 Cybersecurity/Directives/MTO 2021-350-001 Apache Log4j/`
  - `3.0 Cybersecurity/Directives/%Samba Wanna-Cry%`
  - `3.0 Cybersecurity/Directives/%SPARTAN VIPER%`
  - `3.0 Cybersecurity/Directives/%PKI%`
  - `3.0 Cybersecurity/Directives/%VPN Laptop%`
- Operator fallback if the system misses: Use the frozen five-directive list from the evidence binder and say the query is bounded to that reference set.
- Fallback narration: `This is a small audited directive set, not a corpus-wide compliance count.`

### `VALCAN-Q001`

- Query text: `How many open validation purchase orders exist across all validation sites, and what is their total value?`
- Persona: `Logistics Lead`
- Safety class: `canary-only validation control`
- Why it is safe: Pre-known synthetic control with exact expected count and total.
- What it proves: The structured path can do arithmetic on a deterministic validation pack.
- Expected family: `VALCAN`
- Expected supporting files / paths:
  - `valcanary_po_register_2024.xlsx`
  - `valcanary_po_receipts_2024.xlsx`
- Operator fallback if the system misses: Stop making aggregate claims, switch to the validation evidence table, and call the control failed.
- Fallback narration: `This is a validation control, not hidden proof. If it fails, we stop using live aggregate claims.`

### `VALCAN-Q002`

- Query text: `How many distinct validation part numbers failed during lightning-related service events in 2024, and at which validation sites did those failures occur?`
- Persona: `Aggregation / Cross-role`
- Safety class: `canary-only validation control`
- Why it is safe: Pre-known synthetic hard control with exact event, part, and site counts.
- What it proves: The structured path can handle cross-document aggregation, not just a single spreadsheet total.
- Expected family: `VALCAN`
- Expected supporting files / paths:
  - `valcanary_service_event_tracker_2024.xlsx`
  - `valcanary_failure_mode_summary_2024.pdf`
  - `valcanary_part_failure_to_po_crosswalk.xlsx`
- Operator fallback if the system misses: Enumerate the four lightning events and five parts from the evidence artifact and keep the trust boundary intact.
- Fallback narration: `This is the hard validation control; if it misses, it stays in rehearsal only.`

## Explicit Do-Not-Use-Live Set

### `PQ-107`

- Query text: `How many CDRL deliverable types are defined in the enterprise program contract?`
- Why to avoid live: Broad contract-wide aggregation and cataloging, not a tight operator win.

### `PQ-118`

- Query text: `What procurement records exist for the monitoring system Sustainment option year 2 period?`
- Why to avoid live: Vague aggregate surface; too easy to wander into broad procurement claims.

### `PQ-134`

- Query text: `What is the Part Failure Tracker and what parts have been replaced?`
- Why to avoid live: The binder itself notes this spreadsheet does not aggregate cleanly via chunk retrieval; also too close to polluted part-count territory.

### `PQ-143`

- Query text: `What ATO re-authorization packages have been submitted for legacy monitoring system since 2020?`
- Why to avoid live: Multi-year aggregate list; good audit query, poor stage query.

### `PQ-149`

- Query text: `Which monitoring system and legacy monitoring system sites have had installation visits documented?`
- Why to avoid live: Long site enumeration with weak operator ergonomics.

### `PQ-150`

- Query text: `What is the full set of CDRL deliverables for the enterprise program?`
- Why to avoid live: Too broad and list-heavy; invites overclaiming about coverage.

### `PQ-203`

- Query text: `How many 2024 shipments went to OCONUS sites and which sites were involved?`
- Why to avoid live: Multi-site count + list answer; brittle live.

### `PQ-205`

- Query text: `How many weekly variance reports have been filed in 2024 and how do they distribute across months?`
- Why to avoid live: Reference evidence explicitly says only partial monthly confirmation exists.

### `PQ-192` and `PQ-263`

- Query text:
  - `What ACAS scan deliverables have been filed under the new FA881525FB002 contract?`
  - `How many A027 ACAS scan deliverables have been issued under contract FA881525FB002?`
- Why to avoid live: Current source materials disagree on the confirmed count (`4` vs `3`). Reconcile before using either.

## Binder Sources

- `tests/golden_eval/production_queries_400_2026-04-12.json`
- `docs/CANARY_INJECTION_METHODOLOGY_2026-04-12.md`
- `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md`
- `docs/DEMO_SCRIPT_2026-04-05.md`
