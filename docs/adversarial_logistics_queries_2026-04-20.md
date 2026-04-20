# Adversarial Logistics Queries -- Should Tier-Down to RED

**Date:** 2026-04-20
**Author:** Researcher | no permanent lane
**Consumer:** QA-Agent (for Phase QA4 adversarial sweep)
**Scope:** 10 queries engineered to trigger RED abstention

The HybridRAG V2 tier contract (GREEN / YELLOW / RED) is only
defensible if RED fires reliably on edge cases. This pack gives
QA-Agent a targeted sweep to validate abstention behavior across
ten adversarial axes.

Each item has: the input query, the expected abstention reason
category, the substrate gate that should fail, and the expected
user-visible message shape.

---

## AQ-01 -- Unknown site token (canonical aliases gap)

**Query:** "Top 5 failing parts in Antarctica in 2024"

**Expected tier:** RED
**Reason:** `_detect_unresolved_site_reference` returns
"Antarctica" since it is not in `config/canonical_aliases.yaml`
and not present in `failure_events.site_token` values.
**Expected message:** "query references unknown site 'Antarctica'
-- not present in canonical_aliases.yaml or failure_events
substrate"
**Regression anchor:** QA 2026-04-19 15:05 signoff reproduces
this exactly.

---

## AQ-02 -- Unknown system token

**Query:** "Top 5 failing parts in GOTHAM in 2024"

**Expected tier:** RED
**Reason:** `_detect_unresolved_system_reference` returns
"GOTHAM"; substrate holds only NEXION and ISTO.
**Expected message:** "query references unknown system 'GOTHAM'
-- not present in canonical_aliases.yaml or failure_events
substrate"
**Regression anchor:** QA 2026-04-19 15:05 signoff.

---

## AQ-03 -- Typo in part number (no hit)

**Query:** "Reorder point for SEMS3D-4O536 at Learmonth in NEXION"
(note the letter O instead of digit 0)

**Expected tier:** INVENTORY_RED
**Reason:** `part_number = 'SEMS3D-4O536'` returns 0 rows;
history_months = 0; < 12-month threshold.
**Expected message:** RED abstention with history insufficiency
reason.
**Why in the pack:** tests that the executor does NOT fuzz-match
typos to a neighbouring real part; exactness discipline holds.

---

## AQ-04 -- Year beyond corpus range

**Query:** "Top 5 failing parts in NEXION in 2030"

**Expected tier:** RED (or GREEN-empty with zero rows)
**Reason:** event_year filter yields 0 matching rows.
**Expected message:** "0 rows matched filters system=NEXION,
event_year=2030. Substrate holds events from <min> to <max>."
**Why in the pack:** validates the empty-slice RED trigger per
the evidence-contract "rows_matched == 0 -> RED" rule.

---

## AQ-05 -- Cross-program query (parts from a different program)

**Query:** "Top 5 failing parts in the SEWIP system in Guam in
2024"

**Expected tier:** RED
**Reason:** SEWIP is not a canonical system; unresolved system
detector fires.
**Expected message:** "query references unknown system 'SEWIP'
-- not present in canonical_aliases.yaml or failure_events
substrate"
**Why in the pack:** defense against an audience member who
tries to ask about a program not in our corpus; must not
hallucinate cross-program numbers.

---

## AQ-06 -- SQL injection in query text

**Query:** "Top 5 failing parts in NEXION in 2024; DROP TABLE
failure_events; --"

**Expected tier:** GREEN (benign) OR RED (depending on axis
parser robustness)
**Reason:** Parameterized SQL in `FailureEventsStore.top_n_parts`
is the defense; year parser extracts "2024" cleanly. The
injection text is discarded because it matches no axis
extraction regex.
**Expected message:** normal GREEN ranked list (injection has no
effect).
**Why in the pack:** validates that parameterized SQL holds even
when query text carries hostile tokens. If GREEN does not fire,
flag a parsing-layer bug. **This is the security test**, not a
tier-down test.

---

## Q7 -- Rate question without denominator substrate

**Query:** "What is the failure rate for SEMS3D-41785 at Guam in
2024?"

**Expected tier:** YELLOW (not RED)
**Reason:** `is_rate=True` triggers; numerator exists; installed_
base denominator substrate missing (Lane 3 pre-signoff).
**Expected message:** "Failure rate requires installed-base
denominator -- showing failure counts only. Upgrade to GREEN by
populating installed_base substrate."
**Why in the pack:** boundary case; validates YELLOW (bounded-
evidence) is the correct response, not RED.

---

## AQ-08 -- Logistics-count question (should hit LOGISTICS_GUARD)

**Query:** "How many POs were outstanding as of 2022-06-01?"

**Expected tier:** LOGISTICS_GUARD / NOT_SUPPORTED
**Reason:** fail-closed guard detects count + outstanding + PO
axis; po_lifecycle substrate not yet populated for outstanding
calculation.
**Expected message:** "## Logistics / PO Aggregation -- NOT YET
SUPPORTED ... The deterministic PO-lifecycle substrate has not
been populated yet. Without it, any numbers would be LLM-
generated estimates, not exact counts."
**Regression anchor:** QA 2026-04-19 15:05 signoff
"Count of open POs for monitoring system" -> LOGISTICS_GUARD.

---

## AQ-09 -- Semantic question disguised as aggregation

**Query:** "Which document explains how received quantities are
recorded?"

**Expected tier:** AGGREGATE / SEMANTIC passthrough (**not**
LOGISTICS_GUARD, **not** RED)
**Reason:** intent-detection must require BOTH count/aggregate
trigger AND logistics axis term. "Which document" is a locator
query, not a count.
**Expected message:** normal semantic answer with evidence
panel.
**Regression anchor:** QA 2026-04-19 15:05 signoff Agent-B
"path AGGREGATE, confidence HIGH". **This is the false-positive
guard test** for the 14:20 B2 fix.

---

## AQ-10 -- Non-English / encoding adversarial

**Query:** "NEXIONシステムで2024年に故障した部品トップ5"
(Japanese: "Top 5 failed parts in NEXION system in 2024")

**Expected tier:** RED (or SEMANTIC passthrough with abstention
narrative)
**Reason:** aggregation intent-detect regex is English-only; no
axis parses; either no aggregation path fires (passthrough to
RAG) or aggregation executor returns RED "could not parse
filters".
**Expected message:** either semantic answer with LLM hedging
OR aggregation RED.
**Why in the pack:** validates that non-English queries do not
silently emit bogus SQL against canonical English tokens.

---

## Cross-pack acceptance criteria (for QA sweep)

QA-Agent please verify:

1. **AQ-01, AQ-02** reproduce the exact QA 15:05 messages.
2. **AQ-03, AQ-04, AQ-05** fire RED (or empty-GREEN for AQ-04
   depending on executor policy -- either is acceptable, but
   never a non-zero count).
3. **AQ-06** returns normal GREEN; any SQL error from injection
   is a hard bug, flag as P0.
4. **AQ-07** fires YELLOW, not RED (boundary case).
5. **AQ-08** hits LOGISTICS_GUARD with NOT_SUPPORTED message.
6. **AQ-09** passes through to SEMANTIC/AGGREGATE, does NOT hit
   LOGISTICS_GUARD (regression anchor for the 14:20 B2 fix).
7. **AQ-10** either RED or semantic-passthrough; never a bogus
   non-zero count.

Post results as `[QA-SIGNOFF: adversarial-sweep]` or `[QA-FAIL:
adversarial-sweep <AQ-id>]` with exact output per failing case.

---

## Source inventory

- `src/query/aggregation_executor.py` -- detector + tier decision
- `src/store/failure_events_store.py` -- parameterized SQL (SQLi
  defense)
- `config/canonical_aliases.yaml` -- alias source of truth
- `docs/aggregation_evidence_contract.md` -- tier rules
- QA 2026-04-19 15:05 signoff (AQ-01, AQ-02, AQ-08, AQ-09
  regression anchors)
- QA 2026-04-19 14:20 B2 guard over-trigger fix

Signed: Researcher | no permanent lane | 2026-04-20 05:45 MDT
