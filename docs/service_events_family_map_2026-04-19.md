# Service Events Family Map — 2026-04-19

**Author:** Miner-Agent | no lane | 2026-04-19 MDT
**Corpus:** `E:\CorpusTransfr\file_state.sqlite3` (214,751 files)
**Companion JSON:** `docs/service_events_family_map_2026-04-19.json`

---

## Executive Summary

The corpus contains **15,398 files** matching 20 service-event patterns. The highest-yield families for a future `service_events` substrate are outage reports (1,649), trip reports (513), restoral events (789), and corrective action plans (83). NEXION dominates service documentation; ISTO coverage is sparser. Year coverage spans 2008-2026 with peak density 2013-2019.

---

## Top Service Event Families

| # | Family | Count | NEXION | ISTO | Notes |
|---|--------|------:|-------:|-----:|-------|
| 1 | cdrl | 3,009 | 2,259 | 418 | All CDRL deliverables (broad) |
| 2 | outage_all | 2,352 | 1,503 | 522 | Includes photos + docs |
| 3 | deliverable_report | 1,953 | 1,078 | 501 | CDRL deliverable reports |
| 4 | outage_report | 1,649 | 1,049 | 458 | Outage reports (docs only) |
| 5 | repair | 994 | 465 | 393 | Repair activities |
| 6 | restoral | 789 | 521 | 163 | System restoral events |
| 7 | trip_report | 513 | 380 | 89 | Trip reports (CDRL A045B) |
| 8 | monthly_audit | 2,616 | 978 | 1,042 | Monthly security audits |
| 9 | replace | 774 | 588 | 88 | Component replacements |
| 10 | troubleshoot | 290 | 218 | 43 | Troubleshooting sessions |
| 11 | daily_status | 175 | 161 | 0 | Daily install status |
| 12 | corrective_action | 83 | 55 | 17 | Corrective Action Plans |
| 13 | weekly_status | 64 | 30 | 12 | Bi-weekly meetings |
| 14 | swap | 38 | 37 | 0 | Component swaps |
| 15 | maintenance_task | 31 | 1 | 30 | Maintenance task docs |

---

## Recommendations

### For a `service_events` substrate (future sprint)

**Tier 1 — Start here:**
- `outage_report` (1,649) — structured outage event records
- `trip_report` (513) — site visit reports with service outcomes
- `corrective_action` (83) — formal CAP documents with root cause

**Tier 2 — Enrichment:**
- `restoral` (789) — system recovery timestamps
- `repair` (994) — repair action records
- `replace` (774) — component replacement events

**Tier 3 — Supporting:**
- `monthly_audit` (2,616) — periodic status for trend analysis
- `deliverable_report` (1,953) — formal CDRL submissions

### Extractor design notes

The existing `failure_events` substrate already captures 35,649 events from path-regex extraction. A `service_events` substrate would complement it by capturing:
- Outage duration and resolution details
- Trip report service outcomes (what was fixed/replaced)
- Corrective action root causes
- Restoral timestamps (system back online)

These are content-level signals, not just path-level — they require chunk-pass extraction with field heuristics for event_type, duration, resolution_action, and root_cause.

---

Miner-Agent | no lane | 2026-04-19 MDT
