# security standard / STIG Regex Over-Matching — PART and PO Columns

**Agent:** reviewer | **Repo:** HybridRAG_V2 | **Date:** 2026-04-12 MDT

**Trigger:** reviewer's 400-query eval mining surfaced that Tier 1 PART and
PO entities on the 10.4M primary workstation LanceDB store are heavily polluted with
security standard SP 800-53 / STIG / MITRE security-standard identifiers, NOT physical
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

**security standard SP 800-53 Rev 5 control family list.**
Confirmed that Rev 5 has exactly 20 control families identified by
two-letter prefixes: AC, AT, AU, CA, CM, CP, IA, IR, MA, MP, PE, PL,
PM, PS, PT, RA, SA, SC, SI, SR. Rev 5 added PT (PII Processing and
Transparency) and SR (Supply Chain Risk Management) compared to Rev 4.

- Source: NIST SP 800-53 Rev 5 canonical publication on
  csrc.{nist-domain}.gov (URL omitted here because the repo sanitizer
  rewrites "nist" inside URLs and produces a broken link; search
  "SP 800-53 Rev 5" to locate the canonical catalog)
- Secondary: control family explainers at `saltycloud.com`, `ipkeys.com`,
  `securityscientist.net`, `drata.com`, `secureframe.com`, `cybersaint.io`

reviewer's existing `NIST_CONTROL_PREFIXES` tuple in
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

## Evidence from the live primary workstation entity store

All queries run read-only against `data/index/entities.sqlite3` via
`sqlite3 ... ?mode=ro`. No mutation.

### Top 25 PO entities

```
    42,608  IR-8       (security standard Incident Response control)
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

**10 of the top 10 PO entries are industry standard family controls = 147,509
of 150,602 total PO = 98.0% security standard pollution.** Real report IDs
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
at position 23. Every entry above it is a STIG / security standard / CCI identifier.
Cumulative: **~1,016,407 of the top 21 PART entries are security-standard
codes** = 40% of the PART total just from the top-21 bucket. The 90%
pollution estimate from reviewer holds when the long tail of STIG
baselines is included.

### 100-row direct sample

Cross-check sampling across the PO and PART rows (via `rowid % N = 0`
for even distribution):

```
PO column (100 rowid-samples):
  security standard/STIG/CCI identifiers:    98/100
  SAP 10-digit POs:              0/100
  Other (real report IDs):       2/100

PART column (100 rowid-samples):
  security standard/STIG/CCI identifiers:    59/100  (top entries oversample security codes)
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
list). But `IR-` is also the security standard SP 800-53 Incident Response control
family prefix, and the enterprise program corpus has thousands of security standard
control mappings embedded in cybersecurity SIPs and STIG checklists.
Every `IR-1` through `IR-10` security standard control matches the regex and gets
emitted as a `PO` entity at confidence 0.9.

**Fix:** Remove `IR` from the alternation entirely. Every real report ID
matching this column uses `FSR`, `UMR`, `ASV`, or `RTS`. The PO store
has zero real `IR-*` report IDs — all top entries are security standard collisions.

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
know every current and future STIG/security standard/CCE prefix, and corpus-specific
override is impossible in pure regex.

### Code changes

#### 1. `src/config/schema.py` — new config field

Added `ExtractionConfig.security_standard_exclude_prefixes: list[str]`
with a default of 32 prefixes covering:

- **security standard SP 800-53 Rev 5** (all 20 families) — AC, AT, AU, CA, CM, CP,
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
  IDs in this corpus use FSR/UMR/ASV/RTS; IR was 100% security standard collision.
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
  free text like "connector fault" that can't collide with security standard
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
document family — `Deliverables Report IGSI-1161 legacy monitoring system CP Controls
2023-Nov (A027).xlsx`, a security standard SP 800-53 mapping document. This makes the
100K a **best case for demonstrating the PO fix** (the XLSX is pure
security standard control content, so the 100% PO elimination is expected and
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
security standard rejection IS applied on every walk-away run that starts after
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

The task brief asked me to discuss whether security standard control IDs belong in
their own category rather than being rejected outright. My
recommendation:

**Yes, long-term.** Short-term, reject them. Here's the reasoning.

security standard SP 800-53 controls ARE valid cybersecurity references. An operator
asking "which controls apply to the Diego Garcia site" or "what
configuration baseline governs the GPS receiver" legitimately wants to
hit security standard control IDs as first-class entities. Throwing them away entirely
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
  - All 20 security standard SP 800-53 Rev 5 families rejected (including new PT
    and SR)
  - industry standard family not caught by report_id_regex
  - MITRE CVE / CCE rejected
  - Real physical parts (`RG-213`, `LMR-400`, `ARC-4471`) still accepted
  - Labeled SAP POs extracted (`PO 5000585586`, `Purchase Order: ...`)
  - Bare 10-digit numbers NOT extracted as POs
  - Exclusion list overridable via `security_standard_exclude_prefixes`
    kwarg (empty list disables, custom list replaces)
  - `_is_security_standard_identifier` helper direct unit test

- `TestEventBlockParserSecurityStandardExclusion` (3 methods)
  - security standard/STIG prefix rejected through EventBlockParser PART emissions
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

## Round 2 QA fix — PS-800 / SA-9000 collision regression

### QA finding (CoPilot+, 2026-04-12)

The Round 1 fix (commit `ba4d962`) used **prefix-startswith matching**
against a static list of prefixes. The list included `PS-` and `SA-`
because they're both security standard SP 800-53 family prefixes. But `PS` and
`SA` also name real hardware parts in this corpus:

- **`PS-800`** — Granite Peak backordered part, referenced in
  `docs/DEMO_DAY_CHECKLIST_2026-04-07.md` and
  `tests/test_corpus/tier2_stress/spreadsheet_fragment.txt`.
- **`SA-9000`** — Spectrum Analyzer, appears throughout
  `tests/golden_eval/golden_tuning_400.json`.

Round 1's startswith rejection blocked both. QA reproduced:

```
"Backordered part PS-800 at Granite Peak." -> no PART
"Lead time for Spectrum Analyzer SA-9000 is 6 weeks." -> no PART
```

The same texts extracted correctly when the exclusion was disabled,
which pinpointed the bug to the security standard prefix list.

The config's own `part_patterns` list already declared `PS-\d{3}` as
a first-class part family (`src/config/schema.py::part_patterns`
default). That was a dead giveaway I missed when drafting Round 1.

### Round 2 fix — suffix-length discriminator

Switched the exclusion matcher from **prefix-startswith** to
**regex match**. The new default list constrains NIST families to
**1-2 digit suffixes + optional enhancement**, because NIST SP 800-53
Rev 5 tops out at SC-51 (confirmed via the official control catalog
search on 2026-04-12). Real hardware parts in this corpus use
**3+ digit suffixes** (PS-800, SA-9000, FM-220, ARC-4471). The digit
length cleanly disambiguates — no per-family allowlist needed, no
manual exceptions.

**New security standard family pattern:**
```python
re.compile(
    r"^(?:AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)"
    r"-\d{1,2}(\(\d+\))?$"
)
```

Examples:
- `IR-4`, `AC-2(1)`, `PS-7`, `SA-11`, `SC-51` → **rejected** (security standard
  control, 1-2 digit suffix)
- `PS-800`, `SA-9000`, `CP-220`, `PE-4000`, `SC-1000` → **accepted**
  (3+ digit suffix = hardware, not security standard control)
- `IR-4A`, `IR-1N-04`, `IR-7802` → **accepted** (letters or 3+ digit
  suffixes = real report IDs)

**STIG baseline codes** (`AS-`, `OS-`, `GPOS-`, `HS-`) stay on a
broader pattern `^(?:AS|OS|GPOS|HS)-\d{3,5}$` because AS/OS/GPOS/HS
are STIG-only prefixes with no observed real-part collisions. CCI,
SV, SP-800, CVE, and CCE use their own patterns.

### Round 2 API change

- Renamed the extractor kwarg and config field from
  `security_standard_exclude_prefixes` to
  `security_standard_exclude_patterns`.
- Entries are now interpreted as regex patterns (accepts strings or
  pre-compiled `re.Pattern` objects).
- Passing an empty list still disables all exclusion (same as Round 1).
- The class attribute is now `_DEFAULT_SECURITY_STANDARD_PATTERNS`
  (tuple of compiled regexes).

No currently-active caller reads the config field (it's latent until
the CLI/GUI wiring commit), so the rename is safe.

### Round 2 regression tests

Added to `tests/test_extraction.py::TestSecurityStandardExclusion`:

- **`test_real_hardware_parts_sharing_nist_prefix_accepted`** — pins
  `PS-800` and `SA-9000` as must-extract-as-PART, with 4 separate
  corpus-like phrasings. This is the regression guard for the
  Round 1 bug.
- **`test_nist_family_short_suffix_still_rejected`** — pins security standard
  controls like `PS-1`, `PS-3`, `PS-7`, `SA-1`, `SA-5`, `SA-11`,
  `SA-22`, `AC-2(1)`, `SC-51` as must-still-be-rejected, so any
  future rewrite that over-narrows the security standard pattern gets caught.
- **`test_hypothetical_3digit_hardware_on_other_nist_families`** —
  future-proof check with hypothetical `CP-220`, `PE-4000`, `PM-500`,
  `SC-1000`, `IR-420` (none of which exist in the current corpus,
  but could in a future one). The suffix-length rule should let all
  of them through.
- **`test_event_block_parser_accepts_hardware_with_nist_prefix`** —
  same regression guard applied to the EventBlockParser code path,
  not just RegexPreExtractor, so both emission paths honor the
  Round 2 rule.

All 78 extraction tests pass (was 74; +4 new Round 2 regression
guards). Full repo: 190 passed (was 186; +4).

### Round 2 re-measurement on the same 100K sample

The pollution reduction is identical to Round 1 because the top-25
PO and PART noise is all 1-2 digit industry standard family or 3-5 digit STIG
codes — both still caught by the regex patterns.

```
PO entities:   8,616 -> 0     (-100.0%)   — same as Round 1
PART entities:   430 -> 61    ( -85.8%)   — same as Round 1

Regression probes:
  Backordered part PS-800 at Granite Peak.       PART=['PS-800', 'PS-800']
  Spectrum Analyzer SA-9000 lead time 6 weeks.   PART=['SA-9000']
  IR-4 applies to this system.                    PART=[]  PO=[]
  AS-5021 baseline.                               PART=[]  PO=[]
```

`PS-800` appears twice because `part_patterns` has both `PS-\d{3}`
(explicit) and `[A-Z]{2,}-\d{3,4}` (catch-all) in the default config;
both match. The entity store's `UNIQUE(chunk_id, entity_type, text)`
constraint dedupes at insert time, so this is a cosmetic duplicate in
the in-memory extractor output, not a stored duplicate.

### Round 2 recommendation

The suffix-length discriminator is the correct long-term rule. It:

1. Matches security standard SP 800-53's actual numbering convention (1-2 digit
   control numbers + optional enhancement).
2. Leaves 3+ digit space free for hardware parts.
3. Extends to future security standard families without modification (any new
   family added to the alternation inherits the same rule).
4. Doesn't require a per-family allowlist of exceptions.
5. Works identically for Rev 4 and Rev 5 because Rev 5's new families
   (PT, SR) have the same short-suffix convention.

The only remaining risk is a hardware family with a 1-2 digit suffix
AND a security standard-family prefix (e.g., a hypothetical part number `PS-7`
that happens to also be a real Personnel Security control). No such
collision is observed in the current corpus. If one appears, the
per-corpus override path (via `security_standard_exclude_patterns=[]`
or a custom pattern list) is the escape hatch.

---

Signed: reviewer | HybridRAG_V2 | 2026-04-12 MDT
