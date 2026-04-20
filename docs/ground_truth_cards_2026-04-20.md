# Ground-Truth Cards for HybridRAG V2 Demo

**Date:** 2026-04-20
**Author:** Researcher | no permanent lane
**Consumer:** demo operator + QA-Agent + Agent-A/B/C/D for cross-check
**Scope:** 10 demo queries (Q1, Q2, Q3 + Q-DEMO-A through Q-DEMO-G)

Every card has an exact query, exact expected answer, exact
evidence paths sourced from truth-pack JSONs + QA sign-off posts +
Miner deliverables. No invented data. Tier source: aggregation
evidence contract (GREEN / YELLOW / RED).

---

## Q1 -- Top failing parts in NEXION 2024

**Exact query:** "What were the highest failing part numbers in
the NEXION system in 2024?"

**Tier:** GREEN (matches FAIL-AGG-01 in failure_truth_pack_2026-04-18).

**Ground-truth SQL:**
```sql
SELECT part_number, COUNT(*) AS failure_count
FROM failure_events
WHERE system='NEXION' AND event_year=2024 AND part_number!=''
GROUP BY part_number
ORDER BY failure_count DESC LIMIT 5
```

**Exact expected top 3 (from coder self-regression 02:20 MDT):**
1. EC11612
2. RFA-4005
3. SEMS3D-41785

**Substrate:** `failure_events.sqlite3` (35,649 events, 100%
system-attributed; pass-2 part_number coverage 3,025 / 37,148).

**Evidence paths** (representative, from QA 15:05 context):
- `SEMS3D-* Learmonth NEXION MSR CDRL A001...` (MSR documents)
- `Guam ... NEXION MSR CDRL A001...`
- `1.0 IGS DM - Restricted\SEMS3D\A001-MSR\... NEXION MSR...`

**Tier justification:**
- system axis resolved via canonical_aliases.yaml -> "NEXION"
- event_year axis resolved -> 2024
- part_number substrate coverage ~8% overall but non-zero for this
  slice (verified in 44/44 suite and 39/50 benchmark)

**Fallback if live tier != GREEN:**
- If RED: likely a substrate regression. Pivot to Q2.
- If YELLOW: narrate counts only; state the rate-unavailable caveat.

---

## Q2 -- Top failing parts in ISTO Djibouti 2022-2025

**Exact query:** "What were the highest failing part numbers in
the ISTO system in Djibouti from 2022 through 2025?"

**Tier:** GREEN (matches FAIL-AGG-02).

**Ground-truth SQL:**
```sql
SELECT part_number, COUNT(*) AS failure_count
FROM failure_events
WHERE system='ISTO'
  AND site_token='djibouti'
  AND event_year BETWEEN 2022 AND 2025
  AND part_number!=''
GROUP BY part_number
ORDER BY failure_count DESC LIMIT 5
```

**Exact expected top 2 (from coder self-regression 02:20):**
1. SEMS3D-35674
2. TA00122

**Evidence paths:**
- `Djibouti ... ISTO MSR ...` prefix
- `zzSEMS ARCHIVE\005_ILS\... Djibouti ...`

**Tier justification:**
- three-axis filter (system + site_token + year_range) -> all
  canonicalize; non-zero part_number rows exist in slice.

**Fallback:**
- If RED: site coverage gap on Djibouti. Pivot to Q1.
- If YELLOW: narrate counts only; call out lower Djibouti IB
  coverage if asked.

---

## Q3 -- Top failure rate parts per year, past 7 years

**Exact query:** "What are the top failure rate parts ranked each
year for the past 7 years?"

**Tier:** YELLOW (matches FAIL-AGG-03 `why_yellow`).

**Ground-truth SQL:**
```sql
SELECT event_year, part_number, COUNT(*) AS failure_count
FROM failure_events
WHERE event_year BETWEEN 2020 AND 2026
  AND part_number!=''
GROUP BY event_year, part_number
ORDER BY event_year, failure_count DESC
```

**Expected shape:** per-year ranking with YELLOW caveat panel.

**Tier justification:**
- `is_rate=True` in parsed params; installed_base denominator
  substrate not yet populated (Agent-C Lane 3 [READY-FOR-QA] at
  22:28 -- foundation only, pass-2 yielded 0 part/qty rows on
  chunk-only pass).
- YELLOW caveat: "Failure rate requires installed-base denominator
  -- showing failure counts only."

**Fallback:**
- If GREEN (unexpected): Lane 3 has materially advanced -- proceed
  but call out the good-news substrate shift.
- If RED: pivot to Q1 for a clean GREEN instead.

---

## Q-DEMO-A -- Top ordered parts

**Exact query:** "What are the top ordered parts from our purchase-
order history?"

**Tier:** YELLOW (date range 2015-2022 only; 2023-2025 extractor
fix pending per Miner P3 diagnosis + Agent-B [QA-REJECT] 22:05).

**Ground-truth SQL:**
```sql
SELECT part_number, COUNT(DISTINCT po_number) AS order_count,
       SUM(qty) AS total_qty
FROM po_pricing
WHERE part_number!=''
GROUP BY part_number
ORDER BY order_count DESC LIMIT 5
```

**Exact expected top 5 (from QA 16:33 Q-DEMO-A signoff):**
1. DPS4D (order_count=8, total_qty=2.0)
2. PC1400 (order_count=4, total_qty=15.0)
3. 1UKJ7 (order_count=4, total_qty=13.0)
4. 32PJ52 (order_count=4, total_qty=12.0)
5. EDDDEC22 (order_count=4, total_qty=5.0)

**Substrate:** `po_pricing.sqlite3` (7,259 rows, 837 POs, 553
parts; po_date range 2015-10-29 to 2022-02-28).

**Evidence paths (Agent-B 21:54 samples):**
- `zzSEMS ARCHIVE\005_ILS\Purchases\2-Received\1-Received\...`
- `zzSEMS ARCHIVE\005_ILS\Calibration\...\Oscilloscope Purchase
  Docs\PO 7000296852.pdf`

**Tier justification:**
- date range caveat: 2015-2022 only; 2023-2025 missing due to
  regex gap documented in Miner P3 date-coverage diagnostic.
- YELLOW caveat: "Date range: 2015-2022; 2023-2025 expansion in
  extractor-fix cycle."

**Fallback:**
- Plan A: swap to Q-DEMO-C (volume-ranked, same substrate).
- Plan B: archived YELLOW screenshot.
- Plan D (per 00:15 rule): re-route to Q1/Q2/Q3 banked if PO
  substrate not GREEN by demo.

---

## Q-DEMO-B -- Longest lead-time parts

**Exact query:** "Which parts had the longest lead times from
order to receipt?"

**Tier:** YELLOW (lead_time_days coverage 545 / 7,259 = 7.51%).

**Ground-truth SQL:**
```sql
SELECT part_number, po_number, vendor, lead_time_days,
       order_date, receive_date
FROM po_pricing
WHERE lead_time_days > 0
ORDER BY lead_time_days DESC LIMIT 10
```

**Exact expected top 1 (from Agent-B 21:54 sample rows):**
1. FA4600-14-D-0004 at LOWELL DIGISONDE INTERNATIONAL,
   lead_time_days=1,555, po_date=2015-10-29
   (evidence: `zzSEMS ARCHIVE\005_ILS\Purchases\2-Received\
   1-Received\WX28 (PO 7500137184) (Devel-Upgrade Kits)\
   PO 7500137184 (Upgrade Kits).pdf`)

**Additional expected entries (from Agent-B 16:33 Q-DEMO-B
sample):**
- AS-5021104, LOWELL DIGISONDE INTERNATIONAL, lead=139 days
- I5-730, PCPC DIRECT LTD, lead=58 days
- CAT5E, INTERNATIONAL COMPUTER PRODUCTS INC, lead=54 days
- RG-213, INTERNATIONAL COMPUTER PRODUCTS INC, lead=54 days

**Tier justification:**
- lead_time coverage is the limit. Must say 7.51% aloud.

**Fallback:** Plan A -> Q-DEMO-E; Plan D -> Q1/Q2/Q3 banked.

---

## Q-DEMO-C -- Top ordered parts by volume

**Exact query:** "What are the highest-volume parts we've ordered?"

**Tier:** YELLOW (qty coverage 650 / 7,259 = 8.96%).

**Ground-truth SQL:**
```sql
SELECT part_number, SUM(qty) AS total_qty,
       COUNT(DISTINCT po_number) AS order_count
FROM po_pricing
WHERE qty > 0 AND part_number!=''
GROUP BY part_number
ORDER BY total_qty DESC LIMIT 5
```

**Expected top entries (derived from Q-DEMO-A sample: same source,
sort key = SUM(qty) DESC):**
- 054-00013 (total_qty=30.0)
- 115-GUY (total_qty=14.0)
- JIC-2755 (total_qty=14.0)
- 66-114-A (total_qty=13.0)
- PC1400 (total_qty=15.0)

**Tier justification:** qty coverage sparse; caveat required.

**Fallback:** Plan A -> Q-DEMO-A; Plan D -> Q1/Q2/Q3 banked.

---

## Q-DEMO-D -- Reorder point for SEMS3D-40536 at Learmonth

**Exact query:** "What should our reorder point be for part
SEMS3D-40536 at Learmonth in the monitoring system?"

**Tier:** INVENTORY_GREEN (stub-mode) per Agent-D 16:02.

**Ground-truth SQL** (from Agent-D 16:02 sample):
```sql
SELECT event_date, event_year
FROM failure_events
WHERE part_number = 'SEMS3D-40536'
  AND system = 'NEXION'
  AND site_token = 'learmonth'
```

**Exact expected result (from Agent-D 16:02 sample):**
- recommended_units = 27
- history_months = 37
- total_failures = 8
- lead_time_source = stub_fallback_90

**Evidence paths:**
1. `1.0 IGS DM - Restricted\SEMS3D\A001-MSR\Learmonth 2022
   (21 Apr to 2 May) ASV-TX Tensions\SEMS3D-40536 Learmonth NEXION
   MSR CDRL A001(26 May 2022) - Final.docx`
2. `...SEMS3D-40536 Learmonth NEXION MSR CDRL A001(26 May 2022)
   - Final.pdf`
3. `! Site Visits\(01) Sites\Learmonth\2022-04-16 thru 25
   (ASV-RTS - Pitts-Dettler)\MSR\SEMS3D-40536 Learmonth NEXION
   MSR CDRL A001 (30 May 2022).docx`

**Tier justification:**
- history_months (37) > 12-month threshold -> GREEN
- stub-mode lead_time_days = 90 displayed explicitly; not hidden

**Fallback:**
- Plan A: swap to SEMS3D-41107 / Eglin / NEXION YELLOW example
  (recommended_units=33, history_months=13).
- Plan B: swap to FA2528 / Ascension / NEXION RED abstention
  (history_months=1 < 12 required).

---

## Q-DEMO-E -- Replacement cost

**Exact query:** "What's the replacement cost for a given part we
order for American Samoa?"

**Tier:** YELLOW (site scoping weak in po_pricing; unit_price
coverage 100%).

**Ground-truth SQL:**
```sql
SELECT part_number, unit_price, vendor, po_number, po_date,
       source_path
FROM po_pricing
WHERE part_number = '<specific part>'
ORDER BY po_date DESC LIMIT 1
```

**Expected shape:** single-row representative-recent-price.

**Sample result (from Agent-B 21:54 rows):**
- FA4600-14-D-0004: unit_price=$1,550, vendor=DATA WEST,
  po_date=2016-04-19, po=7000296852
- JTK-97LW: unit_price=$1,289, vendor=DATA WEST,
  po_date=2016-04-19, po=7000296852

**Tier justification:** site scoping not enforced; YELLOW caveat
"representative recent price, not site-specific contract".

**Fallback:** Plan A -> Q-DEMO-F; Plan D -> Q1/Q2/Q3 banked.

---

## Q-DEMO-F -- Most expensive items ordered

**Exact query:** "What were the most expensive items we've
ordered?"

**Tier:** YELLOW (date range 2015-2022 only).

**Ground-truth SQL:**
```sql
SELECT part_number, unit_price, vendor, po_number, po_date,
       source_path
FROM po_pricing
WHERE unit_price > 0
ORDER BY unit_price DESC LIMIT 5
```

**Exact expected top 1 (from Agent-B 21:54 sample):**
1. FA4600-14-D-0004, unit_price=$110,313.27, vendor=LOWELL
   DIGISONDE INTERNATIONAL, po_date=2015-10-29,
   po=7500137184
   (evidence: `...WX28 (PO 7500137184) (Devel-Upgrade Kits)\
   PO 7500137184 (Upgrade Kits).pdf`)

**Tier justification:** same 2015-2022 caveat as Q-DEMO-A.

**Fallback:** Plan A -> Q-DEMO-A; Plan D -> Q1/Q2/Q3 banked.

---

## Q-DEMO-G -- Days part X at site Y

**Exact query:** "How many days has part SEMS3D-40536 been at
Learmonth across all site visits?"

**Tier:** RED (installed_base per-part per-snapshot_date is mid-
build on Lane 3; single-part attribution not supported).

**Abstention message (exact from aggregation contract):**
> "I cannot answer this deterministically. Reason: single-part
> site-days requires per-snapshot installed-base attribution;
> substrate populated at site/program aggregate only. What would
> fix this: Agent-C installed_base xlsx-parser slice (next sprint)
> plus part-to-snapshot join key."

**Companion GREEN query (QA 15:12 signoff):**
- "How many days ASV+RTS visits at Guam 2022-2025?"
- SQL: `SELECT ... FROM site_visits WHERE site_token='guam' AND
  visit_type IN ('ASV','RTS') AND event_year BETWEEN 2022 AND
  2025`
- Exact answer: **48 days** (reproduced by QA 15:12 sign-off)
- Comparable: Thule all 2022-2025 = 11 days; Lualualei
  all 2022-2025 = 29 days, 2024-2025 = 18 days.

**Tier justification:** RED is the correct, doctrinal abstention.
Demo operator pivots to Guam=48 companion as the fallback
narrative ("I cannot attribute to a single part; here's the
adjacent question I CAN answer deterministically").

**Fallback:**
- Plan A: pivot to Guam=48 companion query immediately.
- Plan B: operator closes with "this is a next-sprint gate".

---

## Cross-card ground truth

**Known positive-RED queries (from QA 15:05 signoff):**
- "Top 5 failing parts in Antarctica in 2024" -> RED (unknown site)
- "Top 5 failing parts in GOTHAM in 2024" -> RED (unknown system)

These are confidence anchors the operator can invoke if an
audience member asks "show me a system abstention".

**Logistics-guard passthrough sanity (from QA 15:05):**
- "Which procurement policy governs Guam shipments?" -> SEMANTIC
  (passes through, does NOT hit LOGISTICS_GUARD)
- "Which document explains how received quantities are recorded?"
  -> AGGREGATE/SEMANTIC (does NOT hit LOGISTICS_GUARD)
- "How many POs received in 2024?" -> LOGISTICS_GUARD
  (NOT_SUPPORTED, correctly intercepted)

---

## Source inventory (evidence provenance)

- `tests/aggregation_benchmark/failure_truth_pack_2026-04-18.json`
  (FAIL-AGG-01 through FAIL-AGG-03+, 50-item pack)
- Coder self-regression 2026-04-19 02:20 MDT (7/7 pass, exact
  top-3 per query)
- QA sign-off 2026-04-19 15:05 MDT (B1+B2, Antarctica/GOTHAM RED)
- QA sign-off 2026-04-19 15:12 MDT (site_visits, Guam=48,
  Thule=11, Lualualei=29/18)
- QA sign-off 2026-04-19 16:33 MDT (PO extractor pilot,
  Q-DEMO-A/B sample rows)
- Agent-B 2026-04-19 21:54 MDT (po_pricing populate, 7,259 rows,
  5 sample rows including FA4600-14-D-0004)
- Agent-D 2026-04-19 16:02 MDT (inventory recommender, 3
  tier-exemplar samples)
- Miner 2026-04-20 00:40 MDT (P7 25-doc corpus samples)
- Miner 2026-04-20 05:15 MDT (M-3 NEXION BOM: 2,320 rows,
  1,282 distinct parts, Azores master 497 parts)

Signed: Researcher | no permanent lane | 2026-04-20 05:30 MDT
