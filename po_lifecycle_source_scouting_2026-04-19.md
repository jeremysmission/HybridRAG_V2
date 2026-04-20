# PO-Lifecycle Source Scouting -- 2026-04-19

**Owner:** Agent B  
**Repo:** `C:\HybridRAG_V2`  
**Scope:** identify the smallest raw-corpus source families that can support a deterministic `ordered -> received -> shipped/arrived -> outstanding/as-of` substrate.

## Evidence Base

- `docs/lane2_family_recon_2026-04-13.json`
- `docs/lane2_family_samples_2026-04-13.json`
- `docs/LANE2_LOGISTICS_TABLE_FOLLOWON_EVIDENCE_2026-04-13.md`
- `docs/LOGISTICS_PATH_SHAPE_MEMO_2026-04-13.md`
- `docs/retrieval_app_path_probe_2026-04-11.json`

## Bottom Line

The cleanest first unlock is not "all logistics." It is a narrow three-family stack:

1. `PR & PO` spreadsheets for order-plane truth
2. `Procurement / Received` PO folders for receipt-plane truth
3. `Shipping Tracker` plus selective packing-slip / packing-list families for shipment and arrival hints

Those three families already show real corpus coverage, stable path shapes, and usable join keys. They are strong enough to support a bounded deterministic milestone without waiting for broad OCR or Pass-2 extraction.

## Recommended Priority

| Priority | Family | Why it matters |
|---|---|---|
| 1 | `PR & PO` spreadsheets | Best structured source for `po_orders`; already yields deterministic rows with `PO Number`, `PR Number`, `Network`, `Shopping Cart Number` |
| 2 | `Procurement / Received` PO folders | Best receipt evidence for `po_receipts`; filenames and folder names carry PO number, vendor, received date, and often item clues |
| 3 | `Shipping Tracker` / targeted packing docs | Best downstream shipment evidence for `po_shipments`; useful for `as_of` and received-vs-shipped reasoning once PO rows exist |
| 4 | `Space Report` spreadsheets | Useful upstream PR aging / release-status family, but secondary until PO and receipt joins are stable |
| 5 | `DD250` / transfer forms | Valuable delivery evidence, but sparse and not the fastest first unlock |

## Phase 1 Families

### 1. `PR & PO` spreadsheets

**Observed family signal**

- Needle count: `PR & PO` = `25,115` chunks in `docs/lane2_family_recon_2026-04-13.json`
- Real sample path:
  - `D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl\2024 01 PR & PO.xlsx`
- Existing staged substrate evidence:
  - `received_po` family produced `67,476` rows in the 30k-chunk pilot
  - exact `PO Number` and `PR Number` lookups already passed in the staged tabular eval

**Fields already observed**

- `PO Number`
- `PR Number`
- `CLIN`
- `Network`
- `Shopping Cart Number`
- `Requisition Date`
- `Allocated Quantity`
- `Allocation Amount in PO Currency`

**Why this is first**

- Most structured family in the repo for order creation and PR-to-PO joins
- Strong natural keys for `po_orders`
- Already proven compatible with the deterministic tabular substrate

**Phase-1 use**

- Seed `po_orders`
- Join `PR Number -> PO Number -> Network -> Shopping Cart`
- Support "ordered", "open PO", and some early "outstanding" reasoning

### 2. `Procurement / Received` PO folders

**Observed family signal**

- Needle counts:
  - `Received` = `30,525`
  - `Rcvd` = `20,875`
  - `Purchase Order` = `367`
  - `PO.xls` = `20,229`
- Real path shapes from repo evidence:
  - `5.0 Logistics\Procurement\002 - Received\1-Received\WX29 (PO 7000372377)(Newark)(RG-58 Cable)($388.24)Rcvd 2019-04-08\PO 7000372377.pdf`
  - `5.0 Logistics\Procurement\001 - Open Purchases\...\Received\PO 5000665726 - 01.27.2026 - Lines 1-2 (P).pdf`
  - `zzSEMS ARCHIVE\005_ILS\Purchases\2-Received\1-Received\WX39 (PO 7200753121)(Grainger)($143.33)\Packing Slip 2_PO 7200753121_Rcvd 2018-12-06.pdf`
  - `zzSEMS ARCHIVE\005_ILS\Purchases\2-Received\1-Received\WX29 (PO 7000327416)...\PO 7000327416 (...).pdf`

**Fields and signals already visible**

- PO number in folder and filename
- Vendor in folder name
- Received date in folder or filename
- product / part hints in folder name
- receipt / packing slip / notes variants inside the same PO folder

**Why this is second**

- Best source family for `po_receipts`
- Even when OCR text is weak, the path itself often carries deterministic receipt metadata
- Natural bridge from order-plane rows to receipt-plane evidence

**Phase-1 use**

- Seed `po_receipts`
- Extract `po_number`, `vendor`, `received_date`, `source_path`, `receipt_doc_type`
- Mark received/open state when joined against `po_orders`

### 3. `Shipping Tracker` plus targeted packing docs

**Observed family signal**

- Needle counts:
  - `Shipment` = `961,126`
  - `Shipping` = `392,182`
  - `Packing List` = `1,499,085`
  - `Packing Slip` = `1,019`
- Real path shapes from repo evidence:
  - `zzSEMS ARCHIVE\005_ILS\Dashboard\Shipping Tracker.xlsx`
  - `! Site Visits\...\Shipping and Hand-Carry\Packing List.docx`
  - `5.0 Logistics\Parts (Downloaded Information)\...\PR 141985 (Ethernet Extender Kit) (Packing Slip).pdf`
  - `...Packing Slip (OB Light Xfer Relay) (Rcvd 2017-12-08).pdf`

**Fields and signals already visible**

- tracking number
- ship-to / ship-from
- shipment type
- estimated ship date
- date arrived
- PO references on some packing slips
- item descriptions and quantities on some packing documents

**Why this is third**

- Best candidate for shipment-plane facts after `po_orders` and `po_receipts` exist
- `Shipping Tracker.xlsx` appears to carry arrival-state columns directly
- Packing-slip / packing-list docs provide PO-linked evidence for specific shipments

**Phase-1 use**

- Seed `po_shipments` or a lighter `shipment_events` helper table
- Support `as_of` and `received/not received` reasoning when joined to orders and receipts

## Supporting Families Worth Keeping Nearby

### `Space Report`

Useful as an upstream control-plane family, not the first receipt/shipment substrate.

- Needle count: `17,602`
- Real sample path:
  - `10.0 Program Management\1.0 FEP\Matl\Space Report_2025.05.27.xlsx`
- Useful fields:
  - `PR Number`
  - `Release Status`
  - `Status Category`
  - `Aging Days`
  - `Network`

This family looks valuable for "open", "buyer RFQ/PO", and aged-outstanding views, but it should enrich `po_orders`, not replace it.

### `DD250`

Good delivery/acceptance evidence, but too sparse for the first deterministic unlock.

- Needle counts:
  - `DD250` = `612`
  - `DD 250` = `8`
- Staged substrate evidence:
  - `dd250` produced only `12` rows in the spares-targeted probe

Keep it in phase 2 once the order/receipt join is stable.

### `Calibration`

Contains PO references but is not a receipt family.

- Needle count: `Calibration` = `5,408`
- Real sample fields include `PurchaseOrder:5300043575`

This is useful as corroborating evidence that a PO funded work, not as the primary lifecycle substrate.

## Families To Avoid As First Unlocks

- Broad `Packing List` and broad `Shipment` by needle alone:
  - counts are large, but selectivity is poor
  - these need path-shape narrowing or existing PO joins to stay deterministic
- General `Inventory`:
  - count is high (`268,006`) but the family is too broad for first PO-lifecycle work
- Archive-heavy historical folders without current join keys:
  - useful later for coverage, bad first-step substrate

## Smallest Deterministic Build Order

1. Build `po_orders` from `PR & PO` spreadsheets.
2. Build `po_receipts` from `Procurement / Received` PO folders and packing-slip variants.
3. Add `shipment_events` from `Shipping Tracker.xlsx` and narrow packing-list / packing-slip families.
4. Derive `outstanding` and `as_of` views from joins across those three tables.

## Suggested Initial Join Keys

- `po_number`
- `pr_number`
- `shopping_cart`
- `network`
- `vendor`
- `received_date`
- `ship_to`
- `date_arrived`
- `source_path`

## Recommendation

Do not start with a broad "all logistics" extractor. Start with:

- `PR & PO.xlsx`
- `Procurement / Received` PO folders
- `Shipping Tracker.xlsx`

That is the smallest honest path to deterministic PO-lifecycle answers with bounded scope and real corpus evidence.

Signed: Agent B
