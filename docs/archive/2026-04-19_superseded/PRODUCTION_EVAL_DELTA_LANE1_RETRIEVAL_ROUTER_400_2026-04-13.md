# Production Eval Delta

## Run Scope

- baseline: `20260413_195019`
- new: `20260414_035850`
- baseline queries: `400`
- new queries: `400`
- overlapping IDs compared: `400`

## Headline Delta

- PASS: `226` -> `249` (+23)
- PARTIAL: `78` -> `72` (-6)
- MISS: `96` -> `79` (-17)
- routing correct: `298` -> `301` (+3)
- retrieval P50 ms: `3695` -> `6990` (+3295)
- retrieval P95 ms: `16233` -> `35109` (+18876)

## Verdict Flips

- `MISS -> PARTIAL`: `6`
- `MISS -> PASS`: `17`
- `PARTIAL -> MISS`: `4`
- `PARTIAL -> PASS`: `23`
- `PASS -> MISS`: `2`
- `PASS -> PARTIAL`: `15`

## Routing Flips

- `False -> True`: `5`
- `True -> False`: `2`

## Family Delta

| Family | PASS delta | PARTIAL delta | MISS delta |
| --- | ---: | ---: | ---: |
| Asset Mgmt | +0 | +0 | +0 |
| CDRLs | +10 | +2 | -12 |
| Cybersecurity | -7 | +6 | +1 |
| Engineering | +0 | +0 | +0 |
| Field Engineering | +0 | -1 | +1 |
| Logistics | +22 | -15 | -7 |
| Program Management | +0 | +0 | +0 |
| Site Visits | -1 | +1 | +0 |
| SysAdmin | +0 | +0 | +0 |
| Systems Engineering | -1 | +1 | +0 |
| legacy monitoring system Sites | +0 | +0 | +0 |

## Improved IDs

- `PQ-103`, `PQ-113`, `PQ-136`, `PQ-137`, `PQ-144`, `PQ-147`, `PQ-192`, `PQ-202`, `PQ-203`, `PQ-204`, `PQ-208`, `PQ-210`, `PQ-223`, `PQ-224`, `PQ-225`, `PQ-227`, `PQ-228`, `PQ-231`, `PQ-233`, `PQ-234`, `PQ-237`, `PQ-257`, `PQ-283`, `PQ-285`, `PQ-291`, `PQ-294`, `PQ-321`, `PQ-340`, `PQ-343`, `PQ-345`, `PQ-346`, `PQ-350`, `PQ-356`, `PQ-362`, `PQ-374`, `PQ-383`, `PQ-405`, `PQ-432`, `PQ-440`, `PQ-457`

## Regressed IDs

- `PQ-118`, `PQ-195`, `PQ-196`, `PQ-200`, `PQ-201`, `PQ-226`, `PQ-242`, `PQ-262`, `PQ-296`, `PQ-326`, `PQ-329`, `PQ-376`, `PQ-385`, `PQ-397`, `PQ-402`, `PQ-419`, `PQ-450`, `PQ-475`, `PQ-476`, `PQ-479`, `PQ-481`

