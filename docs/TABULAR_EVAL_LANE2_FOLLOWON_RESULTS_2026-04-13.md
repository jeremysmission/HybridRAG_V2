# Tabular Eval Report — lane2_followon_tabular_v1

**Date:** 2026-04-13
**Config:** `config/config.lane2_followon_stage_2026-04-13.yaml`
**Entity DB:** `C:\HybridRAG_V2\data\index\clean\lane2_followon_stage_20260413\entities.sqlite3`
**Total table rows in store:** 9,133
**Queries:** 8
**PASS:** 8
**FAIL:** 0

## Results

| ID | Family | Kind | Verdict | Rows | Notes |
| --- | --- | --- | --- | --- | --- |
| T-01 | received_po | exact_po_lookup | **PASS** | 15 |  |
| T-02 | spares_report | exact_part_lookup | **PASS** | 9 |  |
| T-03 | spares_report | description_lookup | **PASS** | 6 |  |
| T-04 | received_po | header_enumeration | **PASS** | 282 |  |
| T-05 | spares_report | source_enumeration | **PASS** | 254 |  |
| T-06 | received_po | exact_pr_lookup | **PASS** | 3 |  |
| T-07 | spares_report | pipe_joined_row_lookup | **PASS** | 500 |  |
| T-08 | spares_report | vendor_lookup | **PASS** | 16 |  |

## Sample rows per query

### T-01 — Find the row for PO Number 5300045239.

- `D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl\2024 01 PR & PO.xlsx` `03d10a26f4d2d41e5552c9fd9f2980_kvtable_2` row=0
    - `LOE`: `Matl`
    - `Count PO#`: `1`
    - `PO Invoice Completed Indicator`: `##`
    - `PO Number`: `5300045239`
    - `Shopping Cart Number`: `0015803502`
    - `G/L Account Number`: `0004300011`

- `D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl\2024 01 PR & PO.xlsx` `6c6b39c5a174ce833e4870e070d031_kvtable_2` row=1
    - `LOE`: `Matl`
    - `CLIN`: `0002A`
    - `Network`: `NA1A26703400`
    - `PR Number`: `0031393862`
    - `PO Number`: `5300045239`
    - `Shopping Cart Number`: `0015803502`

### T-02 — Find the spares row for Part Number ZFBT-4R2G-FT+.

- `rpusTransfr\verified\IGS\1.0 enterprise program DM - Restricted\SEMS3D\A001-PSIP\A001-ISTO_Initial_Spares\SEMS3D-37218 legacy monitoring system Spares.xlsx` `80936a3841efbca70951adb1a8056c_kvtable_3` row=0
    - `TO`: `WX31M4`
    - `Requirement`: `BOM`
    - `Line Item`: `36`
    - `Quote #`: `Web Quote`
    - `Site`: `Material Buydown legacy monitoring system Spares Kit`
    - `Part Number`: `ZFBT-4R2G-FT+`

- `rpusTransfr\verified\IGS\1.0 enterprise program DM - Restricted\SEMS3D\A001-PSIP\A001-ISTO_Initial_Spares\SEMS3D-37218 legacy monitoring system Spares.xlsx` `dae52721763ab1230b1d90014cc54d2_pipekv_1` row=0
    - `Date Received TO`: `WX31M4`
    - `Requirement`: `BOM`
    - `Line Item`: `35`
    - `Quote #`: `Q000X5B6`
    - `Site`: `Material Buydown legacy monitoring system Spares Kit`
    - `Part Number`: `DGXZ +36NFNF-A`

### T-03 — Find the spares row for a Power Supply, Redundant, 900W.

- `rpusTransfr\verified\IGS\1.0 enterprise program DM - Restricted\SEMS3D\A001-PSIP\A001-ISTO_Initial_Spares\SEMS3D-37218 legacy monitoring system Spares.xlsx` `80936a3841efbca70951adb1a8056c_kvtable_1` row=0
    - `Part Description`: `Power Supply, Redundant, 900W`
    - `UOM`: `EA`
    - `Qty Required`: `2`
    - `Vendor Name`: `Sterling Computers`
    - `Shopping Cart`: `PR 0031126723`

- `rpusTransfr\verified\IGS\1.0 enterprise program DM - Restricted\SEMS3D\A001-PSIP\A001-ISTO_Initial_Spares\SEMS3D-37218 legacy monitoring system Spares.xlsx` `dae52721763ab1230b1d90014cc54d2_pipekv_1` row=0
    - `Date Received TO`: `WX31M4`
    - `Requirement`: `BOM`
    - `Line Item`: `35`
    - `Quote #`: `Q000X5B6`
    - `Site`: `Material Buydown legacy monitoring system Spares Kit`
    - `Part Number`: `DGXZ +36NFNF-A`

### T-04 — How many PR Number rows were captured from the PR & PO spreadsheet?

- `D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl\2024 01 PR & PO.xlsx` `0f105b2e4bd7477385d61cf4355957_kvtable_2` row=0
    - `LOE`: `Matl`
    - `CLIN`: `0002A`
    - `Network`: `NA1A26703400`
    - `PR Number`: `0031409028`
    - `PO Number`: `5000352661`
    - `Shopping Cart Number`: `0015917815`

- `D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl\2024 01 PR & PO.xlsx` `0f105b2e4bd7477385d61cf4355957_kvtable_2` row=1
    - `LOE`: `Matl`
    - `CLIN`: `0002A`
    - `Network`: `NA1A26703400`
    - `PR Number`: `0031409307`
    - `PO Number`: `5000354293`
    - `Shopping Cart Number`: `0015919472`

### T-05 — How many rows were captured from Initial Spares sources?

- `enterprise program DM - Restricted\SEMS3D\Non-CDRL Deliverables\legacy monitoring system monitoring system Initial Spares\SEMS3D-37125 monitoring system-legacy monitoring system Initial Spares.xlsx` `ff18052e69344ad42a676a103f7c22_kvtable_1` row=0
    - `er`: `2002 Q3`
    - `Esc Value`: `143.066666666667`

- `enterprise program DM - Restricted\SEMS3D\Non-CDRL Deliverables\legacy monitoring system monitoring system Initial Spares\SEMS3D-37125 monitoring system-legacy monitoring system Initial Spares.xlsx` `ff18052e69344ad42a676a103f7c22_kvtable_2` row=0
    - `UOM`: `UN`
    - `UOM Description`: `Unit`
    - `Year & Quarter`: `2002 Q4`
    - `Esc Value`: `143.7`

### T-06 — Find the row for PR Number 0031393862.

- `D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl\2024 01 PR & PO.xlsx` `6c6b39c5a174ce833e4870e070d031_kvtable_2` row=1
    - `LOE`: `Matl`
    - `CLIN`: `0002A`
    - `Network`: `NA1A26703400`
    - `PR Number`: `0031393862`
    - `PO Number`: `5300045239`
    - `Shopping Cart Number`: `0015803502`

- `D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl\2024 01 PR & PO.xlsx` `36371c202fd227dd27055cf3891b624_pipekv_1` row=0
    - `Purchase Requisition Network Allocations`: `CLIN, : PR Number, : PR Number, : PO Number, : Requisition Date, : Network, : Network (Assigned), : `
    - `Allocation Amount in PO Currency`: `Matl`
    - `Purchase Requisition Network Allocations 2`: `0002A, : 0031393862, : 31393862, : 5300045239, :`
    - `00`: `00, : NA1A26703400, : NA1A26703400, : 0015803502, : 0004300011, : ##, : 0, : 211, :`
    - `40850`: `Matl`
    - `Purchase Requisition Network Allocations 3`: `0001A, : 0031394027, : 31394027, : 5000304558, :`

### T-07 — Confirm the pipe-joined extractor produced at least one row (table_id contains _pipekv_).

- `e Visits\(01) Sites\Alpena\2017-08-13 thru 08-18 (NEXION_ASV)(Brukardt-Pitts)\Spares Inventory (Alpena)_(2017-08-16).pdf` `07e9ceead9e8708c941b3673_inventory_table` row=0
    - `Description`: `Analog Telephone Device Returned to COS for LLL 16 Aug 2017`
    - `Part Number`: ``
    - `Qty`: `0`

- `e Visits\(01) Sites\Alpena\2017-08-13 thru 08-18 (NEXION_ASV)(Brukardt-Pitts)\Spares Inventory (Alpena)_(2017-08-16).pdf` `07e9ceead9e8708c941b3673_inventory_table` row=1
    - `Description`: `Antenna Switch   C 64`
    - `Part Number`: `AS-7020103`
    - `Qty`: `1`

### T-08 — Find spares rows for vendor Sterling Computers.

- `rpusTransfr\verified\IGS\1.0 enterprise program DM - Restricted\SEMS3D\A001-PSIP\A001-ISTO_Initial_Spares\SEMS3D-37218 legacy monitoring system Spares.xlsx` `80936a3841efbca70951adb1a8056c_kvtable_1` row=0
    - `Part Description`: `Power Supply, Redundant, 900W`
    - `UOM`: `EA`
    - `Qty Required`: `2`
    - `Vendor Name`: `Sterling Computers`
    - `Shopping Cart`: `PR 0031126723`

- `rpusTransfr\verified\IGS\1.0 enterprise program DM - Restricted\SEMS3D\A001-PSIP\A001-ISTO_Initial_Spares\SEMS3D-37218 legacy monitoring system Spares.xlsx` `80936a3841efbca70951adb1a8056c_kvtable_2` row=0
    - `TO`: `WX31M4`
    - `Requirement`: `BOM`
    - `Line Item`: `38`
    - `Quote #`: `Q-00191352`
    - `Site`: `Material Buydown legacy monitoring system Spares Kit`
    - `Part Number`: `820306-B21`
