# Logistics Path-Shape Memo -- 2026-04-13

**Scope:** read-only analysis of the clean Tier 1 baseline, focused on the remaining Logistics exact-ID / path-heavy misses after the current shipment + CDRL path work.

**Primary evidence:** `docs/production_eval_results_clean_tier1_2026-04-13.json`

## Bottom Line

The remaining Logistics problems are not random retrieval failures. They cluster around a small set of path shapes that already exist in the corpus:

- PO status / procurement lookups
- DD250 / transfer-equipment forms
- open / received procurement folders
- parts catalogs / COTS manuals / spares docs
- coax / cable / shipment / return-shipping terms

The clean baseline already shows the right family in top-5 for every Logistics `PARTIAL` row. That means the next gain is mostly **ranking**, not broad recall. The true `MISS` rows are the cases where the family never enters top-5, and those are the rows that need stronger path hints and exact-ID anchoring.

## Exact Path Shapes That Keep Reappearing

These are the master-compatible path patterns actually observed in the current corpus:

### PO status / received procurement

- `5.0 Logistics\\Procurement\\002 - Received\\1-Received\\WX29 (PO 7000372377)(Newark)(RG-58 Cable)($388.24)Rcvd 2019-04-08\\PO 7000372377.pdf`
- `5.0 Logistics\\Procurement\\002 - Received\\1-Received\\WX39 (PO 7000367469)(Newark)(RG-213 1000')($2,204.09)rcvd 2019-02-13\\PO 7000367469.pdf`
- `5.0 Logistics\\Procurement\\001 - Open Purchases\\Soldering Material COCO1\\Received\\PO - 5000665726, PR 3000187518 Solvents\\PO 5000665726 - 01.27.2026 - Lines 1-2 (P).pdf`
- `zzSEMS ARCHIVE\\005_ILS\\Purchases\\Archive\\monitoring system Purchases Rcvd (PO Type) (ARINC-BAH)\\2011 PRs\\PR 121401 (R) (LDI) (Sys 06-08 Plus Sys 30) (DPS-4D - Spares)\\PR 121401 (LDI) (PO 250788).pdf`
- `zzSEMS ARCHIVE\\005_ILS\\Purchases\\Archive\\monitoring system Purchases Rcvd (PO Type) (ARINC-BAH)\\2011 PRs\\PR 121414 (R) (TCI) (3 Each Towers-Antennas)\\PR 121414 (TCI) (PO 1st Sent).pdf`
- `zzSEMS ARCHIVE\\005_ILS\\Purchases\\Archive\\monitoring system Purchases Rcvd (PO Type) (ARINC-BAH)\\2014 PRs\\PR 396307 (B&H Photo) (500GB Hard Drives)\\BH_478322790.pdf`

### DD250 / transfer forms

- `1.0 enterprise program DM - Restricted\\OASIS\\A004 - Technical Report – DD250 (Transfer Equipment to Government)\\Deliverables Report IGSI-443 A004 Technical Report DD250 (Transfer Equipment to Government) Niger.zip`

### Shipping / return-shipping / hand-carry

- `! Site Visits\\(01) Sites\\San Vito\\2022-02-02 thru 02-09 (RTS)(Seagren-Dexter)\\Shipping and Hand-Carry\\Return Shipping List.docx`
- `! Site Visits\\(01) Sites\\San Vito\\2022-02-02 thru 02-09 (RTS)(Seagren-Dexter)\\Shipping and Hand-Carry\\Packing List.docx`
- `monitoring system\\Documents and Forms\\DOCUMENTS LIBRARY\\Shipping\\industry standardP_NOT_1.pdf`
- `monitoring system\\Documents and Forms\\DOCUMENTS LIBRARY\\Archive\\PHS&T\\industry standardP w Chg 3.pdf`
- `monitoring system\\Documents and Forms\\DOCUMENTS LIBRARY\\industry standardP w Chg 3 (industry Standard Practice) (Military Marking for Shipment and Storage) (2004-10-29).pdf`
- `zzSEMS ARCHIVE\\005_ILS\\Shipping\\Shipping Mode Information - T-TAC Account\\enterprise Transportation Regulation-Part ii\\dtr_part_ii_205.pdf`
- `zzSEMS ARCHIVE\\005_ILS\\Shipping\\2018 Completed\\2018-04-25(WX28)(NG-Upgrade Kits & Tower Parts)(NG to Patrick)(2936.21)\\Archive\\DD Form 1149 3of3 TCN FB25008115X503XXX (2018-04-25) (Signed).pdf`

### Parts catalogs / spares / coax / cable

- `1.5 enterprise program CDRLS\\A041 - Commercial-Off-the- Shelf (COTS) Manuals and Supplemental Data\\legacy monitoring system\\legacy monitoring system COTS Manuals\\P240-270VDG Preamplifier Data Sheet.pdf`
- `1.5 enterprise program CDRLS\\A054 - Trouble Shooting Aids and Guides\\47QFRA22F0009_ IGSI-1140_OY1_IGS_Troubleshooting_Aides_Guides-ISTO_2024_06_26.docx`
- `3.0 Cybersecurity\\archive\\VPN-GFE_Laptops\\Archive\\003.1_Document_Management\\01_Document_Templates\\Critical_Spares_Reports\\SEMS3D-xxxxx legacy monitoring system Critical Spares Planning Estimate (A001).docx`
- `1.0 enterprise program DM - Restricted\\SEMS3D\\A001-Critical_Spares_Reports\\A001 - WX31 Critical Spares Planning Estimate\\SEMS3D-36712 Critical Spares Planning Estimate (A01).docx`
- `zzSEMS ARCHIVE\\005_ILS\\Government_Property\\monitoring system GFP_GFE\\Archive\\User Manual for RedBeam Asset Tracking v5 5.pdf`
- `zzSEMS ARCHIVE\\005_ILS\\Export_Control\\legacy monitoring system Jurisdiction and Classification Requests\\MS-JC-17-01498 (Fieldfox RF Analyzer) (N9913A) (Keysight)\\KT Data Sheet (N9913A) (5990-9783EN).pdf`

## Strongest Path Terms

These are the path tokens that show up repeatedly in Logistics misses/partials and are worth keeping as ranking hints:

- `PO`
- `PR`
- `shipment`
- `received`
- `shipments`
- `shipping and hand-carry`
- `return shipping list`
- `packing list`
- `procurement`
- `open purchases`
- `purchase order`
- `critical spares`
- `spares`
- `parts (downloaded information)`
- `cable`
- `coax`
- `RG-`
- `LMR-`
- `DD250`
- `industry standard`
- `catalog`
- `asset tracking`

In the miss/partial top-5 paths, the most common terms were:

- `PO` / `po` and `PR`
- `shipment` / `shipments`
- `received`
- `shipping and hand-carry`
- `RG-`
- `spares`
- `cable`
- `procurement`
- `return shipping list`
- `packing list`
- `critical spares`
- `industry standard`
- `open purchases`
- `purchase order`
- `DD250`

## Main Noise Traps

These are high-frequency path tokens that are useful for corpus navigation but too broad to trust on their own:

- `enterprise program`
- `monitoring system`
- `legacy monitoring system`
- `SEMS3D`
- `OASIS`
- `Archive`
- `DM_Backup`
- `5.0 Logistics`
- `1.0 enterprise program DM - Restricted`
- `! Site Visits`
- `Documents and Forms`
- `DOCUMENTS LIBRARY`
- `manifest_20180523.txt`
- `A031`
- `A023`
- `A041`
- `A054`

They often appear in the right answer family, but they are not selective enough to solve a Logistics query by themselves.

## What The Clean Baseline Says About Ranking

For Logistics:

- `PASS`: `16`
- `PARTIAL`: `36`
- `MISS`: `49`

The important split is:

- every `PARTIAL` already has the right family in top-5
- every `MISS` does not

That means the smallest good lever is not a new broad retriever. It is a path-aware ranking nudge that favors the right folder shape when the query is obviously Logistics-heavy.

## Smallest Retrieval / Path-Hint Recommendations

### 1. Boost exact Procurement / PO status paths for PO queries

When the query contains a PO number, `purchase order`, `open purchase`, `received`, `status`, `order`, `vendor`, or `PR`, candidates under these shapes should get a ranking bump:

- `5.0 Logistics\\Procurement\\001 - Open Purchases\\...`
- `5.0 Logistics\\Procurement\\002 - Received\\1-Received\\...`
- `zzSEMS ARCHIVE\\005_ILS\\Purchases\\Archive\\monitoring system Purchases Rcvd (PO Type) (ARINC-BAH)\\...`
- filenames containing:
  - `PO `
  - `PO-`
  - `Purchase Order`
  - `PO Type`
  - `Rcvd`
  - `Received`
  - `PR `

### 2. Boost DD250 / transfer-form paths when DD250 is present

If the query mentions `DD250`, `DD Form 250`, `transfer equipment`, or `Government`, prioritize:

- `A004 - Technical Report – DD250 (Transfer Equipment to Government)`
- filenames containing `DD250`, `DD Form 250`, or `Transfer Equipment to Government`

### 3. Boost parts-catalog / spares / cable paths for inventory questions

If the query mentions `parts catalog`, `spares`, `coax`, `cable`, `RG-`, `LMR-`, `inventory`, or `AssetSmart`, prioritize:

- `Parts (Downloaded Information)`
- `Critical_Spares_Reports`
- `COTS Manuals and Supplemental Data`
- `Government_Property\\monitoring system GFP_GFE`
- `Shipping` / `Procurement` folders that also contain `RG-` / `LMR-` / `cable` / `spares`

### 4. Keep shipping / return-shipping terms paired with their real folder shapes

Queries with `shipping`, `shipment`, `return shipping`, `packing list`, or `hand-carry` should prefer:

- `Shipping and Hand-Carry`
- `Return Shipping List.docx`
- `Packing List.docx`
- `industry standardP` / `industry standardN`
- `Shipment Confirmation`
- `DD Form 1149`

## Master-Compatible Path Hints

The following are the shortest stable hints worth feeding into retrieval or reranking:

- `Procurement`
- `Received`
- `Open Purchases`
- `PO`
- `PR`
- `Purchase Order`
- `DD250`
- `Shipping and Hand-Carry`
- `Return Shipping List`
- `Packing List`
- `Critical_Spares_Reports`
- `COTS Manuals`
- `RG-`
- `LMR-`
- `cable`
- `coax`
- `spares`

## Recommendation In One Line

For the next retrieval step, keep the corpus-wide search broad, but make the reranker path-aware for Logistics and let exact IDs pull toward:

- `Procurement / Received / Open Purchases`
- `DD250 / Technical Report – DD250`
- `Shipping and Hand-Carry / Return Shipping List / Packing List`
- `Critical_Spares_Reports / COTS Manuals / Government_Property`

That should move the remaining Logistics misses more cheaply than broad retriever churn.
