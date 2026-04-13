# Tier 1 Regex Corpus Audit Rerun -- 2026-04-12

**Scope:** `PO` and `PART` only. Read-only mining of the live polluted store plus a fresh clean Tier 1 rerun store. This document defines the adversarial confusion set and the pre-rerun acceptance gate.

**Evidence basis:**

- live store: `data/index/entities.sqlite3`
- fresh clean Tier 1 rerun store: `data/index/tier1_clean_20260412/entities.sqlite3`
- source-path spot checks from procurement-heavy corpus roots
- repeatable helper: [`scripts/audit_tier1_regex_corpus.py`](/C:/HybridRAG_V2/scripts/audit_tier1_regex_corpus.py)

## Executive Summary

- `PO` in the live store is still almost entirely polluted by security-control collisions:
  - `147,562 / 150,602` rows (`97.98%`) match the control-family shape `IR-*`, `AC-*`, `PS-*`, `SA-*`, etc.
  - another `2,120` rows are `IR-*` lookalikes
  - the remaining `920` rows are report/site-visit/product tokens, not purchase orders
- `PART` in the live store still has two major pollution layers:
  - STIG / platform / MITRE style identifiers
  - lower-underscore security tokens and generic audit/status debris
- the clean Tier 1 rerun proves we do still preserve real procurement and hardware identifiers when the guardrails are right:
  - `PO` collapses to labeled SAP-style procurement IDs
  - `PART` keeps real cable, device, and model identifiers

## Exact False-Positive Families Still Poisoning `PO`

| Family | Live rows | Why it is false-positive |
|---|---:|---|
| `^(?:AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)-\d{1,2}(?:\(\d+\))?$` | `147,562` | security-control identifiers, not purchase orders |
| `^IR-[A-Z0-9_-]+$` | `2,120` | `IR-*` lookalikes, still non-procurement tokens |
| `^(?:FSR|UMR|ASV|RTS)-[A-Z0-9_-]+$` | `920` | report/site-visit/product tokens, not POs |

Concrete examples:

- `IR-8`, `IR-4`, `IR-9`, `IR-3`, `IR-6`, `IR-1`, `IR-2`, `IR-7`, `IR-5`, `IR-10`
- `IR-4A`, `IR-1N-04`
- `FSR-L22`, `FSR-461-M-USB`
- `ASV-VAFB`
- `RTS-DATA`

## Exact False-Positive Families Still Poisoning `PART`

| Family | Live rows | Why it is false-positive |
|---|---:|---|
| `^(?:AS|OS|GPOS|HS)-\d{3,5}$` | `909,064` | STIG / platform codes |
| `^CCI-\d+$` | `326,864` | control IDs |
| `^SV-\d+$` | `241,649` | STIG vulnerability IDs |
| `^CCE-\d+$` | `159,669` | config IDs |
| `^CVE-\d{4}` | `59,292` | vulnerability identifiers |
| `^[a-z0-9]+(?:_[a-z0-9]+)+$` | `73,505` | PAM / SELinux / config tokens |
| `^SERVICE_(?:START|STOP)$` | `39,696` | service-state events |
| `^(?:mode|NORMAL|failure|SNMP)$` | `37,828` | generic status/protocol words |
| `^RHSA-\d{4}` | `21,745` | advisories, not parts |
| `^STIG-\d{4}` | `3,812` | filename tags, not parts |
| `^APP-\d{4}$` | `13,616` | security requirement IDs in `SRG-APP-*` contexts |

Concrete examples:

- `pam_faillock`, `unconfined_u`, `unconfined_r`
- `SERVICE_START`, `SERVICE_STOP`
- `SNMP`, `mode`, `NORMAL`, `failure`
- `RHSA-2018`
- `APP-0001`, `APP-0003`, `APP-0004`
- phrase debris such as `single-user mode`, `information system shutdown`, `most restrictive mode`, `compromise`, `disruption`, `Audit processing failure`

## Real Business Identifiers That Must Be Preserved

### `PO` preservation set

These are verified real procurement identifiers:

- `7000298452`
- `7000303468`
- `7000298625`
- `7000335923`
- `7000354180`
- `7000345588`
- `7000354926`
- `7200718189`
- `7201003835`
- `7500163791`

Clean rerun evidence shows explicit PO context such as:

- `NG PO 7000298452, Rcvd: 2016-07-07`
- `PO Number: 7200998755`
- `Prime Order No. (Hdr): PO 7500074564`

### `PART` preservation set

These are real hardware / inventory / BOM / manual identifiers:

- `RG-213`
- `LMR-400`
- `FGD-0800`
- `POL-2100`
- `PCE-4129`
- `RFN-1006`
- `SM-219`
- `SNAP-IN`
- `USHL-130`
- `PT-2700`
- `FGD-6700`
- `SNAP`
- `TK-423`
- `PS-110`
- `MRF-141`
- `WXD-601`
- `GPS-533`
- `MDT-0800`

The clean rerun store confirms these remain visible in context and are not just theoretical examples.

## Fresh Clean Tier 1 Rerun Cross-Check

The fresh clean Tier 1 rerun store contains `6,282,931` entity rows total. The relevant counts are:

- `PO`: `114,155`
- `PART`: `823,006`

Top values in the clean rerun are the same kind of identifiers we want to keep:

- `PO`: `7000298452`, `7000303468`, `7000298625`, `7000335923`, `7000354180`, `7000345588`, `7000354926`, `7000333299`, `7000354546`, `7000351459`, `7200718189`, `7201003835`, `7500163791`, `7500160462`
- `PART`: `RG-213`, `LMR-400`, `SNMP`, `FGD-0800`, `POL-2100`, `PCE-4129`, `RFN-1006`, `SM-219`, `SNAP-IN`, `USHL-130`, `PT-2700`, `FGD-6700`, `SNAP`, `TK-423`, `PS-110`, `MRF-141`, `WXD-601`, `GPS-533`, `MDT-0800`

This is the practical proof that the safe rejects below do not destroy the real business classes we need.

## Objective Sample Gate Before the Next Tier 1 Rerun

Run the helper first:

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_corpus.py --json
```

Require all of the following before trusting the rerun:

1. `PO` top values contain zero control-family collisions (`IR-*`, `AC-*`, `PS-*`, `SA-*`, etc.).
2. `PO` top values contain zero `IR-*` lookalikes and zero `FSR-*` / `UMR-*` / `ASV-*` / `RTS-*` pollution.
3. `PART` top values contain zero STIG / CCI / SV / CCE / CVE / RHSA / `STIG-*` pollution.
4. `PART` top values contain zero lower-underscore security tokens, service-state events, or generic debris tokens.
5. The preservation sentinels above still appear in the clean rerun store.

If the live post-rerun store still shows the same poisoned families, the rerun is not clean enough for honest aggregation claims.

## Safe Global Rejects vs Too-Risky Blocks

### Safe to reject globally at emit sites

- `^(?:AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)-\d{1,2}(?:\(\d+\))?$`
- `^(?:AS|OS|GPOS|HS)-\d{3,5}$`
- `^CCI-\d+$`
- `^SV-\d+$`
- `^CCE-\d+$`
- `^CVE-\d{4}`
- `^RHSA-\d{4}`
- `^STIG-\d{4}`
- `^[a-z0-9]+(?:_[a-z0-9]+)+$`
- `^SERVICE_(?:START|STOP)$`
- exact debris tokens: `SNMP`, `mode`, `NORMAL`, `failure`, `audit processing failure`, `single-user mode`, `most restrictive mode`, `information system shutdown`, `compromise`, `disruption`

### Too risky to block by prefix alone

- `PS-`
  - real part evidence: `PS-110`
  - only the security-control shape with 1-2 digit suffix is safe to reject
- `PT-`
  - real part evidence: `PT-2700`
- `RG-`, `LMR-`, `FGD-`, `POL-`, `PCE-`, `RFN-`, `SM-`, `TK-`, `MRF-`, `WXD-`, `GPS-`, `MDT-`
  - all have direct hardware / inventory evidence
- blanket numeric PO length rules
  - 10-digit labeled SAP POs are clearly real
  - 6-digit labeled legacy POs are real too
  - 8-digit numerics need context

## Residual Ambiguities

1. `FSR-*` is not safe to keep in `PO`, but it is not one clean family either.
   - `FSR-L22` is a part number.
   - other `FSR-*` tokens may be maintenance or report labels.
2. `SNMP`, `SNAP`, `mode`, and `failure` are ambiguous in isolation.
   - they show up as `PART` pollution in the live store.
   - do not globally reject their prefixes without more context.
3. Numeric procurement identifiers are not one-size-fits-all.
   - 10-digit labeled POs are common and clearly real.
   - 6-digit labeled legacy POs are also real.
   - 8-digit numeric labels need label/context.

## Rerunnable Helper

[`scripts/audit_tier1_regex_corpus.py`](/C:/HybridRAG_V2/scripts/audit_tier1_regex_corpus.py) is the read-only repeatable audit helper for this lane. It can be rerun before future Tier 1 attempts to refresh the confusion set from the current live store.
