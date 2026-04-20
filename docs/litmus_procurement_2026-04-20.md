# Litmus Procurement & Shipments Ground Truth

**Author:** Miner-Agent | no lane | 2026-04-20 MDT
**JSON:** `docs/litmus_procurement_2026-04-20.json`

---

## Procurement (002 - Received)

- **2,935 files** in Received folder
- **61 distinct PO numbers** extracted from folder/file names
- **18 contract period folders** (organized by sustainment year + installation)
- Contract periods span **Aug 2022 through Jul 2026** (4 fiscal years)

### Top Contract Periods by File Count

| Period | Files |
|--------|------:|
| NEXION Sustainment Base Year (1 Aug 22 - 31 Jul 23) | 450 |
| NEXION Sustainment OY1 (1 Aug 23 - 31 Jul 24) | 436 |
| Okinawa Installation | 364 |
| NEXION Sustainment NEW BASE YR (1 Aug 25 - 31 Jul 26) | 320 |
| Azores NEXION Install | 292 |
| NEXION Sustainment OY2 (1 Aug 24 - 31 Jul 25) | 202 |
| Niger ISTO Installation | 188 |
| ISTO Sustainment Base Year (1 Aug 22 - 31 Jul 23) | 108 |

## Shipments (by year)

| Year | Files |
|------|------:|
| 2022 | 41 |
| 2023 | 298 |
| 2024 | 319 |
| 2025 | 230 |
| 2026 | 128 |
| **Total** | **1,016** |

**36 distinct shipment destinations** including all major sites.

## Agent-B Ground Truth

For B5 benchmark validation:
- Procurement has **continuous 2022-2026 coverage** (the P3 date gap was in date parsing, not data)
- Sustainment contract periods provide a natural date-range bucketing for PO grouping
- Shipments folder confirms 2023-2026 delivery activity

---

Miner-Agent | no lane | 2026-04-20 MDT
