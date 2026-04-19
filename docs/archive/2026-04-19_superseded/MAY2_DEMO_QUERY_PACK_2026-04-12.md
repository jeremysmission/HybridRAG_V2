# May 2 Demo Query Pack — 2026-04-12

**Purpose:** Safe May 2 query pack built from the 400-query eval corpus plus the current canary methodology.
**Posture:** Retrieval-first by default. Narrow real-scoped counts only with frozen evidence. Canary controls only with transparent disclosure.
**Do not do:** broad corpus-wide totals, early audience-choice, or any query that depends on polluted `PART` / `PO` aggregation.

## Use Rules

- `retrieval-first safe`: OK for the default live script
- `narrow real-scoped count safe`: only after the evidence binder is frozen for that count
- `canary-only validation control`: only after VALCAN injection and validator pass
- `refusal / boundary-setting safe`: use to demonstrate trust boundary, not coverage

## Core Safe Set

| ID | Query | Persona | Safety class | Why it is safe now | What it proves |
|---|---|---|---|---|---|
| `PQ-101` | What is the latest enterprise program weekly hours variance for fiscal year 2024? | Program Manager | retrieval-first safe | Direct spreadsheet lookup against one dated recurring artifact family | PM spreadsheet retrieval on a real 10.4M corpus |
| `PQ-104` | What is the enterprise program Integrated Master Schedule deliverable and where is it tracked? | Program Manager | retrieval-first safe | Single deliverable family with clear A031 folder anchors | V2 can explain contract/deliverable structure, not just search free text |
| `PQ-113` | What is purchase order 5000585586 and what did it order? | Logistics Lead | retrieval-first safe | Exact-token PO lookup with a confirmed procurement folder | Exact identifier retrieval against logistics records |
| `PQ-115` | Which Tripp Lite power cord part number is used for legacy monitoring systems? | Logistics Lead | retrieval-first safe | Exact part-number family in a clean parts folder | Exact part lookup from downloaded logistics references |
| `PQ-122` | What recommended spares parts list exists and what fields does it track? | Logistics Lead | retrieval-first safe | Canonical spreadsheet family with known columns | Spreadsheet/tabular retrieval without risky arithmetic |
| `PQ-129` | What site outages have been analyzed in the Systems Engineering folder? | Field Engineer | retrieval-first safe | Clear engineering folder family with multiple dated artifacts | Engineering-family retrieval and folder awareness |
| `PQ-130` | What is the Corrective Action Plan for Fairford monitoring system incident IGSI-1811? | Field Engineer | retrieval-first safe | Exact incident ID anchored to one real CAP file | Incident-driven engineering retrieval |
| `PQ-136` | What ACAS scan results are documented for the legacy monitoring systems under CDRL A027? | Cybersecurity / Network Admin | retrieval-first safe | Clear A027 ACAS folder family, not a count claim | Cyber artifact retrieval on a compliance-heavy subtree |
| `PQ-141` | What Apache Log4j directive has been issued for enterprise program systems? | Cybersecurity / Network Admin | retrieval-first safe | Exact directive ID and folder name | Fast exact-token cyber retrieval |
| `BND-001` | What maintenance was performed at Fort Wainwright in 2024? | Boundary | refusal / boundary-setting safe | Known out-of-corpus test from the legacy demo script | V2 should refuse rather than invent |

## Optional Stretch Set

| ID | Query | Persona | Safety class | Why it is conditional | What it proves |
|---|---|---|---|---|---|
| `PQ-103` | Which CDRL is A002 and what maintenance service reports have been submitted under it? | Program Manager | retrieval-first safe | Still safe, but more jargon-heavy than the core set | Contract code to deliverable-family resolution |
| `PQ-110` | What is the LDI suborganization 2024 budget for ORG enterprise program and how is it organized by option year? | Program Manager | retrieval-first safe | More sensitive and spreadsheet-heavy than `PQ-101` | Budget-sheet retrieval |
| `PQ-112` | What pre-amplifier parts are used in the legacy monitoring systems and what are their specifications? | Logistics Lead | retrieval-first safe | Safe if the room wants parts/spec detail, but denser than `PQ-115` | Detailed parts/spec retrieval |
| `PQ-128` | What maintenance actions are documented in the Thule monitoring system Maintenance Service Reports? | Field Engineer | retrieval-first safe | Good field-engineering query, but more narrative and site-specific | Maintenance-history retrieval from MSRs |
| `PQ-138` | What is the System Authorization Boundary for monitoring system defined in SEMP? | Cybersecurity / Network Admin | retrieval-first safe | Safe, but more technical and acronym-heavy | Cyber architecture retrieval |
| `PQ-142` | What STIG reviews have been filed and when? | Cybersecurity / Network Admin | retrieval-first safe | Tabular cyber query, but thinner evidence family than `PQ-141` | Cyber spreadsheet retrieval |
| `PQ-395` | How many Monthly Actuals spreadsheets are filed for calendar year 2024? | Program Manager | narrow real-scoped count safe | Defensible only if the 12-file manual evidence list is frozen | Narrow real count over one recurring file family |
| `PQ-146` | How many site-specific Maintenance Service Report folders exist across both legacy monitoring system and monitoring system? | Aggregation / Cross-role | narrow real-scoped count safe | Defensible only if the A002 folder list is frozen and visible | Narrow real count over one deliverable family |
| `REAL-Q005` | How many named cybersecurity directives are in the current directive reference set? | Cybersecurity / Network Admin | narrow real-scoped count safe | Not from the 400 file; comes from the canary methodology and needs a frozen five-directive list | Narrow real count over one auditable directive set |
| `VALCAN-Q001` | How many open validation purchase orders exist across all validation sites, and what is their total value? | Logistics Lead | canary-only validation control | Only valid after VALCAN injection + validator pass | The aggregation path can count and total a known synthetic pack |
| `VALCAN-Q002` | How many distinct validation part numbers failed during lightning-related service events in 2024, and at which validation sites did those failures occur? | Aggregation / Cross-role | canary-only validation control | Hard control; only use after VALCAN validation and operator rehearsal | Cross-document structured aggregation on a known synthetic pack |

## Explicit Do-Not-Use-Live Set

| ID | Why not live-safe now |
|---|---|
| `PQ-107` | Broad CDRL-type enumeration across the contract; too close to a cataloging demo instead of a user-value demo |
| `PQ-118` | Vague procurement aggregation over an option-year period; answer surface is broad and hard to narrate cleanly |
| `PQ-134` | Explicitly tied to the Part Failure Tracker spreadsheet; even the corpus rationale notes this does not aggregate cleanly via chunk retrieval |
| `PQ-143` | Multi-year ATO package count/list; too broad for a live aggregate and easy to overclaim |
| `PQ-149` | Site-visit enumeration returns a long site list; good audit query, bad stage query |
| `PQ-150` | "Full set of CDRL deliverables" is a broad catalog dump, not a clean demo win |
| `PQ-203` | Multi-site OCONUS shipment counting is defensible on paper but too list-heavy and brittle live |
| `PQ-205` | Its own reference notes only partial month coverage was confirmed; not strong enough for a live count claim |
| `PQ-192` and `PQ-263` | The two queries disagree on the FA881525FB002 ACAS deliverable count (`4` vs `3` confirmed). Do not use either live until reconciled |
| Any ad hoc `PO` or `PART` corpus-wide total | Current methodology still treats broad procurement and part counts as unsafe until cleanup + rerun + validation land |

## Recommended Live Sequence

### Default retrieval-first sequence

1. `PQ-101`
2. `PQ-113`
3. `PQ-129`
4. `PQ-141`
5. `PQ-130` or `PQ-136`
6. `BND-001`

### If one narrow real-scoped count is cleared

1. `PQ-101`
2. `PQ-113`
3. `PQ-395` or `REAL-Q005`
4. `PQ-129`
5. `PQ-141`
6. `BND-001`

### If canary controls are fully cleared

1. `PQ-101`
2. `VALCAN-Q001`
3. `PQ-113`
4. `PQ-129`
5. `PQ-141`
6. `BND-001`

**Do not put `VALCAN-Q002` in the live path unless the control has already passed in rehearsal and the operator wants one hard control.** It is better as a rehearsal/binder control than as a stage opener.

## Short Fallback Lines

- Retrieval-first miss: `Let me show you the source family this answer should come from.`
- Narrow real-scoped count miss: `This count is from a frozen narrow subtree, so I am switching to the evidence binder rather than trusting a weak live answer.`
- Canary control miss: `That failed the validation control, so we are not making a live aggregation claim from it.`
- Boundary query: `That is outside the corpus or outside the validated lane, and refusal is the correct behavior here.`

## Sources Used

- `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md`
- `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md`
- `docs/CANARY_INJECTION_METHODOLOGY_2026-04-12.md`
- `docs/DEMO_DAY_RESEARCH_2026-04-12.md`
- `docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md`
- `tests/golden_eval/production_queries_400_2026-04-12.json`
- `docs/DEMO_SCRIPT_2026-04-05.md` for `BND-001`
