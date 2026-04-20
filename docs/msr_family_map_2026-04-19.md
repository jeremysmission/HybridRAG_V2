# MSR (Maintenance/Service Report) Family Map

**Author:** Miner-Agent | no lane | 2026-04-20 MDT
**JSON:** `docs/msr_family_map_2026-04-19.json`

---

## Summary

331 distinct site visit folders across 31 sites. Two dominant maintenance visit types: **ASV (Annual Service Visit)** with 95 visits / 32,419 files, and **RTS (Return To Service)** with 48 visits / 10,140 files.

## Visit Type Distribution

| Type | Visits | Files | Notes |
|------|-------:|------:|-------|
| Other | 136 | - | Data collection, cable work, GPS repair, decommissioning |
| ASV | 95 | 32,419 | Annual recurring. Dominant 2015+ |
| RTS | 48 | 10,140 | Return to service after outage/maintenance |
| Install | 40 | 38,715 | System installation. Dominant 2008-2014, high file count |
| Survey | 23 | 7,668 | Site surveys and characterization |
| Upgrade | 7 | 179 | OS/hardware upgrades |
| Selection | 4 | - | Site selection visits |
| Repair | 3 | - | Targeted repair missions |

## Structured Deliverables

- **336 Trip Report PDFs/DOCX** — the primary structured output per visit
- **302 CDRL A045B tagged** — formal trip report deliverables

## Recommended Schema for `site_visits` Substrate

```sql
CREATE TABLE site_visits (
    id INTEGER PRIMARY KEY,
    site_token TEXT NOT NULL,
    visit_type TEXT NOT NULL,  -- ASV, RTS, Install, Survey, Upgrade, Repair, Other
    system TEXT,               -- NEXION, ISTO, both
    start_date TEXT,           -- from folder name YYYY-MM-DD
    end_date TEXT,             -- from folder name "thru MM-DD"
    travelers TEXT,            -- from parenthetical in folder name
    trip_report_path TEXT,     -- path to CDRL A045B deliverable
    source_folder TEXT
);
```

---

Miner-Agent | no lane | 2026-04-20 MDT
