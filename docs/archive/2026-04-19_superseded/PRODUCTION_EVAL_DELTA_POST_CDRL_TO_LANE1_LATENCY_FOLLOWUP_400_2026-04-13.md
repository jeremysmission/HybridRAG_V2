# Production Eval Delta

## Run Scope

- baseline: `20260413_195019`
- new: `20260414_055334`
- baseline queries: `400`
- new queries: `400`
- overlapping IDs compared: `400`

## Headline Delta

- PASS: `226` -> `249` (+23)
- PARTIAL: `78` -> `71` (-7)
- MISS: `96` -> `80` (-16)
- routing correct: `298` -> `300` (+2)
- retrieval P50 ms: `3695` -> `6085` (+2390)
- retrieval P95 ms: `16233` -> `25997` (+9764)

## Verdict Flips

- `MISS -> PARTIAL`: `3`
- `MISS -> PASS`: `17`
- `PARTIAL -> MISS`: `3`
- `PARTIAL -> PASS`: `22`
- `PASS -> MISS`: `1`
- `PASS -> PARTIAL`: `15`

## Routing Flips

- `False -> True`: `6`
- `True -> False`: `4`

## Family Delta

| Family | PASS delta | PARTIAL delta | MISS delta |
| --- | ---: | ---: | ---: |
| Asset Mgmt | +0 | +0 | +0 |
| CDRLs | +11 | -2 | -9 |
| Cybersecurity | -5 | +5 | +0 |
| Engineering | +0 | +0 | +0 |
| Field Engineering | -1 | +0 | +1 |
| Logistics | +21 | -13 | -8 |
| Program Management | -1 | +1 | +0 |
| Site Visits | -1 | +1 | +0 |
| SysAdmin | +0 | +0 | +0 |
| Systems Engineering | -1 | +1 | +0 |
| legacy monitoring system Sites | +0 | +0 | +0 |

## Improved IDs

- `PQ-113`, `PQ-136`, `PQ-137`, `PQ-144`, `PQ-147`, `PQ-192`, `PQ-202`, `PQ-203`, `PQ-204`, `PQ-208`, `PQ-210`, `PQ-223`, `PQ-224`, `PQ-225`, `PQ-227`, `PQ-228`, `PQ-231`, `PQ-233`, `PQ-234`, `PQ-237`, `PQ-255`, `PQ-257`, `PQ-285`, `PQ-291`, `PQ-294`, `PQ-321`, `PQ-343`, `PQ-345`, `PQ-346`, `PQ-350`, `PQ-362`, `PQ-374`, `PQ-383`, `PQ-405`, `PQ-432`, `PQ-457`, `PQ-458`, `PQ-459`, `PQ-462`, `PQ-477`

## Regressed IDs

- `PQ-118`, `PQ-154`, `PQ-170`, `PQ-195`, `PQ-196`, `PQ-201`, `PQ-262`, `PQ-296`, `PQ-306`, `PQ-326`, `PQ-329`, `PQ-376`, `PQ-399`, `PQ-419`, `PQ-449`, `PQ-475`, `PQ-476`, `PQ-479`, `PQ-481`

