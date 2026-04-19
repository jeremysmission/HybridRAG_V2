# Production Eval Delta

## Run Scope

- baseline: `20260414_035850`
- new: `20260414_055334`
- baseline queries: `400`
- new queries: `400`
- overlapping IDs compared: `400`

## Headline Delta

- PASS: `249` -> `249` (+0)
- PARTIAL: `72` -> `71` (-1)
- MISS: `79` -> `80` (+1)
- routing correct: `301` -> `300` (-1)
- retrieval P50 ms: `6990` -> `6085` (-905)
- retrieval P95 ms: `35109` -> `25997` (-9112)

## Verdict Flips

- `MISS -> PARTIAL`: `3`
- `MISS -> PASS`: `2`
- `PARTIAL -> MISS`: `4`
- `PARTIAL -> PASS`: `4`
- `PASS -> MISS`: `2`
- `PASS -> PARTIAL`: `4`

## Routing Flips

- `False -> True`: `1`
- `True -> False`: `2`

## Family Delta

| Family | PASS delta | PARTIAL delta | MISS delta |
| --- | ---: | ---: | ---: |
| Asset Mgmt | +0 | +0 | +0 |
| CDRLs | +1 | -4 | +3 |
| Cybersecurity | +2 | -1 | -1 |
| Engineering | +0 | +0 | +0 |
| Field Engineering | -1 | +1 | +0 |
| Logistics | -1 | +2 | -1 |
| Program Management | -1 | +1 | +0 |
| Site Visits | +0 | +0 | +0 |
| SysAdmin | +0 | +0 | +0 |
| Systems Engineering | +0 | +0 | +0 |
| legacy monitoring system Sites | +0 | +0 | +0 |

## Improved IDs

- `PQ-200`, `PQ-226`, `PQ-242`, `PQ-255`, `PQ-385`, `PQ-397`, `PQ-402`, `PQ-419`, `PQ-450`

## Regressed IDs

- `PQ-103`, `PQ-154`, `PQ-170`, `PQ-283`, `PQ-306`, `PQ-340`, `PQ-356`, `PQ-399`, `PQ-440`, `PQ-449`

