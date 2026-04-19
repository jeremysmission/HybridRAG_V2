# Clean Tier1 Baseline Followon Priorities 2026-04-13

## Purpose

This doc freezes the first post-clean-baseline synthesis so future coordinator
passes do not need to rediscover the same findings.

Primary evidence:

- `docs/PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md`
- `docs/production_eval_results_clean_tier1_2026-04-13.json`
- targeted post-baseline query probes run on the clean config

## Clean Baseline Headline

- PASS: `158/400` (`40%`)
- PARTIAL: `96/400`
- PASS+PARTIAL: `254/400` (`64%`)
- MISS: `146/400`
- routing correct: `287/400` (`72%`)

This confirms the rebuilt path is real, but the remaining misses are still
concentrated enough to justify targeted retrieval and routing work rather than
broad untuned changes.

## Immediate Correctness Fixes Already Landed

### 1. Per-persona report mismatch fixed

The clean markdown report initially showed a false `0/0` row for
`Cybersecurity / Network Admin` because the renderer used the stale persona
label `Network Admin / Cybersecurity` while the 400-query corpus and JSON
results use `Cybersecurity / Network Admin`.

Fix:

- `scripts/run_production_eval.py`

Effect:

- rebuilt clean markdown report now matches the JSON truth row:
  - `80 total`
  - `31 PASS`
  - `21 PARTIAL`
  - `28 MISS`
  - `55/80 routing correct`

### 2. Retrieval candidate-pool wiring fixed

The clean baseline review exposed a real retrieval wiring defect:

- config already declares `retrieval.candidate_pool: 30`
- FlashRank reranking is enabled
- but the main retrieval path was only fetching `top_k` candidates from
  LanceDB before handing results to the context builder

That meant reranking often had nothing larger than the final `top_k` to work
with.

Fixes landed in:

- `src/query/vector_retriever.py`
- `src/query/pipeline.py`
- `scripts/boot.py`
- `src/api/server.py`
- `src/gui/launch_gui.py`
- `scripts/run_golden_eval.py`
- `scripts/run_production_eval.py`
- `scripts/run_ragas_eval.py`
- `tests/test_candidate_pool_wiring.py`

Verification:

- `python -m pytest -q tests/test_candidate_pool_wiring.py`
- `python -m pytest -q tests/test_reranker_path_aware.py`

Important note:

- this improves the real pipeline path immediately
- the current production-eval harness still reports a separate raw vector-search
  view for uniform top-result reporting, so not every reranker gain will be
  visible until the harness is upgraded to score the actual pipeline context
  ordering

## Highest-Yield Failure Clusters

### MISS by expected family

- `CDRLs`: `86`
- `Logistics`: `49`
- all other families combined: `11`

### PARTIAL by expected family

- `Logistics`: `36`
- `CDRLs`: `30`
- `Cybersecurity`: `19`

### Routing-wrong concentration

- `SEMANTIC -> ENTITY`: `37`
- `ENTITY -> TABULAR`: `25`
- `SEMANTIC -> TABULAR`: `15`

Wrong-route misses are also concentrated in the same two families:

- `CDRLs`: `15`
- `Logistics`: `15`

## What The Misses Actually Look Like

### CDRLs

Representative clean-baseline misses:

- `PQ-103` — “Which CDRL is A002 and what maintenance service reports have been submitted under it?”
- `PQ-109` — “What does the Program Management Plan (CDRL A008) say about contract deliverables and schedules?”
- `PQ-159` — “What is the Priced Bill of Materials in CDRL A014 for the enterprise program?”
- `PQ-161` — “What has been delivered under CDRL A025 Computer Operation Manual and Software User Manual?”

Observed pattern:

- retrieval often finds DID references or nearby program-management material
- it does not reliably surface the actual filed deliverable instance or the
  specific CDRL family folder quickly enough
- CDRL-coded questions are still too dependent on exact folder/file naming and
  path context

Concrete evidence from the clean baseline:

- `PQ-103` top hit was `A002--Maintenance Service Report/DI-MGMT-80995A.pdf`
  rather than the actual submitted MSR corpus
- `PQ-159` top hit was `A014--Bill of Materials/DI-MGMT-81994A.pdf` rather
  than the actual PBOM deliverable instance

Interpretation:

- the system is recognizing the code family, but it is not yet anchored tightly
  enough on the difference between DID reference material and filed
  deliverables

### Logistics

Representative clean-baseline misses:

- `PQ-163` — Learmonth August 2024 shipment / destination type
- `PQ-165` — Thule July 2024 ASV shipment / travel mode
- `PQ-166` — Ascension Mil-Air shipment in February 2024
- `PQ-171` — Azores return equipment shipment of `2024-06-14`
- `PQ-172` — Djibouti return shipment of October 2024

Observed pattern:

- retrieval often finds the right site family but the wrong year, wrong visit,
  or a nearby logistics/travel document instead of the target packing-list
  folder
- date + site + shipment-mode/path cues are not being emphasized enough

Concrete evidence from the clean baseline:

- `PQ-163` surfaced older Learmonth visit/support material instead of the
  `2024_08_26 - Learmonth (Comm)` shipment folder
- `PQ-165` surfaced transportation-regulation files and a 2021 Thule ASV visit
  artifact ahead of the `2024_07_18 - Thule (Mil-Air)` shipment folder
- `PQ-172` surfaced generic return-shipping material and unrelated Djibouti
  files instead of the October 2024 target

Interpretation:

- the remaining gap is heavily path-oriented
- site/date/shipment queries need stronger path-aware anchoring than they are
  getting from the current hybrid search alone

## Targeted Post-Patch Probe Notes

After the candidate-pool fix, a small clean-config probe against representative
queries showed the actual pipeline context is already closer to the right
families than the raw-vector-only report implies, but not yet good enough to
close the core misses:

- `PQ-103` now surfaces the A002 DID plus adjacent A027 deliverable material,
  but still not the submitted A002 MSR corpus strongly enough
- `PQ-159` surfaces the A014 DID immediately, but still not the actual PBOM
  deliverable instance
- `PQ-163` surfaces Learmonth shipment-family material, but still misses the
  exact August 2024 shipment folder as the dominant hit
- `PQ-165` still needs better site/date/mode anchoring for the July 2024 Thule
  shipment

## Recommended Next Engineering Order

### Priority 1: CDRL path-aware retrieval

Objective:

- distinguish CDRL DID/reference material from actual filed deliverables

Likely work:

- deterministic query expansions for `CDRL Axxx` queries
- stronger path/file-name weighting for `Axxx`, deliverable title, and
  deliverable-instance patterns
- explicit bias toward filed deliverables when the query asks “what has been
  submitted/delivered/filed” rather than “what does this DID describe”

### Priority 2: Logistics shipment/date/site retrieval

Objective:

- make shipment queries land on the exact packing-list / shipment folder before
  nearby travel or legacy support material

Likely work:

- deterministic expansion for site/date shipment questions
- path-aware weighting for exact site names and normalized date forms
- stronger emphasis on `packing list`, shipment mode, and return-shipment cues

### Priority 3: Router cleanup on the concentrated error pairs

Objective:

- reduce the high-volume wrong-route cases that still sabotage otherwise good
  retrieval

Most important pairs:

- `SEMANTIC -> ENTITY`
- `ENTITY -> TABULAR`
- `SEMANTIC -> TABULAR`

This should be evidence-driven against the clean baseline, not a broad router
rewrite.

### Priority 4: Eval harness upgrade

Objective:

- score the actual pipeline retrieval/context ordering, not just a separate raw
  vector probe

Rationale:

- now that candidate-pool + reranker are correctly wired, the harness should
  expose those gains honestly

## Recommended Immediate Sequence

1. keep the corrected clean baseline artifacts frozen
2. keep the candidate-pool retrieval fix
3. implement CDRL-focused retrieval/path improvements
4. implement logistics shipment/date/site retrieval/path improvements
5. rerun the clean 400 baseline
6. then tighten the router on the newly measured wrong-route residue

## Bottom Line

The clean baseline says the next work should be narrow and mechanical, not
speculative:

- CDRL retrieval
- Logistics retrieval
- then router cleanup

The highest-leverage immediate code fix after clean Tier 1 was not another regex
change. It was restoring the configured retrieval candidate pool so reranking
can finally operate on the wider search set the architecture already expected.
