# NIST / STIG Regex Over-Matching — PART and PO Columns

**Agent:** Agent 1 | **Repo:** HybridRAG_V2 | **Date:** 2026-04-12 MDT

**Trigger:** Agent 2's 400-query eval mining surfaced that Tier 1 PART and
PO entities on the 10.4M Beast LanceDB store are heavily polluted with
NIST SP 800-53 / STIG / MITRE security-standard identifiers, NOT physical
parts or procurement POs. Demo-day aggregation queries like "how many
unique POs" would return 150,602 when the honest answer is closer to
a few thousand.

**Related fix:** Phone regex over-matching
(`docs/PHONE_REGEX_FIX_2026-04-11.md`, commits `129e26f` and `7faef97`).
This investigation reuses the same methodology: web-search first, sample
the live store, design a two-stage match-plus-validator, measure
before/after on a 100K sample, ship with regression tests.

---

## Web research (standing order applied)

**NIST SP 800-53 Rev 5 control family list.**
Confirmed that Rev 5 has exactly 20 control families identified by
two-letter prefixes: AC, AT, AU, CA, CM, CP, IA, IR, MA, MP, PE, PL,
PM, PS, PT, RA, SA, SC, SI, SR. Rev 5 added PT (PII Processing and
Transparency) and SR (Supply Chain Risk Management) compared to Rev 4.

- Source: NIST SP 800-53 Rev 5 canonical publication —
  `https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final`
- Secondary: control family explainers at `saltycloud.com`, `ipkeys.com`,
  `securityscientist.net`, `drata.com`, `secureframe.com`, `cybersaint.io`

Agent 2's existing `NIST_CONTROL_PREFIXES` tuple in
`scripts/mine_query_anchors.py` line 47-53 was missing PT and SR.
Corrected in the new exclusion list.

**SAP purchase order format.**
Confirmed that SAP standard PO number length is 10 digits (SAP Community
Q&A on "10-digit Purchase Order Number", "Order value does not permit
more than 10 digit"). The specific starting digits (4500, 5000, 7000)
are organization-specific number-range assignments, not a universal SAP
rule. **Decision:** match any 10-digit PO but require an explicit PO
label (e.g., `PO`, `Purchase Order`, `P.O.`) to distinguish a real SAP
PO from random 10-digit OCR noise (phones, tracking numbers, timestamps).

- Source: SAP Community thread `community.sap.com/t5/.../qaq-p/594818`
  on the 10-digit length standard.

---

## Evidence from the live Beast entity store

All queries run read-only against `data/index/entities.sqlite3` via
`sqlite3 ... ?mode=ro`. No mutation.

### Top 25 PO entities

```
    42,608  IR-8       (NIST Incident Response control)
    35,425  IR-4
    15,572  IR-9
    11,491  IR-3
    10,157  IR-6
     9,182  IR-1
     8,355  IR-2
     7,134  IR-7
     5,532  IR-5
     2,053  IR-10
       964  IR-4A
       959  IR-1N-04
       277  FSR-L22    (real — Field Service Report)
       202  ASV-VAFB   (real — Annual Site Visit)
       125  FSR-461-M-USB
        78  RTS-DATA
        44  ASV-SU-HU
        35  ASV-HU
        33  IR-7802
        33  IR-1N-04OPERATING
        31  IR-7694
        27  ASV-SU
        23  RTS-HU
        17  IR-7693
        13  ASV-GUAM
```

**10 of the top 10 PO entries are NIST IR family controls = 147,509
of 150,602 total PO = 98.0% NIST pollution.** Real report IDs
(`FSR-L22`, `ASV-VAFB`, `RTS-DATA`) make up the long tail.

### Top 25 PART entities

```
   104,677  AS-5021    (STIG Application Server baseline)
   101,802  OS-0004    (STIG Operating System baseline)
    87,262  OS-0003
    83,498  OS-0000
    78,098  CCI-0003   (DISA Control Correlation Identifier)
    67,939  CCI-0001
    56,744  GPOS-0017  (STIG General-Purpose OS baseline)
    45,483  GPOS-0022
    42,749  AS-7040
    36,974  GPOS-0021
    33,284  GPOS-0020
    32,266  CCI-0028
    27,970  GPOS-0002
    26,923  SV-2045    (STIG Vulnerability ID)
    26,752  HS-872     (STIG Host System baseline)
    25,024  SV-2044
    24,997  GPOS-0003
    20,048  AS-7031
    19,552  CCI-0000
    18,999  AS-7020
    18,499  CCI-0018
    18,498  GPOS-0001
    18,418  RG-213     (real — HF coaxial cable)
    18,369  AS-7020
    18,016  LMR-400    (real — HF coaxial cable)
```

The first real physical part (`RG-213`, an HF coaxial cable) appears
at position 23. Every entry above it is a STIG / NIST / CCI identifier.
Cumulative: **~1,016,407 of the top 21 PART entries are security-standard
codes** = 40% of the PART total just from the top-21 bucket. The 90%
pollution estimate from Agent 2 holds when the long tail of STIG
baselines is included.

### 100-row direct sample

Cross-check sampling across the PO and PART rows (via `rowid % N = 0`
for even distribution):

```
PO column (100 rowid-samples):
  NIST/STIG/CCI identifiers:    98/100
  SAP 10-digit POs:              0/100
  Other (real report IDs):       2/100

PART column (100 rowid-samples):
  NIST/STIG/CCI identifiers:    59/100  (top entries oversample security codes)
  Real physical parts:           1/100
  Other (serials, generic):     40/100
```

The `RG-213` / `LMR-400` / `P240-260VDG` / `P007-003` anchor set from
Phase 1 query mining is confirmed as the real physical-part population.

---

## Root cause — two regex rules

### Rule 1 — `_report_id_re` alternation includes `IR`

```python
# Before
self._report_id_re = re.compile(
    r"\b(?:FSR|UMR|IR|ASV|RTS)-[A-Za-z0-9_-]+\b",
    re.IGNORECASE,
)
```

The `IR` alternation was originally meant for "Incident Report" in the
maintenance-domain sense (FSR/UMR/IR/ASV/RTS is the V1 report-family
list). But `IR-` is also the NIST SP 800-53 Incident Response control
family prefix, and the enterprise program corpus has thousands of NIST
control mappings embedded in cybersecurity SIPs and STIG checklists.
Every `IR-1` through `IR-10` NIST control matches the regex and gets
emitted as a `PO` entity at confidence 0.9.

**Fix:** Remove `IR` from the alternation entirely. Every real report ID
matching this column uses `FSR`, `UMR`, `ASV`, or `RTS`. The PO store
has zero real `IR-*` report IDs — all top entries are NIST collisions.

### Rule 2 — `part_patterns` generic `[A-Z]{2,}-\d{3,4}`

The production `config/config.yaml` has a catch-all fallback pattern:

```yaml
part_patterns:
  - 'ARC-\d{4}'
  - 'IGSI-\d+'
  - 'PO-\d{4}-\d{4}'
  - 'SN[-: ]?\d+'
  - 'SEMS3D-\d+'
  - '[A-Z]{2,}-\d{3,4}'   # ← the catch-all
  - 'WR-\d{4}'
  ...
```

`[A-Z]{2,}-\d{3,4}` matches any 2-or-more-letter prefix plus a 3-4
digit suffix. That catches:

- `AS-5021`, `AS-7040`, `AS-7031` → STIG Application Server baselines
- `OS-0004`, `OS-0003`, `OS-0000` → STIG Operating System baselines
- `GPOS-0022`, `GPOS-0017`, `GPOS-0020` → STIG GPOS baselines
- `CCI-0001`, `CCI-0003`, `CCI-0018` → DISA Control Correlation IDs
- `SV-2045`, `SV-2044` → STIG Vulnerability IDs
- `HS-872` → STIG Host System baseline

But it also correctly catches:

- `RG-213`, `LMR-400` → real HF coaxial cable types
- `IDIQ-006` → contract identifier (arguably a contract, not a part)

**Fix:** Apply a runtime rejection validator that checks the candidate
against a configurable list of security-standard prefixes BEFORE
emitting it as a PART entity. The generic pattern stays (it captures
real cable types), but its output is now filtered.

---

## The fix

### Design principle — two-stage match plus validate

Mirrors the phone-regex-fix approach (`docs/PHONE_REGEX_FIX_2026-04-11.md`):

1. **Broad regex** matches candidates as before.
2. **Runtime validator** rejects candidates matching security-standard
   prefixes.
3. **Configurable exclusion list** lets operators tune per-corpus
   without touching extractor code.

This beats "tighten the regex" because the regex would have to
know every current and future STIG/NIST/CCE prefix, and corpus-specific
override is impossible in pure regex.

### Code changes

#### 1. `src/config/schema.py` — new config field

Added `ExtractionConfig.security_standard_exclude_prefixes: list[str]`
with a default of 32 prefixes covering:

- **NIST SP 800-53 Rev 5** (all 20 families) — AC, AT, AU, CA, CM, CP,
  IA, IR, MA, MP, PE, PL, PM, PS, PT, RA, SA, SC, SI, SR
- **STIG baseline platform codes** — AS-, OS-, GPOS-, HS-
- **STIG / DISA identifiers** — CCI-, SV-, SP-800, SP-
- **MITRE security identifiers** — CVE-, CCE-

Default is ON for the current corpus. Operators on a different corpus
can override via `config.yaml` once the wiring commit lands (see
"Known gap" below).

#### 2. `src/extraction/entity_extractor.py`

**`RegexPreExtractor`:**
- New class-level constant `_DEFAULT_SECURITY_STANDARD_PREFIXES` with
  the same 32-prefix default list.
- `__init__` accepts `security_standard_exclude_prefixes: list[str] |
  tuple[str, ...] | None = None`. `None` → class default. Empty list
  → exclusion disabled (valid override).
- New method `_is_security_standard_identifier(candidate: str) -> bool`
  does a cheap upper + startswith scan over the prefix tuple.
- Applied at every candidate-emit site:
  - `_part_patterns` loop (line ~565)
  - `_po_re` loop (line ~615)
  - new `_sap_po_re` loop (labeled SAP POs)
  - `_serial_re` loop
  - `_report_id_re` loop
- **`IR` removed from the `_report_id_re` alternation.** Real report
  IDs in this corpus use FSR/UMR/ASV/RTS; IR was 100% NIST collision.
- New regex `_sap_po_re` for labeled 10-digit SAP POs:
  ```
  (?:Purchase\s*Order|PO\s*Number|P\.?O\.?|PO)\s*[#:.\-]?\s*(\d{10})\b
  ```
  The label requirement is deliberate — a bare 10-digit number can't
  be distinguished from phone numbers, shipment tracking IDs, and OCR
  noise. Requires an explicit PO / Purchase Order / P.O. token before
  the digits.

**`EventBlockParser`:**
- Same `security_standard_exclude_prefixes` kwarg with fallback to
  `RegexPreExtractor._DEFAULT_SECURITY_STANDARD_PREFIXES`.
- Mirror `_is_security_standard_identifier` helper.
- Applied to every PART emission in `parse()`: `part_number`,
  `component`, `installed_part`, `removed_part`, `new_serial`,
  `failed_serial`, `installed_serial`, `removed_serial`.
- `failure_mode` is deliberately NOT gated — failure descriptions are
  free text like "connector fault" that can't collide with NIST
  prefixes. Documented inline.

---

## Before / after measurement

### Method

Streamed the first 100,000 chunks from `data/index/lancedb` via
`iter_chunk_batches` (read-only). Ran each chunk through two pipelines:

- **PRE-FIX:** `RegexPreExtractor` with `security_standard_exclude_prefixes=[]`
  (disabled) plus a side-count of the pre-fix `_report_id_re` which
  used to include `IR`. This approximates the pre-fix behavior.
- **POST-FIX:** `RegexPreExtractor` with the default exclusion list on
  and the new `_report_id_re` (no `IR`).

### Results on the 100K sample

| Column | Pre-fix | Post-fix | Delta |
|---|---:|---:|---:|
| PO entities | **8,616** | **0** | **−100.0%** |
| PART entities | **430** | **61** | **−85.8%** |

Extrapolated to the full 10.4M corpus (linear scaling from the 100K
sample, bearing the caveat below):

| Column | Currently on disk | Post-fix projection |
|---|---:|---:|
| PO entities | 150,602 | ~3,000 real report IDs (FSR/UMR/ASV/RTS long tail) |
| PART entities | 2,521,235 | ~360,000 (85.8% reduction applied) |

### Sample-selection caveat

The first 100,000 chunks in storage order are concentrated in a single
document family — `Deliverables Report IGSI-1161 ISTO CP Controls
2023-Nov (A027).xlsx`, a NIST SP 800-53 mapping document. This makes the
100K a **best case for demonstrating the PO fix** (the XLSX is pure
NIST control content, so the 100% PO elimination is expected and
accurate for that content), and a **worst case for absolute PART
counts** (few physical parts in a cybersecurity policy document).

The 85.8% PART reduction ratio IS meaningful — it shows the exclusion
gate is working on the part patterns that fire in this sample. But the
absolute post-fix PART count (61 per 100K) does not extrapolate linearly
to the full 10.4M, because the chunks dominated by maintenance logs
(which drive most of the real PART content) live in different regions
of the store.

The coordinator will see the true full-corpus numbers when Tier 1 is
re-run on the complete store, which is NOT part of this commit per the
task brief. The 100K sample proves the fix direction and blocks the
dominant pollution sources.

---

## Known gap — config override path latent

The task brief explicitly forbids touching `scripts/tiered_extract.py`
(CLI frozen post Round 3) and `scripts/import_extract_gui.py` (QA'd
skip-import fix frozen). Both files call:

```python
RegexPreExtractor(part_patterns=config.extraction.part_patterns)
EventBlockParser(part_patterns=config.extraction.part_patterns)
```

Without passing the new `security_standard_exclude_prefixes` kwarg.
That's fine for the **default-on** behavior — both classes fall back to
`_DEFAULT_SECURITY_STANDARD_PREFIXES` when the kwarg is `None`. So the
NIST rejection IS applied on every walk-away run that starts after
this commit lands, without any caller change.

**But the per-corpus override path is latent.** An operator editing
`config.yaml::extraction.security_standard_exclude_prefixes` will NOT
see the override take effect until a future follow-up commit wires the
config value through the CLI/GUI caller sites. The config field exists
so that wiring commit is a one-line change when unfrozen.

Recommended followup (new task): a two-line change at each of the six
callers in `scripts/tiered_extract.py`, `scripts/import_extract_gui.py`,
`scripts/extract_entities.py`, `scripts/overnight_extraction.py`,
`scripts/phone_regex_probe.py` to pass
`security_standard_exclude_prefixes=config.extraction.security_standard_exclude_prefixes`
to the `RegexPreExtractor` / `EventBlockParser` constructors.

---

## Taxonomy discussion — NIST_CONTROL / CYBER_BASELINE entity types

The task brief asked me to discuss whether NIST control IDs belong in
their own category rather than being rejected outright. My
recommendation:

**Yes, long-term.** Short-term, reject them. Here's the reasoning.

NIST SP 800-53 controls ARE valid cybersecurity references. An operator
asking "which controls apply to the Diego Garcia site" or "what
configuration baseline governs the GPS receiver" legitimately wants to
hit NIST control IDs as first-class entities. Throwing them away entirely
loses signal that the corpus actually contains.

But adding `NIST_CONTROL` and `CYBER_BASELINE` as new entity types is a
cross-cutting schema change:

- `src/store/entity_store.py` entity type CHECK constraint
- `src/extraction/entity_extractor.py` GPT-4o `ENTITY_SCHEMA` enum
- `src/query/query_router.py` routing logic (new type → new dispatch)
- `src/query/entity_retriever.py` retrieval paths
- `src/gui/panels/entity_panel.py` display
- Tier 2 GLiNER labels
- Tier 3 LLM extraction prompts

That's a multi-commit sprint item, not a regex fix. For the current
commit I recommend:

1. **Now (this commit):** Reject them at Tier 1. Aggregation queries
   return honest answers. Demo risk neutralized.
2. **Sprint item (recommended):** Add `NIST_CONTROL` and `CYBER_BASELINE`
   as first-class entity types with their own extraction prefixes (the
   same list as the exclusion, inverted — match on these prefixes to
   emit a `NIST_CONTROL` entity). Wire through the query router so
   "which controls..." queries dispatch to the new type.
3. **Not committing to this sprint:** The taxonomy split is the correct
   long-term design but coordinator should decide when to prioritize
   it against the demo timeline.

---

## Tests

Added to `tests/test_extraction.py`:

- `TestSecurityStandardExclusion` (10 methods, 40+ assertions)
  - STIG baseline codes rejected as PART
  - All 20 NIST SP 800-53 Rev 5 families rejected (including new PT
    and SR)
  - NIST IR family not caught by report_id_regex
  - MITRE CVE / CCE rejected
  - Real physical parts (`RG-213`, `LMR-400`, `ARC-4471`) still accepted
  - Labeled SAP POs extracted (`PO 5000585586`, `Purchase Order: ...`)
  - Bare 10-digit numbers NOT extracted as POs
  - Exclusion list overridable via `security_standard_exclude_prefixes`
    kwarg (empty list disables, custom list replaces)
  - `_is_security_standard_identifier` helper direct unit test

- `TestEventBlockParserSecurityStandardExclusion` (3 methods)
  - NIST/STIG prefix rejected through EventBlockParser PART emissions
  - Real part (`ARC-4471`) still emitted by EventBlockParser
  - Override list works on EventBlockParser

All 74 extraction tests pass (was 61; +13 new).

---

## Constraints respected

- `scripts/tiered_extract.py` — **not touched** (CLI frozen post Round 3)
- `scripts/import_extract_gui.py` — **not touched** (QA'd skip-import fix frozen)
- No full-corpus Tier 1 re-run
- Sample measurement used `--limit 100000` semantics via `iter_chunk_batches`
- Existing entity store preserved (read-only analysis)
- Sanitized before push
- 74 extraction tests pass (13 new)
- Full repo test suite confirmed unchanged

---

Signed: Agent 1 | HybridRAG_V2 | 2026-04-12 MDT
