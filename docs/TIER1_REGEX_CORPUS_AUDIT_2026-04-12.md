# Tier 1 Regex Corpus Audit -- 2026-04-12

**Scope:** `PO` and `PART` only. This is a read-only mining pass against the current V2 store plus procurement-heavy corpus paths. It is intended to define the adversarial sample gate for the next Tier 1 rerun.

**Evidence basis:**

- `data/index/entities.sqlite3` opened read-only
- `data/index/lancedb` FTS spot checks on real identifiers
- procurement path scan under:
  - `E:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement`
  - `E:\CorpusTransfr\verified\IGS\zzSEMS ARCHIVE\005_ILS\Purchases`
- rerunnable helper: [audit_tier1_regex_corpus.py](/C:/HybridRAG_V2/scripts/audit_tier1_regex_corpus.py)

## Executive Findings

1. `PO` is still almost entirely poisoned by control-family collisions in the current store.
   - `147,562 / 150,602` `PO` rows (`97.98%`) are control-family tokens like `IR-8`, `IR-4`, `IR-9`.
   - Another `2,120` rows (`1.41%`) are `IR-*` lookalikes such as `IR-4A` and `IR-1N-04`.
   - The remaining `920` rows (`0.61%`) are also not procurement truth; they are mostly report/site-visit/product tokens like `FSR-L22`, `ASV-VAFB`, `FSR-461-M-USB`, and `RTS-DATA`.

2. `PART` has two layers of pollution.
   - The already-known cyber identifier families are massive:
     - `AS|OS|GPOS|HS-\d{3,5}` = `909,064`
     - `CCI-\d+` = `326,864`
     - `SV-\d+` = `241,649`
     - `CCE-\d+` = `159,669`
     - `CVE-\d{4}` = `59,292`
   - There is also a second uncovered junk layer still living in the `PART` store:
     - lower-underscore cyber tokens like `pam_faillock`, `unconfined_u`, `unconfined_r` = `73,505`
     - `SERVICE_START` / `SERVICE_STOP` = `39,696`
     - generic cyber/status words `SNMP`, `mode`, `NORMAL`, `failure` = `37,828`
     - `RHSA-\d{4}` advisories = `21,745`
     - `APP-\d{4}` security requirement IDs = `13,616`
     - phrase-level cyber/status debris like `single-user mode`, `information system shutdown`, `disruption`, `compromise`, `Audit processing failures` = `21,805`

3. The real business identifiers are still clearly visible and should be used as preservation sentinels.
   - Strong `PO` truth is numeric and explicitly labeled in context.
   - Strong `PART` truth is hardware/procurement language in BOMs, packing lists, manuals, quotes, and warehouse/property books.

## Exact False-Positive Families Remaining

### PO

| Family | Rows | Why it is false-positive in `PO` |
|---|---:|---|
| `IR-\d{1,2}(\(\d+\))?` and the other control-family shapes | `147,562` | security control IDs, not purchase orders |
| `IR-*` lookalikes such as `IR-4A`, `IR-1N-04`, `IR-7802` | `2,120` | still non-procurement tokens; current store never shows them as labeled purchase orders |
| `FSR-*`, `ASV-*`, `RTS-*`, `UMR-*` | `920` | wrong semantic class for `PO`; examples resolve to report/site-visit labels or even part numbers |

Concrete evidence:

- `FSR-L22` occurs in a logistics quote and procurement path, but the context is `Mechatronics Fan Group E9225E24B-FSR-L22`; this is a fan part number, not a purchase order.
- `FSR-461-M-USB` occurs as `JCR PART NUMBER: SK-102-FSR-461-M-USB`; again a part number, not a purchase order.
- `ASV-VAFB` resolves to site-visit / movement-form contexts, not procurement.
- `RTS-DATA` resolves to a cyber data-service string, not procurement.

### PART

| Family | Rows | Why it is false-positive in `PART` |
|---|---:|---|
| `AS|OS|GPOS|HS-\d{3,5}` | `909,064` | STIG baseline / platform codes |
| `CCI-\d+` | `326,864` | DISA control IDs |
| `SV-\d+` | `241,649` | STIG vulnerability IDs |
| `CCE-\d+` | `159,669` | MITRE configuration IDs |
| `CVE-\d{4}` | `59,292` | vulnerability identifiers, not parts |
| `pam_faillock`, `unconfined_u`, `unconfined_r`, similar lowercase underscore tokens | `73,505` | SELinux/PAM/security config tokens |
| `SERVICE_START`, `SERVICE_STOP` | `39,696` | service-state events from audit logs |
| `SNMP`, `mode`, `NORMAL`, `failure` | `37,828` | generic protocol/status words |
| `RHSA-\d{4}` | `21,745` | Red Hat security advisory IDs |
| `APP-\d{4}` | `13,616` | security requirement IDs like `SRG-APP-000014` |
| `single-user mode`, `information system shutdown`, `most restrictive mode`, `compromise`, `disruption`, `Audit processing failures` | `21,805` | prose fragments from cyber controls and audit narratives |

Concrete evidence:

- `pam_faillock` comes from `A027 - Cybersecurity Assessment Test Report-RHEL 8 ISTO`.
- `unconfined_u` and `unconfined_r` come from `...Monthly Audits-Archive...audit.log`.
- `RHSA-2018` appears in scan result titles like `RHEL 6 / 7 : microcode_ctl (RHSA-2018:0093)`.
- `APP-0001` / `APP-0003` / `APP-0004` appear as `SRG-APP-000014`, `SRG-APP-000231`, etc.

## Strongest Real-Positive Business Identifiers To Preserve

### PO preservation set

These were verified from live chunk text or procurement-heavy path evidence:

| Token | Why it matters |
|---|---|
| `7000372377` | live chunk says `Purchase Order No. 7000372377`; clean SAP-style procurement ID |
| `7200751620` | live chunk says `Catalog PO Number: 7200751620`; procurement ID in shopping-cart approval artifact |
| `268235` | live chunk says `Purchase Order: 268235`; real legacy procurement ID |
| `250802` | procurement archive artifact `PO 250802 Micro Metals.pdf`; legacy procurement family |
| `5000696458` | live chunk says `ACQUISITION DOCUMENT NUMBER (PO): 5000696458`; modern logistics spreadsheet evidence |
| `5300168230` | live chunk says `Customer PO #: 5300168230`; modern procurement evidence |

Important nuance:

- Procurement path scan found **656** unique numeric `PO` labels.
- Length mix in filenames is not single-family:
  - 6 digits: `125`
  - 8 digits: `6`
  - 10 digits: `5,352` path matches
- At least one 8-digit case is ambiguous: `15404062` appears under a `PO`-labeled folder, but the live chunk says `Not a Purchase Order ... iBuy Order Receipt Number: 15404062`. Do not treat all 8-digit numerics as safe PO truth.

### PART preservation set

These all resolve to real hardware / inventory / BOM / manual contexts:

| Token | Evidence |
|---|---|
| `RG-213` | coax cable in BOMs and quotes |
| `LMR-400` | RF cable in troubleshooting guides and maintenance reports |
| `FGD-0800` | Sensaphone autodialer in property books and quotes |
| `POL-2100` | obstruction-light family in system manuals |
| `PCE-4129` | Advantech data computer model in manuals and quotes |
| `PT-2700` | Brother label printer in shipment lists and price schedules |
| `TK-423` | TRENDnet KVM model in manuals |
| `PS-110` | Power-Out Alert hardware in manuals |
| `MRF-141` | MOSFET device in maintenance manuals |
| `DBZH-101` | humidistat data-sheet / COTS-manual token |

These are the strongest proof that simple shape-based rejection is too coarse. Real parts in this corpus include:

- short alpha prefixes plus 3-4 digits: `PS-110`, `PT-2700`, `TK-423`
- RF cable families: `RG-213`, `LMR-400`
- vendor/device models embedded in manuals and quotes: `PCE-4129`, `FGD-0800`, `MRF-141`

## Safe Global Rejects vs Too-Risky Blocks

### Safe to reject globally at `PO` / `PART` emit sites

- `^(AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)-\d{1,2}(\(\d+\))?$`
- `^(AS|OS|GPOS|HS)-\d{3,5}$`
- `^CCI-\d+$`
- `^SV-\d+$`
- `^CCE-\d+$`
- `^CVE-\d{4}`
- `^RHSA-\d{4}`
- `^APP-\d{4}$` when it is part of `SRG-APP-*` / control contexts
- `^[a-z0-9]+(?:_[a-z0-9]+)+$`
- `^SERVICE_(START|STOP)$`
- exact cyber/status debris:
  - `SNMP`
  - `mode`
  - `NORMAL`
  - `failure`
  - `audit processing failure`
  - `single-user mode`
  - `most restrictive mode`
  - `information system shutdown`
  - `compromise`
  - `disruption`

### Too risky to block by prefix alone

- `PS-`
  - real part evidence: `PS-110`
  - security-family collision exists only on **1-2 digit** suffix controls like `PS-1`
- `PT-`
  - real part evidence: `PT-2700`
  - same suffix-length caution as `PT-1`
- `RG-`, `LMR-`, `FGD-`, `POL-`, `PCE-`, `TK-`, `MRF-`, `DBZH-`
  - all have direct business-hardware evidence
- blanket numeric PO length blocks
  - 6-digit labeled procurement IDs exist (`268235`, `250802`)
  - 10-digit labeled procurement IDs dominate modern procurement
  - 8-digit numeric procurement-adjacent IDs are ambiguous and need label/context, not blanket allow
- blanket `FSR-`, `UMR-`, `ASV-`, `RTS-` allow rules in `PO`
  - current store shows these are wrong for `PO`
  - some are report/site-visit labels, others are embedded part numbers

## Recommended Sample Gate Before Trusting The Next Rerun

Run [audit_tier1_regex_corpus.py](/C:/HybridRAG_V2/scripts/audit_tier1_regex_corpus.py) immediately after the rerun and block signoff unless all of these are true:

### Gate A -- hard rejects absent from the top ranks

- `PO` top 20 exact values contain **zero** matches from:
  - control-family shapes
  - `IR-*` lookalikes
  - `FSR-*`, `UMR-*`, `ASV-*`, `RTS-*`
- `PART` top 30 exact values contain **zero** matches from:
  - STIG/CCI/SV/CCE/CVE/RHSA families
  - lowercase underscore cyber tokens
  - `SERVICE_START` / `SERVICE_STOP`
  - `APP-*`
  - the phrase/status debris listed above

### Gate B -- preservation sentinels survive

- `PO` exact matches must include all of:
  - `7000372377`
  - `7200751620`
  - `268235`
  - `250802`
  - `5000696458`
  - `5300168230`
- `PART` exact matches must include all of:
  - `RG-213`
  - `LMR-400`
  - `FGD-0800`
  - `POL-2100`
  - `PCE-4129`
  - `PT-2700`
  - `TK-423`
  - `PS-110`
  - `MRF-141`
  - `DBZH-101`

### Gate C -- manual context spot check

Manual review only needs 20 rows total if the helper output is already clean:

- 10 `PO` rows:
  - 5 from the preservation set above
  - 5 from the top-frequency `PO` values after rerun
- 10 `PART` rows:
  - 5 from the preservation set above
  - 5 from the top-frequency `PART` values after rerun

Pass only if every reviewed row still reads as the right business class in context.

## Residual Ambiguities

1. `FSR-*` is not safe to keep in `PO`, but it is not one clean family either.
   - `FSR-L22` is a part number.
   - other `FSR-*` tokens may be maintenance/report labels.
   - conclusion: remove it from `PO`, but do not assume it belongs to one replacement class without more type work.

2. Some `PART` lookalikes are still ambiguous by prefix alone.
   - `WXD-601` currently resolves to hostname strings, not hardware.
   - that is enough to reject the specific token family in this corpus only if a later lane validates the whole prefix family.
   - it is not strong enough yet to declare every `WXD-*` globally invalid.

3. Numeric procurement identifiers are not one-length-fits-all.
   - 10-digit labeled POs are common and clearly real.
   - 6-digit labeled legacy POs are also real.
   - 8-digit numeric labels need context because at least one current corpus example is an order receipt, not a PO.

## Concrete Confusion Sets

### Hard-reject confusion set

- `PO`: `IR-8`, `IR-4`, `IR-9`, `IR-3`, `IR-6`, `IR-1`, `IR-2`, `IR-7`, `IR-5`, `IR-10`, `IR-4A`, `IR-1N-04`, `FSR-L22`, `FSR-461-M-USB`, `ASV-VAFB`, `RTS-DATA`
- `PART`: `AS-5021`, `OS-0004`, `GPOS-0022`, `CCI-0003`, `SV-2045`, `CCE-8043`, `CVE-2018`, `RHSA-2018`, `pam_faillock`, `unconfined_u`, `SERVICE_STOP`, `SNMP`, `APP-0001`, `single-user mode`

### Preserve confusion set

- `PO`: `7000372377`, `7200751620`, `268235`, `250802`, `5000696458`, `5300168230`
- `PART`: `RG-213`, `LMR-400`, `FGD-0800`, `POL-2100`, `PCE-4129`, `PT-2700`, `TK-423`, `PS-110`, `MRF-141`, `DBZH-101`
