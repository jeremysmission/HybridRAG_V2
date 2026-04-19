# CAP / Incident Path Hints

Source set:
- `tests/golden_eval/production_queries_400_2026-04-12.json`
- `docs/production_eval_results_clean_tier1_2026-04-13.json`
- `docs/CDRL_METADATA_PATH_HINTS_EVIDENCE_2026-04-13.md`
- `docs/CLEAN_BASELINE_RETRIEVAL_FINDINGS_2026-04-13.md`

## What Is Actually Distinguishing The Real Artifacts

The clean baseline shows that CAP / incident / A001-A027 misses are not mainly about missing corpus content. They are mostly about weak path hints and noisy near-matches.

The real artifacts have a few stable signals:

- folder root includes `A001 - Corrective Action Plan (CAP)` for CAP queries
- filenames include `47QFRA22F0009_IGSI-####_Corrective_Action_Plan_...`
- site token is present in the filename, usually right after the incident number
- a date suffix often appears at the end of the filename, usually `YYYY-MM-DD`
- the same artifact may exist in both `1.0 ... /OASIS/` and `1.5 ... /CDRLS/` trees

For A027-style incident/security deliverables, the strongest real-artifact cues are:

- `A027 - DAA Accreditation Support Data (ACAS Scan Results)`
- `A027 - Cybersecurity Assessment Test Report`
- `A027 - RMF Authorization Documentation – Security Plan`
- `A027 - RMF Security Plan`
- `A027 - DAA Accreditation Support Data (CT&E Plan)`
- incident / deliverable IDs like `IGSI-2553`, `IGSI-2891`, `IGSI-481`, `IGSI-966`
- subtype words in the filename such as `ACAS-Scan`, `Scan Results`, `CT&E`, `Plans and Controls`, `Monthly Audit Report`

## Clean-Baseline Failure Shape

The current wrong-route cluster is dominated by CAP / incident questions landing on nearby noise such as:

- `A018 - System Safety Program Plan (SSPP)` because the text mentions CAP-like language
- `Location Documents` / site-selection folders
- `Non-Historical (BDD)` / deliverable-control-log search notes
- `A001 IPT Briefing Slides`
- `A009 Monthly Status Report`
- generic DM/Archive docs that merely mention incident IDs in body text

Representative misses:

- `PQ-130` → landed on `A018 - System Safety Program Plan (SSPP)` instead of the A001 CAP file
- `PQ-147` → landed on `Location Documents/2013-Alpena Hazard Mitigation 2-Environment.pdf`
- `PQ-183` → landed on `A001 IPT Briefing Slides` instead of the Misawa CAP
- `PQ-184` → landed on `Merged BDD Table` noise
- `PQ-186` → landed on `A001 IPT Briefing Slides`
- `PQ-202` → landed on `A001 IPT Briefing Slides`
- `PQ-210` → landed on `DM/p50152s.pdf`

## Exact Query-Anchor Patterns That Help

The corpus itself shows that these query anchors are the right ones to preserve:

- `Corrective Action Plan`
- `CAP`
- `A001`
- `A027`
- `IGSI-####`
- site name tokens:
  - `Fairford`
  - `Misawa`
  - `Learmonth`
  - `Kwajalein`
  - `Alpena`
- date tokens when present:
  - `2024-06-05`
  - `2024-08-16`
  - `2024-10-25`
  - `2025-07-14`
- subtype tokens for A027:
  - `ACAS`
  - `SCAP`
  - `CT&E`
  - `RMF`
  - `Plans and Controls`
  - `Scan Results`

## Smallest Useful Path-Hint Strategy

The smallest likely win is not a new retrieval architecture. It is a narrow path-hint expansion that prefers:

1. `A001 - Corrective Action Plan (CAP)` when the query says CAP / corrective action plan / incident number
2. `IGSI-####` + site token + date-tail filename matches over generic folder mentions
3. `A027 - DAA Accreditation Support Data (ACAS Scan Results)` or `A027 - Cybersecurity Assessment Test Report` when the query says ACAS / scan results / CT&E / cybersecurity assessment / RHEL8
4. `A027 - RMF Authorization Documentation – Security Plan` / `A027 - RMF Security Plan` when the query says RMF / plans and controls / monthly audit / SCAP / CT&E

In practice, the router/retriever should prefer:

- `Corrective_Action_Plan`
- `Corrective-Action-Plan`
- `CAP/`
- `ACAS-Scan`
- `Scan Results`
- `CT&E`
- `Plans and Controls`
- `Monthly Audit Report`

over generic neighbors like:

- `System Safety Program Plan`
- `IPT Briefing Slides`
- `Location Documents`
- `BDD Table`
- generic `Archive` / `DM_Backup`

## Ranked Next-Step Recommendations

1. Add a narrow CAP path hint: boost `A001 - Corrective Action Plan (CAP)` when the query contains `CAP`, `Corrective Action Plan`, or `incident IGSI-####`, and prefer filenames that also contain a site token and optional date suffix.
2. Add an A027 incident/security path hint: boost the exact A027 subfolder names above plus `IGSI-####` + subtype tokens (`ACAS`, `CT&E`, `SCAP`, `RMF`, `Plans and Controls`).
3. Prefer full filename matches over body-text-only matches when the query names an incident ID and a site.
4. Keep query-side hints narrow: exact `IGSI-####`, `A001`, `A027`, site, date, and subtype tokens. Do not widen to generic “report” / “archive” hints, or the router will keep landing on briefing slides and BDD noise.
5. If one more change is needed after that, make it a ranking hint in the candidate pool / reranker, not a broad router rewrite.

## Practical Bottom Line

For these misses, the corpus is already telling us the answer:

- use the CAP folder name
- use the incident number
- use the site name
- use the date suffix
- use the A027 subtype phrase

The failure mode is almost always “generic folder or slide deck that mentions the right words in body text outranks the real filed deliverable.” The smallest fix is to bias toward exact path prefixes and filename tokens that encode the filed artifact, not just the narrative surrounding it.
