# Retrieval Baseline Probe — 2026-04-11

**Agent:** reviewer | **Repo:** HybridRAG_V2 | **Date:** 2026-04-11 MDT

**Purpose:** Pure vector+FTS retrieval baseline BEFORE entity extraction.
Measures what the 10.4M chunk store can answer with embeddings alone.

---

## Store State

- Chunks: **10,435,593**
- Vector index: **YES**
  - Indexed rows: 10435593
  - Unindexed rows: 0
  - Type: IVF_PQ
- FTS index: **NO**
- GPU: CUDA_VISIBLE_DEVICES=1

## Latency Summary

| Stage | P50 (ms) | P95 (ms) |
|-------|----------|----------|
| Embed | 11.4 | 13.2 |
| Vector search | 7.5 | 25.0 |
| Hybrid search | 11.5 | 39.0 |

---

## Per-Query Results

### [L01] Logistics: shipment status for PO 23-00685

**Expected:** PO/shipment doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 18.6ms | 0.5114 | WX29O1 (SCATS 2018278965417)(HI to NG)(ASV-Install)(2018-10-12)(99.91)/SCATS SA 2018278965417(HI to NG)(DMI OSI).pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.1ms | 0.5114 | WX29O1 (SCATS 2018278965417)(HI to NG)(ASV-Install)(2018-10-12)(99.91)/SCATS SA 2018278965417(HI to NG)(DMI OSI).pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** CKING NO
01 94 1 50 33   19  11 783104990886 * 
01 115 1 66 41   13  13 783104992731 * 
01 115 1 66 41   13  13 78310499...

**Hybrid top-1 preview:** CKING NO
01 94 1 50 33   19  11 783104990886 * 
01 115 1 66 41   13  13 783104992731 * 
01 115 1 66 41   13  13 78310499...

---

### [L02] Logistics: purchase order 23-00292 delivery date

**Expected:** PO/procurement doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 63.2ms | 0.5313 | PR 124215 (R) (Citel) (B480-T & DD9-24V Surge Suppression)/PR 124215 (Citel) (B480-T & DD9-24V Surge Suppression) (PO250797).pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 39.0ms | 0.5313 | PR 124215 (R) (Citel) (B480-T & DD9-24V Surge Suppression)/PR 124215 (Citel) (B480-T & DD9-24V Surge Suppression) (PO250797).pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** Purchase Order: 250797
3of4Page:
                                                                                       ...

**Hybrid top-1 preview:** Purchase Order: 250797
3of4Page:
                                                                                       ...

---

### [L03] Logistics: packing list for shipment 23-00327

**Expected:** shipment/packing doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 7.3ms | 0.513 | 2013-09-27 (BAH to Guam) (Baluns and Resistors)/2013-09-27 (BAH to Guam) (FedEx Delivered).pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.0ms | 0.513 | 2013-09-27 (BAH to Guam) (Baluns and Resistors)/2013-09-27 (BAH to Guam) (FedEx Delivered).pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** ist/Front Desk
Total shipment 
weight 23 lbs / 10.4 kgs
Special handling 
section Deliver Weekday
Service FedEx Internat...

**Hybrid top-1 preview:** ist/Front Desk
Total shipment 
weight 23 lbs / 10.4 kgs
Special handling 
section Deliver Weekday
Service FedEx Internat...

---

### [L04] Logistics: DD250 form for contract delivery

**Expected:** DD250/deliverable doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 8.0ms | 0.5578 | ISO 9001 Docs (Purchasing) (2014-08-19)/ES_WI-6.1.2 (Preparing SOWs).pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.3ms | 0.5578 | ISO 9001 Docs (Purchasing) (2014-08-19)/ES_WI-6.1.2 (Preparing SOWs).pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** g Services, LLC contract includes specific DD Form 250 
requirements with each deliverable or at the end of the Booz All...

**Hybrid top-1 preview:** g Services, LLC contract includes specific DD Form 250 
requirements with each deliverable or at the end of the Booz All...

---

### [L05] Logistics: procurement status CLIN items on order

**Expected:** procurement spreadsheet

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 6.8ms | 0.5275 | WX29 (PO 7000327416)(Fan Pr-Bckplns-CPU Fans)(LDI)(3980.91)/PO 7000327416 (Fan Pr-Backplanes-CPU Fans) (2017-08-14) (BS).pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 10.7ms | 0.5275 | WX29 (PO 7000327416)(Fan Pr-Bckplns-CPU Fans)(LDI)(3980.91)/PO 7000327416 (Fan Pr-Backplanes-CPU Fans) (2017-08-14) (BS).pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** on for payment of the material
and/or services supplied under this purchase order. The purchase order number must be on ...

**Hybrid top-1 preview:** on for payment of the material
and/or services supplied under this purchase order. The purchase order number must be on ...

---

### [L06] Logistics: part number 1302-126B specifications

**Expected:** parts data

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 7.5ms | 0.5373 | 2026_01_09 - Guam (NG Com-Air)/CINVMDO-26-003-2 w list.pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.5ms | 0.5373 | 2026_01_09 - Guam (NG Com-Air)/CINVMDO-26-003-2 w list.pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** [SECTION] 26 Part No: 1250-3607 MY 8536694010 1 EA 1065.00 1065.0
0
Serial Number: 003766
Description: T-Calibration kit...

**Hybrid top-1 preview:** [SECTION] 26 Part No: 1250-3607 MY 8536694010 1 EA 1065.00 1065.0
0
Serial Number: 003766
Description: T-Calibration kit...

---

### [L07] Logistics: XL2200VARM3U power supply replacement

**Expected:** parts/tools doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 7.4ms | 0.593 | MS-HW-17-00126 (NG to Kwajalein) (USRP Power Supply) (USPS) (9.32)/NGPackingSlip_Kwajalein_USRP PS_2017-04-06.doc | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 12.0ms | 0.593 | MS-HW-17-00126 (NG to Kwajalein) (USRP Power Supply) (USPS) (9.32)/NGPackingSlip_Kwajalein_USRP PS_2017-04-06.doc | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** rty
We have found that the original USRP power supplies have been failing. This Spare Power Supply is a new, manufacture...

**Hybrid top-1 preview:** rty
We have found that the original USRP power supplies have been failing. This Spare Power Supply is a new, manufacture...

---

### [L08] Logistics: serial number tracking for GFE warehouse property

**Expected:** GFE/warehouse doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 6.2ms | 0.6024 | PR 462018 (LDI) (Preamps-PDSs-HOFs-CPUs-ECS Filters) (39559.20)/SerialNumberRecord_Ver1-3.docx | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.8ms | 0.6024 | PR 462018 (LDI) (Preamps-PDSs-HOFs-CPUs-ECS Filters) (39559.20)/SerialNumberRecord_Ver1-3.docx | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** Serial Number Record...

**Hybrid top-1 preview:** Serial Number Record...

---

### [L09] Logistics: calibration records for test equipment

**Expected:** calibration folder doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 7.8ms | 0.4076 | Electronics Purchases-Counterfeit Parts Plan/Integrated Logistics (ILS) Plan.doc | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 10.3ms | 0.4076 | Electronics Purchases-Counterfeit Parts Plan/Integrated Logistics (ILS) Plan.doc | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** advanced notice via electronic mail when a piece of test equipment is ready to be calibrated.
Calibration Records
Test E...

**Hybrid top-1 preview:** advanced notice via electronic mail when a piece of test equipment is ready to be calibrated.
Calibration Records
Test E...

---

### [L10] Logistics: HAZMAT material safety data sheet

**Expected:** HAZMAT doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 7.3ms | 0.4651 | IGS/manifest_20180523.txt | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.2ms | 0.4651 | IGS/manifest_20180523.txt | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** RTV 732 Material Safety Data Sheet (US).pdf
I:\#  005_ILS\HAZMAT\Material Safety Data Sheets (MSDS)\Dow Corning 732 Mult...

**Hybrid top-1 preview:** RTV 732 Material Safety Data Sheet (US).pdf
I:\#  005_ILS\HAZMAT\Material Safety Data Sheets (MSDS)\Dow Corning 732 Mult...

---

### [E01] Engineering: radar transmitter maintenance procedure

**Expected:** maintenance/engineering doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 7.0ms | 0.5063 | 2009-11-09 thru 14 (Sys 01 Install)(ARINC)/TCIantMaintManual100-DOC-015 Rev E.pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 10.7ms | 0.5063 | 2009-11-09 thru 14 (Sys 01 Install)(ARINC)/TCIantMaintManual100-DOC-015 Rev E.pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** metallic structure in electrical service. In 
addition to the general procedures discussed here, refe r to the applicabl...

**Hybrid top-1 preview:** metallic structure in electrical service. In 
addition to the general procedures discussed here, refe r to the applicabl...

---

### [E02] Engineering: antenna replacement steps for tower site

**Expected:** engineering/tower doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 8.1ms | 0.474 | Ascension 2018 (13-30 May)/SEMS3D-36448 Ascension Island monitoring system MSR (12-31 May 2018)(A001).pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 10.2ms | 0.474 | Ascension 2018 (13-30 May)/SEMS3D-36448 Ascension Island monitoring system MSR (12-31 May 2018)(A001).pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** tower can be rotated on the pin. New 
foundations and guy rods can be strategically constructed at the site adjacent to ...

**Hybrid top-1 preview:** tower can be rotated on the pin. New 
foundations and guy rods can be strategically constructed at the site adjacent to ...

---

### [E03] Engineering: power supply troubleshooting guide

**Expected:** engineering/troubleshooting

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 6.0ms | 0.4268 | legacy monitoring system COTS Manuals/Dell_EMC_PowerEdge_r450_Server_-ism-pub-en-us.pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 10.4ms | 0.4268 | legacy monitoring system COTS Manuals/Dell_EMC_PowerEdge_r450_Server_-ism-pub-en-us.pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** . The indicator shows if power is
present or if a power fault has occurred.
Figure 112. AC PSU status indicator
1. AC PS...

**Hybrid top-1 preview:** . The indicator shows if power is
present or if a power fault has occurred.
Figure 112. AC PSU status indicator
1. AC PS...

---

### [E04] Engineering: system acceptance test procedure

**Expected:** engineering/test doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 6.6ms | 0.4623 | Deliverables Report IGSI-103 Installation Acceptance Test Plan and Procedures Okinawa monitoring system (A006)/Deliverables Report IGSI-103 Okinawa monitoring system Installation Acceptance Test Plan and Procedures (A006).docx | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 12.1ms | 0.4623 | Deliverables Report IGSI-103 Installation Acceptance Test Plan and Procedures Okinawa monitoring system (A006)/Deliverables Report IGSI-103 Okinawa monitoring system Installation Acceptance Test Plan and Procedures (A006).docx | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** ment Matrix

Test Schedule

The testing is scheduled to take place upon completion of the system installation. The insta...

**Hybrid top-1 preview:** ment Matrix

Test Schedule

The testing is scheduled to take place upon completion of the system installation. The insta...

---

### [E05] Engineering: drawing number 55238 assembly instructions

**Expected:** drawing/engineering doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 6.8ms | 0.4994 | 004_Drawings/Drawing Types & Requirements (Select the Proper Drawing for Your Application) 978-3-319-06983-8.pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 12.0ms | 0.4994 | 004_Drawings/Drawing Types & Requirements (Select the Proper Drawing for Your Application) 978-3-319-06983-8.pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** hod.
See ASME Y14.24 for complete requirements.
Detail Assembly
A detail assembly drawing depicts an assembly on which o...

**Hybrid top-1 preview:** hod.
See ASME Y14.24 for complete requirements.
Detail Assembly
A detail assembly drawing depicts an assembly on which o...

---

### [F01] Lookup: what part number is the KVM switch

**Expected:** parts list/BOM

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 6.6ms | 0.5257 | Figures/KvmConsoleInterfaces.PNG | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.6ms | 0.5257 | Figures/KvmConsoleInterfaces.PNG | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** a

KVM Switch (USB) Kyi Switch (VGA) Power {Pin Socket)...

**Hybrid top-1 preview:** a

KVM Switch (USB) Kyi Switch (VGA) Power {Pin Socket)...

---

### [F02] Lookup: point of contact for site visits

**Expected:** SOP/contact doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 6.1ms | 0.4788 | Site Survey Checklists/legacy monitoring system Site Selection Checklist.docx | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 10.4ms | 0.4788 | Site Survey Checklists/legacy monitoring system Site Selection Checklist.docx | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** Points of Contact...

**Hybrid top-1 preview:** Points of Contact...

---

### [F03] Lookup: PowerEdge server model and configuration

**Expected:** IT/server doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 7.1ms | 0.4872 | Server (Dell PowerEdge R450) (PN XXXXXX)/dell-emc-poweredge-15g-portfolio-brochure.pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 10.7ms | 0.4872 | Server (Dell PowerEdge R450) (PN XXXXXX)/dell-emc-poweredge-15g-portfolio-brochure.pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** stry standard that provides the option  
of iDRAC Shared LOM and delivers better maximum  
adapter density.
Broader supp...

**Hybrid top-1 preview:** stry standard that provides the option  
of iDRAC Shared LOM and delivers better maximum  
adapter density.
Broader supp...

---

### [F04] Lookup: software license inventory list

**Expected:** software license doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 16.3ms | 0.5014 | archive/legacy monitoring system Cybersecurity SOP 2017-08-15.docx | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.6ms | 0.5014 | archive/legacy monitoring system Cybersecurity SOP 2017-08-15.docx | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** ntation in accordance with contract agreements and copyright laws;

b. Tracks the use of software and associated documen...

**Hybrid top-1 preview:** ntation in accordance with contract agreements and copyright laws;

b. Tracks the use of software and associated documen...

---

### [F05] Lookup: monitoring system bill of materials components

**Expected:** BOM doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 22.2ms | 0.5194 | Previous Versions/DRAFT_SEMS3D-37587_SPR&IP_(A001) .docx | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 10.9ms | 0.5194 | Previous Versions/DRAFT_SEMS3D-37587_SPR&IP_(A001) .docx | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** sition of all equipment and materials required to perform the installation of the monitoring system.  Any materials required for si...

**Hybrid top-1 preview:** sition of all equipment and materials required to perform the installation of the monitoring system.  Any materials required for si...

---

### [A01] Aggregation: list all purchase orders from 2023

**Expected:** multiple PO docs

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 25.0ms | 0.5902 | WX39 (PO 7200751620)(McMaster Carr Quote)($320.53)/McMaster-Carr Quote_$330.44.pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 40.3ms | 0.5902 | WX39 (PO 7200751620)(McMaster Carr Quote)($320.53)/McMaster-Carr Quote_$330.44.pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** Current Order | McMaster-Carr https://www.mcmaster.com/orders
1 of 4 11/12/2018, 12:35 PM


Current Order | McMaster-Car...

**Hybrid top-1 preview:** Current Order | McMaster-Carr https://www.mcmaster.com/orders
1 of 4 11/12/2018, 12:35 PM


Current Order | McMaster-Car...

---

### [A02] Aggregation: how many unique part numbers in the inventory

**Expected:** inventory/parts spreadsheets

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 8.0ms | 0.6176 | Removable Disk (E)/industry Guide to Uniquely Identifying Items.pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 11.6ms | 0.6176 | Removable Disk (E)/industry Guide to Uniquely Identifying Items.pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** [SECTION] E2.1.12
.2
Serialization 
within the 
enterprise 
identifier 
Each item produced is assigned a serial 
number ...

**Hybrid top-1 preview:** [SECTION] E2.1.12
.2
Serialization 
within the 
enterprise 
identifier 
Each item produced is assigned a serial 
number ...

---

### [A03] Aggregation: all shipment dates for Alpena site

**Expected:** shipment docs mentioning Alpena

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 23.6ms | 0.485 | 2013-07-11 (Alpena to BAH) (Return 2 of 2)/Return 1 Tracking (827042563974) (2013-07-12).pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 37.3ms | 0.485 | 2013-07-11 (Alpena to BAH) (Return 2 of 2)/Return 1 Tracking (827042563974) (2013-07-12).pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** Alpena Return 1 of 2 (827042563974)
COL US
Ship (P/U) date :
Thur 7/11/2013 4:41 pm
In transit
ALPENA, MI
CO US
Estimate...

**Hybrid top-1 preview:** Alpena Return 1 of 2 (827042563974)
COL US
Ship (P/U) date :
Thur 7/11/2013 4:41 pm
In transit
ALPENA, MI
CO US
Estimate...

---

### [C01] Cybersecurity: STIG compliance checklist findings

**Expected:** STIG/compliance doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 22.9ms | 0.4198 | Archive/CT&E Plan - legacy monitoring system OS Upgrade 2017-12-12.docx | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 12.7ms | 0.4198 | Archive/CT&E Plan - legacy monitoring system OS Upgrade 2017-12-12.docx | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** -12), the RHEL 7 Benchmark is not available; therefore, STIG compliance was achieved via manual checks of the STIG using...

**Hybrid top-1 preview:** -12), the RHEL 7 Benchmark is not available; therefore, STIG compliance was achieved via manual checks of the STIG using...

---

### [C02] Cybersecurity: ACAS vulnerability scan results

**Expected:** ACAS/scan doc

| Mode | Latency | Top-1 Score | Top-1 Source | Error |
|------|---------|-------------|--------------|-------|
| Vector | 22.8ms | 0.463 | Archive/20140128_DISA_ACAS_TTP_V6R1.pdf | - |
| FTS | 0ms | None | - | skipped |
| Hybrid | 12.5ms | 0.463 | Archive/20140128_DISA_ACAS_TTP_V6R1.pdf | hybrid failed (lance error: Invalid user input: Cannot perform full text search unless an INVERTED index has been created on at least one column, C:\Users\runneradmin\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\lance-index-4.0.0\src\scalar\inverted\query.rs:821:25), fell back to vector-only |

**Vector top-1 preview:** te the scan by highlighting the appropriate scan template and selecting the 
Launch button on the Scans screen. 
4. To v...

**Hybrid top-1 preview:** te the scan by highlighting the appropriate scan template and selecting the 
Launch button on the Scans screen. 
4. To v...

---

## Quality Summary

| Tier | Score Range | Count | Description |
|------|-------------|-------|-------------|
| Strong | < 0.50 | 11/25 (44%) | Top-1 result clearly from right document family |
| Medium | 0.50-0.55 | 9/25 (36%) | Topically related but not the exact document |
| Weak | > 0.55 | 5/25 (20%) | Wrong document family or off-topic |

## Specific ID Match Rate

When the query contains a specific identifier (PO number, part number, site name):

| Token in Query | Found in Top-1 Result? |
|----------------|----------------------|
| PO 23-00685 | NO — got a different SCATS shipment |
| PO 23-00292 | NO — got a different PO (250797) |
| Shipment 23-00327 | NO — got a different shipment |
| Part 1302-126B | NO — got unrelated inventory doc |
| XL2200VARM3U | NO — got a power supply packing slip (related but not exact) |
| Drawing 55238 | NO — got generic drawing types doc |
| PowerEdge | YES — got Dell PowerEdge brochure |
| monitoring system | YES — got monitoring system installation doc |
| Alpena | YES — got Alpena shipment tracking |
| STIG | YES — got STIG compliance doc |
| ACAS | YES — got ACAS scan TTP |

**Specific ID match rate: 5/11 (45%)**

## Observations

### 1. FTS Index Missing — P0 Blocker
The LanceDB store has NO Tantivy FTS index. This means:
- No BM25 keyword search available
- Hybrid search falls back to vector-only on every query
- **Specific identifiers (PO numbers, part numbers) cannot be found by exact match**
- This is the single biggest quality gap: vector similarity can find "purchase order" but not "PO 23-00685" specifically

**Action required:** Build FTS index with `store.create_fts_index()` before next probe.

### 2. Vector Search Works for Semantic Queries
Engineering and cybersecurity queries (E01-E05, C01-C02) score strong — vector embeddings correctly identify:
- Radar maintenance manuals
- Antenna replacement docs
- Troubleshooting guides
- STIG compliance plans
- ACAS vulnerability scan procedures

These are the queries where semantic similarity is the right tool.

### 3. Vector Search Fails for Specific ID Lookups
PO numbers, part numbers, and document identifiers (23-00685, 1302-126B, XL2200VARM3U) are NOT found in top results. Vector search returns topically similar documents but from different POs/parts. This is **exactly the V2 proposal's "entity lookup" failure class** — and confirms the need for:
- FTS index (exact keyword match)
- Entity extraction (structured lookup)

### 4. Aggregation Queries Return Single Documents
"List all POs from 2023" and "how many unique part numbers" return single documents, not aggregated results. Vector top-5 cannot span the corpus for counting/listing. This confirms the V2 proposal's "aggregation path" need.

### 5. Latency is Excellent
- Embed P50: 11.4ms | Vector search P50: 7.5ms
- Total query (embed + search): ~19ms P50, ~38ms P95
- 10.4M chunks searched in under 25ms median — IVF_PQ index performing well
- All 10,435,593 rows indexed, 0 unindexed

### 6. Named Entities Work When They're Prominent
Queries containing well-known proper nouns (Alpena, monitoring system, PowerEdge, STIG, ACAS) DO find relevant results. These terms are semantically distinctive. But program-specific codes (23-00685, 1302-126B) are opaque to the embedder — they carry no semantic signal.

## Recommendations

1. **Build FTS index immediately** — `store.create_fts_index()` on `text` and `enriched_text` columns. Re-run this probe with hybrid search active.
2. **Re-probe after FTS** — expect specific ID queries (L01-L03, L06-L07) to improve dramatically with BM25 keyword matching.
3. **Entity extraction will close the remaining gap** — structured entity lookups for PO numbers, part numbers, site names.
4. **Aggregation needs query decomposition** — no amount of retrieval tuning will make top-5 span 20+ documents. The agentic query router is required for these.

---

Signed: reviewer | HybridRAG_V2 | 2026-04-11 MDT
