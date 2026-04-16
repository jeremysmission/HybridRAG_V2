# Sprint Slice: Product Completion Plan (2026-04-13)

**Owner:** Jeremy Randall
**Repos:** `C:\HybridRAG_V2` + `C:\CorpusForge`
**Purpose:** Convert the current retrieval-first progress into an honest May 2 demo, then into the fuller structured product without breaking benchmark integrity or overclaiming aggregation readiness.

## This Slice Does Not Replace The Active GUI Slice

- The active 400-query GUI slice stays separate:
  - `C:\HybridRAG_V2\docs\SPRINT_SLICE_EVAL_GUI_2026-04-13.md`
- This document is the master dependency and execution-order plan for the remaining product work.
- The GUI slice should consume the artifacts and conventions defined here; it should not become the backlog for every remaining product concern.

## Current Truth Snapshot

- Clean Tier 1 store is now the frozen structured baseline.
- Latest 400-query measured retrieval result:
  - `226/400 PASS`
  - `304/400 PASS+PARTIAL`
  - `298/400 routing correct`
- The latest landed but not yet cleanly re-measured retrieval change is the CAP/A027 path-hint follow-on patch.
- Live-demo suitability audit currently says:
  - `258/400 demo_safe`
  - `71/400 retrieval_only_safe`
  - `24/400 needs_tighter_reference`
  - `47/400 avoid_for_demo`
- No `AGGREGATE` query is currently cleared as `demo_safe`.
- Structured substrate is still thin:
  - extracted tables: `0`
  - relationships: `59`
- Dependency audit of the `400` pack says the dominant remaining unlocks are:
  - `121` aggregation/global queries
  - `37` retrieval metadata/path misses
  - `37` routing fixes
  - `26` rerank fixes
  - `15` tabular row-honesty upgrades
- Practical implication:
  - aggregation is the biggest remaining blocker, but it is **not** the next stage/demo lane
  - the biggest honest near-term score/demo gains are still router + rerank + typed metadata
- Typed-metadata sidecar clarification:
  - current Forge export is still only a minimal 7-key chunk contract
  - current V2 ingest would still drop richer metadata even if Forge emitted it
  - metadata work therefore has to be treated as a real cross-repo contract lane, not just a retrieval heuristic cleanup
- Practical read:
  - retrieval and routing are moving in the right direction
  - tabular and aggregation truth are not ready to be sold as solved
- Development-oracle clarification:
  - the outside-repo Claude hardtail runs are now strong enough to serve as the
    hard-tail development benchmark
  - the next question is no longer "does a stronger model help?"
  - it is:
    - which wins can be distilled back into Tier 1 / Tier 2
    - which cases justify a future hosted strong-model lane

## Product Rules

1. Keep the 400 benchmark frozen except for gold-reference tightening, labeling fixes, and separate demo or robustness packs.
2. Do not chase score by rewriting benchmark wording.
3. Treat aggregation and cross-role counting as a separate product track from ordinary retrieval.
4. Do not prioritize Tier 3 LLM extraction ahead of Tier 1 honesty, relationship wiring, and tabular substrate.
5. Prefer explicit typed metadata and filters over ever-growing path-string heuristics whenever the signal can be exported cleanly from Forge.
6. Domain-smart rules are allowed only if they are production-portable.
7. Workstation-scoped operational rules are allowed if they are intentional, documented, and reproducible on the target workstation.
8. Do not ship Beast-specific paths, dev-only artifact assumptions, or heuristics that cannot be reproduced by a clean production workstation run.

## Dependency Order

1. Make measurement and regression truth authoritative.
2. Burn down the remaining retrieval and router misses.
3. Freeze a real demo-safe query packet.
4. Fix the structured substrate that makes logistics and tabular answers trustworthy.
5. Add the aggregation path only after the substrate is honest.
6. Freeze the operator workflow, demo machine, and end-to-end handoff path.

## Master Slices

| Slice | Priority | Goal | Depends On | Status |
|---|---|---|---|---|
| PC.1 | P0 | Measurement, eval, and regression truth | none | START NOW |
| PC.2 | P0 | Retrieval and router hardening on the real miss families | PC.1 instrumentation | ACTIVE - LANE 1 FOLLOW-UP QA SIGNED |
| PC.2A | P1 | Development oracle bakeoff for Tier 3 hard-tail extraction/enrichment | PC.2 context + current extraction schema | ROUND 2 COMPLETE - RUN CODEX ON SAME PACK NEXT |
| PC.3 | P0 | Demo-safe query packet and gold-answer tightening | PC.1 current truth | READY |
| PC.4 | P0 | Structured extraction foundation and store honesty | PC.1 current truth | READY |
| PC.5 | P0 | Tabular substrate for logistics-grade row answers | PC.4 store honesty | READY |
| PC.6 | P1 | Aggregation and cross-role answer path | PC.4 + PC.5 | BLOCKED BY SUBSTRATE |
| PC.7 | P0 | Cross-repo metadata contract and Forge->V2 E2E proof | PC.1 + PC.2 | READY |
| PC.8 | P0 | Productization, GUI integration, preflight, and demo freeze | PC.1 + PC.3 + PC.7 | ACTIVE VIA SUB-SLICES |

## PC.1 - Measurement, Eval, And Regression Truth

**Why first:** the machine bug-out means the latest latency numbers are contaminated until rerun, and the eval harness must stay trusted before more tuning.

### Tasks

- Re-run the 400-query eval on stable hardware after the CAP/A027 retrieval patch.
- Capture stage-level timings separately for:
  - router
  - embedding
  - vector search
  - FTS search
  - fusion
  - rerank
  - total wall clock
- Keep one frozen naming convention for result artifacts so diffing stays mechanical.
- Use `scripts/compare_production_eval_results.py` as the standard delta report between retrieval slices.
- Split and freeze four distinct packs:
  - benchmark pack
  - demo-safe pack
  - robustness pack
  - aggregation/global pack
- Add a miss-family burn-down view so the `96` retrieval-broken rows are grouped by family, not treated as one blob.
- Confirm that candidate-pool and reranker changes are fully reflected by the harness and not undercounted.

### Exit Criteria

- Stable rerun captured after the latest retrieval patch.
- One-click or one-command comparison exists for before/after deltas.
- Latency numbers are trusted enough to drive optimization, not guessed through crash noise.

## PC.2 - Retrieval And Router Hardening

**Why second:** this is where the biggest honest win still is. The recent jump from `158` to `226` PASS says this lane is real.

### Tasks

- First burn-down order from the dependency audit:
  1. provider-agnostic router guards
  2. path-aware reranker
  3. typed metadata fields cross-repo
- Use the typed-metadata sidecar split explicitly:
  - V2-only stopgap backfill from existing `source_path`
  - then canonical Forge emit for the same fields
- Burn down the highest-yield residual miss families first:
  - CDRL deliverable retrieval
  - logistics and procurement
  - shipment and site/date retrieval
  - CAP and A027 incident/deliverable retrieval
  - installation and cross-tree locator queries
- Convert the current path-hint logic into explicit typed metadata where possible:
  - `cdrl_code`
  - `deliverable_family`
  - `site`
  - `shipment_date`
  - `shipment_mode`
  - `incident_id`
  - `po_number`
  - `vendor`
  - `doc_family`
- Mine the completed development-oracle runs for Tier 1 carry-back:
  - regex additions
  - normalization rules
  - exclusion rules
  - path-derived hints
  - row-shape heuristics
- Do not broad-retune global chunk size yet.
- If chunking is revisited, prefer:
  - a tiny hard-question A/B
  - or retrieval-time neighbor / section expansion
  over a full corpus re-chunk.

### Exit Criteria

- Clear family-by-family evidence for the major remaining miss buckets.
- Router behavior is intentional, explainable, and no longer a hidden latency tax on easy questions.
- Retrieval fixes are mostly metadata- and routing-driven, not ad hoc benchmark wording work.
- A Tier 1 distillation backlog exists from the dev-oracle wins.

## PC.2A - Development Oracle Bakeoff For Tier 3

**Why now:** this lane is now the fastest honest way to map hard-tail value, shrink the future hosted strong-model queue, and identify what can be pushed back down into Tier 1 / Tier 2.

### Round 1 Outcome

- Claude Max round 1 completed cleanly on `21` hard chunks across `7` families.
- Verdict split:
  - `14 better_than_local`
  - `4 same_as_local`
  - `3 mixed`
  - `0 worse_than_local`
- Totals:
  - local: `22 entities / 0 rels / 8 rows`
  - Claude: `200 / 56 / 149`
- Strongest gains:
  - procurement
  - CAP / IGSI
  - logistics
- Enrichment pilot also succeeded on `7/7` chunks.
- Current decision:
  - expand to a harder `50`-chunk stress pack
  - keep provider-specific run material outside the repo
  - add Codex on the same pack before building the provider-agnostic Tier 3 sidecar

### Round 2 Outcome

- Claude Max overnight master run completed outside the repo on the harder pack.
- Hardtail extraction headline:
  - `48 better_than_local`
  - `2 mixed`
  - `0 worse`
- Totals:
  - local: `28 entities / 0 relationships / 21 rows`
  - Claude: `554 / 162 / 275`
- By family:
  - procurement: `11/12`
  - logistics: `10/10`
  - CAP / IGSI: `10/10`
  - calibration / DD250: `6/6`
  - semi-table: `5/5`
  - OCR-damaged: `6/7`
- Enrichment:
  - `18/18` completed
  - grounding quality: `94%` date / `72%` team / `50%` site
- Regex mining:
  - `126` validation examples
  - `7` exclusion rules
  - `5` normalization families
- Operational note:
  - chunk `50` hit a Windows CreateProcess null-char crash
  - the lane resumed cleanly from raw progress without rebilling the prior `49` chunks
- Current decision:
  - use this as the new hardtail benchmark
  - run Codex on the same pack next
  - then design the provider-agnostic Tier 3 sidecar

### Round 2B Outcome

- Focused hardtail slice also completed outside the repo.
- Totals:
  - local: `154 entities / 0 relationships / 37 rows`
  - Claude: `613 / 219 / 185`
- Verdicts:
  - entities: `27 better / 23 mixed / 0 same / 0 worse`
  - relationships: `44 better / 6 both_empty / 0 worse`
- Important quality note:
  - prompt tightening eliminated the earlier generic-part hallucination mode
  - reported generic-part hallucinations: `0`
- Current decision:
  - relationship lift is the clearest stronger-model gain
  - freeze the fixed `50`-chunk pack as the cross-provider benchmark
  - run Codex on that same pack next
  - then build the provider-agnostic Tier 3 sidecar only if the same-pack compare stays strong

### Tasks

- Freeze the current `50`-chunk hardtail pack as the development benchmark.
- Run Codex on the exact same pack.
- Keep provider-specific outputs outside the repo.
- Preserve truthful provider provenance in every manifest and evidence note.
- Build a permanent `10`-chunk hardtail adjudication pack for repeated provider comparison.
  - seed it from `extraction_permanent_hardtail_candidates.json`
- Distill the strongest-model wins into Tier 1 / Tier 2 candidate fixes:
  - regex
  - normalization
  - exclusion rules
  - path-derived metadata
  - semi-table row heuristics
- Run a weaker/local-model compare on the permanent pack when useful:
  - `phi4:14b`
  - or another weaker development model
- Expand enrichment to a `25-50` chunk `phi4` A/B against the stronger-model enrichment outputs.
- Use the fixed-pack results to estimate the narrowest future hosted strong-model queue.

### Exit Criteria

- Claude and Codex have been compared on the same hardtail pack.
- A permanent hardtail adjudication pack exists.
- A Tier 1 distillation backlog exists from the dev-oracle wins.
- We know whether to:
  - stop at provider benchmarking
  - build the provider-agnostic Tier 3 sidecar
  - run a weaker/local-model proof pass
  - narrow the future hosted strong-model queue further

## PC.3 - Demo-Safe Query Packet And Gold Tightening

**Why now:** the benchmark is not the live demo. The product needs a narrow packet that is honest and reproducible.

### Tasks

- The dependency audit confirms that the live demo packet should continue excluding aggregation-heavy rows even if retrieval improves.
- The gold/rubric audit confirms that benchmark-only tightening is also needed:
  - `at least N` rows need clearer scoring boundaries
  - strong-retrieval PARTIAL rows need tighter chunk-level references
  - some PASS rows are still narration-unsafe for demo use
- Build the canonical live packet from the current `demo_safe` pool only.
- Keep `retrieval_only_safe` rows for rehearsal, screenshots, or supporting evidence only.
- Tighten the `24` `needs_tighter_reference` rows instead of broad question rewriting.
- Keep the `47` `avoid_for_demo` rows out of the live packet unless independently re-authored and re-verified.
- Produce a compact first-line demo deck:
  - 20-30 canonical queries
  - 10 rehearsal must-pass queries
  - 3 trust-boundary or fallback demonstrations
- Add a robustness mini-pack:
  - typo variants
  - acronym variants
  - shorthand variants
  - under-specified user wording
- Separate "benchmark success" from "stage-safe narration" explicitly in the docs and operator flow.
- Add a benchmark-only rubric cleanup sub-lane:
  - split or tighten scoring on `at least N` aggregation rows
  - distinguish folder-evidence gold from content-evidence gold where necessary
  - backfill stronger chunk-level references for strong-retrieval PARTIAL rows

### Exit Criteria

- One frozen, dated live-demo query packet.
- One frozen rehearsal packet.
- Known narration-unsafe PASS rows are excluded from the live packet.
- No pressure to use broad aggregation or weakly grounded questions on stage.

## PC.4 - Structured Extraction Foundation And Store Honesty

**Why before bigger claims:** this is the foundation for real structured answers, not just file retrieval.

### Tasks

- Keep `stage -> audit -> promote` as the only allowed path for structured-store changes.
- Fix the relationship-store runtime wiring so extraction and serving point at the same relationship DB.
- Keep the clean Tier 1 store as the audited baseline until a newer audited store replaces it.
- Run Tier 2 on the clean store with audit gates first for:
  - `PERSON`
  - `ORG`
  - `SITE`
- Finish workstation and install reproducibility for the Tier 2 path, including the offline GLiNER bundle if that is the chosen operator path.
- Add canary sentinels and blocked-namespace checks that run every time a new structured store is proposed.
- Decide what the acceptable "promotion gate" is for a new entity or relationship store:
  - counts
  - sentinel retention
  - blocked noise absence
  - query-family improvement

### Exit Criteria

- Structured serving and structured extraction use the same truthful stores.
- Tier 2 is promoted only through audited improvement, not hopeful volume.
- Entity-backed answers can be described honestly without hand-waving.

## PC.5 - Tabular Substrate For Logistics Answers

**Why this matters:** logistics and procurement users often need row-level answers, not just "I found the spreadsheet."

### Tasks

- Prioritize the logistics-first families identified by the sidecar before broad generic table work:
  - packing lists
  - received PO records
  - calibration trackers
  - BOMs
  - recommended spares
  - DD250s
- Choose the production table strategy for:
  - spreadsheets
  - BOMs
  - packing lists
  - received PO records
  - DD250s
  - calibration logs
  - spares reports
  - table-heavy PDFs
- Wire table extraction into the real pipeline so `extracted_table_rows` is no longer `0`.
- Define a table schema with provenance back to source file, sheet, row, and page where possible.
- Prioritize logistics-first table families before broader generic table work.
- Build a tabular eval slice from the existing question families so row extraction can be measured directly.
- Make row-level answer formatting citation-friendly and operator-readable.

### Exit Criteria

- At least the core logistics table families are extractable and queryable.
- The system can answer row-backed logistics questions without pretending a filename is the same thing as a row answer.

## PC.6 - Aggregation And Cross-Role Answer Path

**Why later:** aggregation is not just "more retrieval." It depends on clean structure.

### Tasks

- The dependency audit says `121` rows are aggregation-shaped, but only a subset should be treated as near-term honest unlocks.
- Freeze a narrow definition of safe aggregation:
  - only canary-backed or manually verifiable scoped counts
  - no broad enterprise counts without substrate proof
- Create a small validation pack for narrow real-scoped counts.
- Build a separate relationship / aggregation gauntlet:
  - `25-40` sharp questions, not another broad benchmark
  - mostly relationship-chain questions
  - explicit logistics reconciliation rows
  - PM-value cross-record status questions
  - negative / abstention checks
- Design the actual aggregation stack:
  - entity-backed where clean
  - table-backed where row truth exists
  - relationship-backed where predicates are real
  - GraphRAG or global summarization only where it solves a specific remaining gap
- Keep broad cross-role aggregation off-stage until it is independently green.
- Add source-grounded aggregation output requirements so the system shows what counted and why.
- Start with the aggregation families most likely to benefit from:
  - filed-deliverable normalization
  - received-PO indexing
  - shipment table backing
  - CAP / IGSI relationship chains
  - logistics ordered-vs-received reconciliation
  - PM-value deliverable / activity traceability

### Exit Criteria

- Aggregation is a truthful capability, not just a retrieval narrative.
- Demo inclusion is earned by validation, not by optimism.

## PC.7 - Cross-Repo Metadata Contract And End-To-End Flow

**Why cross-repo:** several of the next retrieval wins should be made explicit upstream in Forge, not only inferred downstream in V2.

### Tasks

- Audit which retrieval-critical fields should be exported by Forge rather than rediscovered in V2.
- Amend the planned Forge metadata schema so it explicitly names the thesis retrieval fields rather than leaving them implicit in V2 regex heuristics.
- Add or preserve explicit metadata fields needed for the typed-filter plan.
- Treat these as the highest-value contract fields:
  - `cdrl_code`
  - `incident_id`
  - `po_number`
  - `contract_number`
  - `site_token`
  - `site_full_name`
  - `shipment_date`
  - `shipment_mode`
  - `deliverable_family`
  - `doc_family`
  - `is_reference_did`
  - `is_filed_deliverable`
  - `source_ext`
  - `source_doc_hash`
- Close the current ingest gap so V2 does not silently drop richer metadata if Forge emits it.
- Keep the nightly delta, staging, canary, and full import flow artifact-backed and operator-visible.
- Run one fresh end-to-end proof:
  - Forge clean export
  - V2 staged import
  - structured-store validation
  - 400 benchmark rerun
  - demo-pack rerun
- Keep the export and import metadata contract documented and regression-tested.
- Freeze authoritative machine-specific paths and health checks so operators stop relying on stale counts and stale docs.

### Exit Criteria

- Forge and V2 agree on the metadata contract needed for the next retrieval step.
- There is one trustworthy end-to-end promotion path from export to demo machine.

## PC.8 - Productization, GUI Integration, Preflight, And Demo Freeze

**Why this stays explicit:** a good retrieval system can still fail on stage if the operator surface is stale or scattered.

### Tasks

- Keep the eval GUI slice as the active owner of the 400-query desktop experience.
- Feed the GUI the frozen result conventions, pack taxonomy, and comparison workflow from `PC.1` and `PC.3`.
- GUI operator-readiness sidecar says the GUI is not yet ready as the standardized repeated-run operator surface.
- Highest-value GUI readiness fixes before operator signoff:
  1. remove hardcoded docs-path assumptions
  2. persist and display run provenance
  3. add overwrite protection for manual output paths
  4. add a short operator quick-start
- Add or refresh operator preflight checks:
  - installer verification
  - store-count verification
  - GPU and process contention check
  - query-pack smoke run
  - demo freeze protocol
- Make the installer contract explicit:
  - repo-local runtime repair is in scope
  - external OCR binary install is currently out of scope unless a separate bootstrap lane is added
- Tighten OCR readiness semantics:
  - scanned-PDF OCR should only be green when both Tesseract and Poppler are executable
- Re-test latency on stable hardware after the machine-reset noise is gone.
- Freeze one canonical demo machine and one backup machine.
- Run the non-author GUI smash and the full rehearsal packet on the actual demo machine.
- Publish one current, single-source operator packet that supersedes older conflicting checklists.

### Exit Criteria

- Operators have one truthful checklist.
- The demo machine is frozen and reproducible.
- The GUI, runbooks, and query packets all point at the same source of truth.

## Immediate 4-Lane Split

### Lane A - Measurement And Eval Truth

- Own `PC.1`
- Own the frozen benchmark, demo, robustness, and aggregation pack taxonomy
- Own stable reruns and delta reports

### Lane B - Retrieval And Router Burn-Down

- Own `PC.2`
- Focus only on the remaining high-yield miss families
- Convert heuristics into metadata-first retrieval where possible

### Lane C - Structured, Tiered, And Tabular Foundation

- Own `PC.4` and `PC.5`
- Fix relationship-store truth
- Run audited Tier 2 promotion
- Stand up logistics-grade table extraction

### Lane D - Demo Productization And Cross-Repo Freeze

- Own `PC.3`, `PC.7`, and `PC.8`
- Respect the already-active GUI slice instead of rewriting it
- Own end-to-end proof, operator packet, demo machine freeze, and live packet rehearsal

## Not The Next Move

- Do not broadly rewrite the 400 benchmark for score gain.
- Do not start with chunk-size retuning; the current residuals are more retrieval-, relationship-, and structure-shaped than chunk-shaped.
- Do not present broad aggregation as solved before the tabular and relationship substrate is real.
- Do not expand Tier 3 into a corpus-wide expensive lane before Tier 1, Tier 2, and table extraction are honest.

## Completion Standard

The product is only "perfect" enough to claim success when all of the following are true:

- retrieval quality is measured and repeatable
- the demo packet is narrow, honest, and rehearsed
- logistics-grade tabular questions can be answered from real extracted rows
- structured stores are audited before promotion
- aggregation claims are scoped to what is actually validated
- the Forge->V2 handoff is repeatable
- the operator surface is simpler than the underlying system, not more confusing than it
