# COORDINATOR FIRST READ HANDOVER — 2026-04-13

## READ THIS FIRST

If the next coordinator reads only one file in the repo root, it should be
this one.

This file is the root-visible takeover brief for:

- what is done
- what is blocked
- what was learned today
- what should not be re-discovered
- what to run next
- how to use the development machine and workstations tomorrow

Then read:

1. `docs/COORDINATOR_CONTINUITY_NOTES_2026-04-13.md`
2. `docs/REBOOT_HANDOVER_2026-04-13.md`
3. `docs/SPRINT_SLICE_PRODUCT_COMPLETION_2026-04-13.md`
4. `MORNING_CHECK_OUTSIDE_REPO_FIRST_2026-04-14.md`
5. `DEVELOPMENT_ORACLE_LESSONS_LEARNED_2026-04-14.md`
6. `SUBSCRIPTION_CLI_DEVELOPMENT_PLAYBOOK_2026-04-14.md`
7. `CURRENT_LOCAL_ONLY_DEV_POINTER_2026-04-14.md`

## One-screen mission state

### Accepted current state

- Lane 2 structured/tabular foundation: **QA PASS**
- Lane 3 installer/preflight/docs: **QA PASS**
- Lane 1 retrieval/router: **commit-ready, not demo-build-ready**
- Lane 1 latency follow-up: **QA signed**
- GUI:
  - launcher/interpreter blocker cleared
  - saved-defaults workflow polish cleared
  - remaining signoff gap is non-author human smash
- V2-only typed metadata MVP: landed
- coordinator continuity/handover docs: materially improved
- CoPilot+/CoPilot+ extraction sidecar plan: written at repo root
- CoPilot+ overnight dev bakeoff slice: written at repo root
- Local-only folder convention: created and gitignored
- External stronger local-only path created:
  - `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\`
- Local Git pre-commit / pre-push hooks now block accidental bakeoff pushes

### Not yet done

- final Lane 1 demo-build decision after the latency follow-up rerun
- GUI non-author Tier D smash
- GLiNER QA cleanup
- true metadata-only CLI path
- typed-hit later-chunk retrieval
- authoritative Forge typed emit
- next authoritative production-workstation run
- CoPilot+ run on the fixed `50`-chunk hardtail pack
- Tier 1 distillation from the development-oracle runs
- relationship / aggregation gauntlet design

### Biggest program truth

The project is no longer blocked on broad diagnosis. It is now blocked on a
small number of concrete implementation and validation steps.

## First 10 minutes for the next coordinator

1. Read this file fully.
2. Read the continuity note and reboot handover.
3. Treat these as current truths:
   - production query model is `gpt-4o`
   - `phi4` is local/offline/fallback only
   - Lane 1 is not demo-freeze-safe yet
   - GUI is close, but not fully operator-complete yet
   - typed metadata MVP is useful, but not finished
4. Do **not** spend the next authoritative production-workstation run yet.
5. Do **not** restart broad research unless a new hard question appears.
6. Prioritize the next slices in the order listed below.

## What not to waste time re-discovering

- Aggregation is mostly normalization/index/substrate work before graph work.
- Logistics is a row-truth problem more than a semantic-retrieval problem.
- Typed metadata is the biggest honest retrieval lever still available.
- OCR is not the top blocker before May 2, but it can still unlock real value.
- Gold/rubric weakness is real, but it is not the main product blocker.
- Sanitization is a remote-evidence rule, not a blanket local-dev language rule.
- Workstation-specific behavior is allowed if reproducible on the target
  workstation.
- Development-machine residue is not acceptable in pushed evidence.

## What was accomplished today

### Verified / landed

- Lane 2 structured + tabular foundation is QA PASS.
- Lane 2 logistics table follow-on produced a staged `8/8` tabular PASS:
  - real staged store
  - `9,133` table rows
  - `_pipekv_` extractor proved by `T-07` writing `500` rows
- Lane 3 installer / preflight / docs lane is QA PASS.
- Lane 1 retrieval + router burn-down is now separated correctly into:
  - commit-ready
  - not yet demo-build-ready
- Lane 1 latency-gate follow-up landed on GPU 1 and is now the current lane state:
  - `249 PASS` held
  - retrieval `P50 6990ms -> 6085ms`
  - retrieval `P95 35109ms -> 25997ms`
  - still slower than the post-CDRL pre-Lane-1 baseline
  - QA signed
  - still not clearly demo-safe
- GUI operator surface improved materially:
  - launcher/interpreter blocker is cleared
  - provenance and overwrite protection are in place
  - quickstart exists
  - saved defaults now regenerate fresh timestamped outputs on relaunch
  - latest GUI QA round is clean on `028af15`
- V2-only typed metadata MVP landed:
  - `cdrl_code`
  - `incident_id`
  - `po_number`
  - `contract_number`
  - `site_token`
  - `site_full_name`
  - `is_reference_did`
  - `is_filed_deliverable`
  - `source_ext`
  - optional `shipment_mode`
  - passthrough `source_doc_hash`
- Coordinator continuity / reboot docs were brought much closer to reality.
- CorpusForge now has a plain-English doc for nonprogrammers:
  - `docs/FORGE_IN_PLAIN_ENGLISH.md`
- Another retiring reviewer/QA agent ended around `6/10` freshness:
  - still sharp on:
    - Lane 3 QA
    - CorpusForge light doc pass
    - Lane 1 QA
    - Lane 2 QA
    - sanitizer-scope rules
    - domain-vocabulary protection
  - fuzzier on:
    - exact older line numbers / hunk boundaries
    - full ownership map across all dirty-tree files without a fresh repo probe

### What was clarified

- The main pre-demo bottleneck is still metadata + routing + row truth, not
  model cleverness.
- Aggregation is still mostly:
  - normalization
  - filed-deliverable indexing
  - narrow validated counts
  - logistics row substrate
  - only then true graph/global work
- Production query model should be `gpt-4o`.
- `phi4` is for local upkeep, fallback, and non-authoritative work.
- Sanitization is a remote-evidence / push-safety rule, not a blanket local-dev
  language rule.
- Using paid `gpt-4o` now as a development extraction oracle is allowed and
  useful.
- CoPilot+ Max and CoPilot+ are viable as development-oracle and hard-tail sidecars,
  but not as the primary unattended corpus-scale extraction backend.
- Strong AI is now the best tool for decoding architecture gaps; weaker/local
  models remain the best proof of whether the architecture is actually carrying
  enough structure.

### CoPilot+ Max / CoPilot+ sidecar plan

- Stronger external local-only path now exists and is now the primary home for provider-specific bakeoffs:
  - `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\`
- Current CoPilot+ bakeoff root:
  - `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_01\`
- Current master overnight root:
  - `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\`
- Repo pointer doc:
  - `CURRENT_LOCAL_ONLY_DEV_POINTER_2026-04-14.md`
- Local-only policy doc:
  - `LOCAL_ONLY_POLICY_2026-04-14.md`
- Coordinator rule:
  - yes for development oracle work
  - yes for bounded hard-tail sidecar work
  - no for unattended full-corpus extraction
  - no for fake OSS-20B provenance
- Round 1 result is now real:
  - `21` hard chunks across `7` families
  - `14 better_than_local`
  - `4 same_as_local`
  - `3 mixed`
  - `0 worse_than_local`
  - local: `22 entities / 0 rels / 8 rows`
  - CoPilot+: `200 / 56 / 149`
  - enrichment pilot: `7/7` grounded preambles
- Best next step from that plan:
  - use the completed `50`-chunk hardtail result as the new reference point
  - run CoPilot+ on the same pack next
  - then decide whether to build the provider-agnostic Tier 3 sidecar

### CoPilot+ Max overnight master result

- The overnight master run is complete outside the repo:
  - `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\`
- Hardtail extraction headline:
  - `48 better_than_local`
  - `2 mixed`
  - `0 worse`
- Totals:
  - local: `28 entities / 0 relationships / 21 rows`
  - CoPilot+: `554 / 162 / 275`
- By family:
  - procurement: `11/12`
  - logistics: `10/10`
  - CAP / IGSI: `10/10`
  - calibration / DD250: `6/6`
  - semi-table: `5/5`
  - OCR-damaged: `6/7`
- Enrichment:
  - `18/18` completed
  - grounding hit rates: `94%` date, `72%` team, `50%` site
- Regex mining:
  - `126` validation examples
  - `7` exclusion rules
  - `5` normalization families
- Operational note:
  - chunk `50` hit a Windows CreateProcess null-char crash
  - the lane patched sanitization + resume-from-raw, so the prior `49` chunks were not re-billed
- Coordinator read:
  - this is a decisive development result
  - next move should be CoPilot+ on the same hardtail pack
  - then sidecar design, not more speculation

### CoPilot+ Max focused hardtail slice 02

- The focused hardtail follow-up also completed outside the repo:
  - `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_02_hardtail\`
- Extraction totals:
  - local: `154 entities / 0 relationships / 37 rows`
  - CoPilot+: `613 / 219 / 185`
- Verdicts:
  - entities: `27 better / 23 mixed / 0 same / 0 worse`
  - relationships: `44 better / 6 both_empty / 0 worse`
- Important quality note:
  - tightened prompting eliminated the earlier generic-part hallucination mode
  - reported generic-part hallucinations: `0`
- Coordinator read:
  - relationship lift is now clearly the strongest stronger-model gain
  - the next truth test should be:
    - CoPilot+ on the same fixed pack
    - then a small relationship/aggregation gauntlet

## Current hard truths

### Lane 1

- Lane 1 improved score, but has a real demo tradeoff:
  - baseline: `226 PASS`, `298 routing-correct`
  - Lane 1 run: `249 PASS`, `301 routing-correct`
- Lane 1 latency follow-up improved the worst regression without improving the headline PASS count:
  - follow-up run: `249 PASS`, `300 routing-correct`
  - retrieval `P50 6990ms -> 6085ms`
  - retrieval `P95 35109ms -> 25997ms`
  - versus the post-CDRL baseline, it is still slower:
    - `P50 3695ms -> 6085ms`
    - `P95 16233ms -> 25997ms`
- Lane 1 is still not clearly demo-build-safe because:
  - cyber remains mixed even after the follow-up
  - `PQ-103` still blew out to about `90s`
  - cybersecurity regressed on 9 verified PASS rows:
    - `PQ-196`
    - `PQ-200`
    - `PQ-201`
    - `PQ-262`
    - `PQ-385`
    - `PQ-419`
    - `PQ-475`
    - `PQ-476`
    - `PQ-479`
- cyber/demo-relevant improvements from the follow-up:
  - `PQ-200`: `PARTIAL -> PASS`
  - `PQ-255`: `MISS -> PASS`
  - `PQ-385`: `PARTIAL -> PASS`
  - `PQ-419`: `MISS -> PARTIAL`
- current decision:
  - Lane 1 latency follow-up is QA signed
  - keep Lane 1 commit-ready
  - keep Lane 1 out of demo freeze until rehearsal accepts the remaining tradeoffs:
    - `PQ-103` ~`90s` outlier
    - cyber still mixed vs pre-Lane-1 baseline
    - overall latency still slower than the post-CDRL baseline

### Lane 2

- Lane 2 follow-on is technically good and substantively useful:
  - staged store tabular eval passed `8/8`
  - clean-baseline write guard held
  - no GUI or benchmark-pack contamination
  - lane reviewer wrap-up note:
    - self-rated `8/10` on context freshness
    - strong on recent QA lanes, Eval GUI arc, and V2/Forge changes
    - main drag is concurrent unrelated work in both trees, which makes ownership and push-safety harder to reason about without re-auditing files
- Coordinator adjudication:
  - accept the `scripts/tiered_extract.py` scope expansion as an explicit unfreeze for the logistics table pilot
  - reason: new CLI args default off, behavior is gated, tests are green, and the staged eval proved real value
- Remaining required cleanup before a clean commit/push:
  - correct the evidence doc contradiction about "new flags were not added"
  - keep the sanitizer regression as a separate lane, not bundled into the Lane 2 follow-on commit

### GUI

- The launcher/interpreter issue is cleared.
- The saved-defaults regression is cleared on `028af15`.
- Latest GUI coder summary:
  - slice is `7` local commits
  - no outstanding code findings remain
  - nothing in the GUI lane is pushed yet
  - coder self-rating at wrap-up: `6/10` context freshness, still coherent on GUI/retrieval but long-session fatigue is real
  - exact GUI local commit stack called out by the coder:
    - `6cab1ac` skeleton + 4 panels + installer/launcher
    - `e1fa599` compare-panel negative-delta sign
    - `d728076` proxy hardening
    - `2301802` operator readiness (portability, provenance, overwrite, quickstart)
    - `5fda76a` canonical `-m` module entry point
    - `9e67ebc` operator-saved defaults + per-field walkthrough
    - `028af15` fresh output timestamps on every launch
- Current GUI truth:
  - saved defaults restore operator input choices
  - report and JSON output targets regenerate fresh timestamps on relaunch
  - legacy defaults files are tolerated safely
- Remaining GUI gate:
  - non-author human smash only

### Typed metadata MVP

- The V2-only MVP is useful and real.
- Two follow-up fixes are still needed:
  1. `--metadata-only` should not require loading `vectors.npy`
  2. typed hits should not force a head-chunk-only representative when the
     answer is in a later chunk of the right file
- Additional metadata implementation/doc mismatches now confirmed:
  3. the current migration-plan doc is stale relative to the landed V2-only sidecar-DB implementation
  4. re-import into an existing Lance store can be a silent no-op for new metadata columns because existing `chunk_id`s are skipped
  5. boolean fallback merge is weaker than documented:
     - authoritative `False` values do not truly override path-derived `True`
     - current merge logic can resolve both `is_filed_deliverable` and `is_reference_did` to `True`
- Coordinator rule:
  - treat `docs/METADATA_MIGRATION_IMPLEMENTATION_2026-04-13.md` plus live code as current
  - treat `docs/FORGE_TO_V2_TYPED_METADATA_MIGRATION_PLAN_2026-04-13.md` as historical strategy until refreshed
  - do **not** assume “one fresh re-import” is enough unless it is into a clean/new store path or an explicit update migration exists
- Metadata evidence-artifact caution:
  - some older metadata-path evidence docs now read as sanitized summaries rather than literal raw probe/eval transcripts
  - use them as push-safe summaries, not byte-for-byte audit artifacts

### GLiNER offline install / skip-signal follow-up

- The torch-overwrite fix is real:
  - offline bundle build is now two-pass
  - offline install is now two-pass
  - `gliner` installs with `--no-deps`
  - builder refuses to publish a bundle containing `torch-*.whl`
- Two follow-up fixes were later verified:
  - `benchmark_gliner.py` now exits cleanly on CPU/no-CUDA boxes before CUDA-only probes
  - CRAG manual skip now logs as operator skip instead of fake retry exhaustion
- But the lane is **not fully QA-clean yet**.
- Agent self-rating at wrap-up: `6/10`
  - still coherent on the GLiNER offline / skip-signal arc
  - good for QA punch-list and focused follow-up
  - not ideal for starting a brand-new subsystem without a fresh primer
- Current GLiNER / skip-signal QA findings:
  1. `entity_extractor.py` working tree currently shows an unrelated regex regression that would break original `IGSI-...` / `IGSCC-...` Tier 1 matching
     - important nuance: `HEAD` is correct; the bad regex is from concurrent uncommitted work, not the GLiNER fix itself
  2. live terminal keypress E2E on a real retry loop is still missing
  3. current dirty-tree state is much broader than this lane and must be audited before any push
- Coordinator rule:
  - treat the offline install pattern as basically correct
  - do **not** call the GLiNER lane fully signed off until:
    - the concurrent `IGSI` / `IGSCC` regex regression is resolved or fenced
    - a live retry-loop keypress E2E is run
    - the broader dirty tree is audited before any push

### Promotion / production-workstation run

- Do **not** spend the next authoritative production-workstation run yet.
- Biggest hidden promotion risk remains:
  - accepted clean Tier 1 baseline vs active default store ambiguity
- Other blockers:
  - wrong default query-pack foot-gun in `run_production_eval.py` if
    `--queries` is omitted
  - demo-safe pack not yet materialized as a single frozen file
  - metadata-contract decision must be explicit before the next fresh export

## Lessons learned today

### Product / architecture

- Typed metadata is the biggest honest retrieval lever still available before
  May 2.
- Logistics is a row-substrate problem more than a retriever problem.
- OCR is not the top bottleneck before May 2, but it is still a real source of
  missed value, especially for scanned PDFs and logistics/acceptance families.
- Gold/rubric weakness is real, but it should not distract from the product
  work. The split still looks roughly like:
  - `~70%` real product weakness
  - `~15-20%` gold/rubric weakness
  - `~10-15%` ambiguity

### Operating discipline

- A clean commit and truthful provenance matter as much as a better score.
- Workstation-specific tuning is fine if reproducible on the target machine.
- Local-only development artifacts may contain development-specific language if
  they are clearly not for push.

### Model strategy

- `gpt-4o` is worth using now as a development oracle for hard extraction cases.
- That is the clean way to estimate whether `gpt-oss-20b` / `gpt-oss-120b`
  will be sufficient later on AWS-hosted extraction.

## What can be pushed vs what should stay local

### Push-safe now

- Current continuity / handover docs
- QA reports and evidence docs that are already written in push-safe language
- quickstarts and operator guides that are workstation-neutral
- root-visible planning / handover docs like this one

### Keep local until fixed or intentionally reviewed

- Lane 1 code as demo-build candidate until latency/cyber follow-up lands
- metadata MVP until the two follow-up defects are fixed
- any local-only development extraction bakeoff outputs using raw development
  machine provenance
- any sanitizer-overreach candidates that would mutate domain-smart code or
  tests incorrectly

### Push rule

- Prefer scoped commits.
- Do **not** do a blind repo-wide sanitize-apply in the current mixed dirty
  tree.
- Sanitize remote-bound docs and artifacts where possible, but do not let the
  sanitizer corrupt domain-smart logic or tests.
- Audit concurrent working-tree changes carefully before any push:
  - the GLiNER QA follow-up saw much broader dirty-tree churn than one lane
  - some JSON/evidence files show very large deletions from other sessions
  - the `IGSI` / `IGSCC` regex regression was confirmed to be a concurrent working-tree issue, not a safe blind revert
- Keep the Lane 2 table-pilot commit separate from the sanitizer-cleanup lane.

## Development use of `gpt-4o`

### Recommended development experiment

Run a small bakeoff on `50-100` hard chunks:

- logistics tables
- procurement rows
- CAP / IGSI incident documents
- A027 subtype documents
- OCR-damaged or semi-structured chunks

For each chunk:

1. run `gpt-4o` extraction as the reference
2. run the current local extraction path
3. compare field-by-field
4. identify what must be AWS-hosted later and what local OSS can probably carry

### Why this matters

- It gives us a realistic extraction ceiling.
- It will show whether `gpt-oss-20b` is enough for the harder fields.
- It lets us design schema from evidence instead of guesswork.

## OCR value note

Yes, missing OCR likely means there is still real value not yet captured.

Most likely affected:

- scanned PDFs
- DD250s
- scanned logistics/support documents
- image-heavy acceptance / install artifacts

Important caveat:

- if OCR changes the extracted text, then yes:
  - documents must be re-parsed
  - chunks must be regenerated
  - vectors must be regenerated
  - a fresh export + V2 import is required

So OCR is not just a metadata patch. It is a true corpus regeneration step for
the affected families.

## Canonical current blockers

### Lane 1 blockers

- tail-fallback / metadata-path latency
- cyber regression slice
- final demo-pack safety check

### GUI blockers

- non-author Tier D human smash still needed

### Metadata blockers

- `--metadata-only` still loads `vectors.npy`
- typed-hit retrieval still prefers one representative head chunk per file

### GLiNER blockers

- resolve the concurrent working-tree `IGSI` / `IGSCC` regex regression
- run one live terminal keypress E2E against a real retry loop
- audit dirty-tree contamination before any push

### Promotion blockers

- clean-store vs default-store ambiguity
- wrong default query-pack foot-gun
- demo-safe pack still not a single frozen file
- metadata-contract decision still needs to be explicit
- mixed dirty-tree state still makes blind promotion unsafe

## Next 5 slices in best chronological order

The rule on the development machine should be at least 2 active lanes at all
times, and often 3. Prefer:

- GPU 1 for the heaviest eval/extraction lane
- GPU 0 for the lighter or secondary lane
- CPU/doc lane in parallel whenever possible

### Slice 1 — Immediate stabilization

**Goal:** make the current system more honest and more demo-safe before doing
any fresh authoritative run.

Lane A — Retrieval
- cap/gate Lane 1 metadata-path tail fallback
- re-run the 400
- inspect cyber regressions

Lane B — GUI
- complete non-author human smash

Lane C — Metadata MVP
- fix true `--metadata-only`
- fix typed-hit later-chunk retrieval

Lane D — Lane 2 cleanup
- correct the Lane 2 evidence doc honesty issue around new CLI flags
- isolate the follow-on commit from unrelated sanitizer damage

**Definition of done for Slice 1**

- Lane 1 latency reduced materially from the current regression
- cyber regressions are understood or fenced off from the demo pack
- GUI saved-defaults workflow is truthful
- metadata MVP behaves the way the docs claim it behaves

### Slice 2 — Workstation truth capture

**Goal:** convert overnight workstation work into verified evidence.

Lane A — Desktop workstation
- inspect overnight clean Tier 1 and Tier 2 outputs
- run audits and count checks
- verify relationships, entities, tables, and any new evidence docs

Lane B — Laptop workstation
- verify repo sync / install / GUI / quickstart usability
- set up as the secondary operator/review machine

Lane C — Local dev
- prepare exact commands and frozen inputs for the next production-model proof
  run

**Definition of done for Slice 2**

- desktop workstation outputs are audited and recorded
- laptop is ready for secondary operator work
- the next production-model proof run can be launched without guesswork
- Lane 2 staged follow-on evidence is either committed cleanly or explicitly held for one narrow review cycle

### Slice 3 — Hard extraction bakeoff

**Goal:** convert the new development-oracle lab into a sharper hard-tail plan
and a smaller future OSS queue.

Lane A — CoPilot+ same-pack compare
- run CoPilot+ on the exact same `50`-chunk hardtail pack
- preserve provider provenance and keep outputs outside the repo

Lane B — Tier 1 distillation
- mine the CoPilot+ wins for:
  - regex additions
  - normalization rules
  - exclusion rules
  - path-derived hints
  - row-shape heuristics

Lane C — weaker-model proof
- run `phi4:14b` or another weaker local model on the permanent hardtail pack
- use that to test whether the architecture is carrying enough structure

Lane D — evaluation / schema
- define the permanent `10`-chunk hardtail adjudication pack
- decide which families/fields actually need future `gpt-oss-20b` /
  `gpt-oss-120b`

**Definition of done for Slice 3**

- CoPilot+ and CoPilot+ have been compared on the same hardtail pack
- a permanent hardtail adjudication pack exists
- Tier 1 distillation candidates are written down
- we know which families/fields justify AWS-hosted extraction later

### Slice 4 — Forge + OCR leverage

**Goal:** increase durable corpus value, not just retrieval cleverness.

Lane A — Forge typed metadata emit
- move the MVP fields upstream into Forge emit

Lane B — OCR enablement
- install/verify Poppler where needed
- validate Tesseract and scanned-PDF readiness
- choose a limited OCR rerun family if time is tight

Lane C — Logistics follow-on
- keep pushing row-truth on received POs, packing lists, calibration, spares,
  and DD250s

**Definition of done for Slice 4**

- typed fields move upstream into Forge or are explicitly deferred
- OCR decision is no longer hand-wavy
- logistics row truth continues to improve in honest, narrow slices

### Slice 5 — Promotion preparation

**Goal:** spend the next authoritative workstation run only when it is worth
spending.

Lane A — promotion hygiene
- fix query-pack default foot-gun
- resolve clean-store vs default-store ambiguity
- freeze demo-safe pack as a real file

Lane B — rehearsal
- run 5-query `gpt-4o` production proof
- then run full 400 only if the proof is clean

Lane C — documentation / package
- finalize runbook
- package artifacts under one promotion run directory
- capture operator signoff

**Definition of done for Slice 5**

- the next authoritative workstation run is worth spending
- promotion evidence is trustworthy
- the run can be explained and defended later

## Tomorrow at work — workstation desktop

### First things to do

1. Inspect the overnight clean Tier 1 and Tier 2 outputs.
2. Record:
   - entity count
   - relationship count
   - extracted-table count
   - audit verdicts
3. Check whether the outputs match expectations from the current canonical docs.

### Then do

1. Open `MORNING_CHECK_OUTSIDE_REPO_FIRST_2026-04-14.md`.
2. Read the outside-repo overnight master outputs first.
3. Decide whether the next dev lane is:
   - CoPilot+ on the same hardtail pack
   - Tier 1 distillation from the CoPilot+ wins
   - aggregation gauntlet design
4. Only after that, verify `gpt-4o` path is usable:
   - keyring present
   - provider reachable
   - no auth/proxy surprise
5. Run a small `5`-query production-model smoke with explicit config.
6. Only if that is clean, decide whether to spend a full `400`.

### Desktop reminders

- prefer explicit `--queries`
- prefer explicit `--config`
- capture output paths deliberately
- do not let the old 25-pack default sneak in
- if you use GUI, focus on the non-author smash pass rather than launcher/defaults debugging
- do not move provider-specific bakeoff material back into the repo
- do not broad-retune chunk size before Tier 1 distillation and aggregation
  gauntlet work

## Tomorrow at work — workstation laptop

Use the laptop as:

- the secondary operator machine
- GUI validation machine
- doc/review station
- fallback local test surface

### Laptop checklist

1. Pull / sync only the push-safe packet.
2. Verify `.venv`.
3. Verify GUI launch + quickstart clarity.
4. Verify Tesseract / Poppler state.
5. If GPU is limited, use laptop more for QA/docs/GUI than heavy extraction.

## Exact checks to run tomorrow

### Desktop workstation

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\health_check.py
.venv\Scripts\python.exe scripts\validate_setup.py
```

Then inspect clean outputs and audits before deciding on any full eval.

### OCR checks

```powershell
where.exe tesseract
where.exe pdftoppm
echo $env:TESSERACT_CMD
echo $env:HYBRIDRAG_POPPLER_BIN
```

### Production-model smoke

Use explicit config and explicit query pack. Do not rely on defaults.

## GLiNER install tips

### Important rule

Do **not** let an offline GLiNER install overwrite the tuned workstation torch.

### Safe pattern

1. Install support deps first.
2. Install `gliner` with `--no-deps`.

That prevents a bundled `torch` wheel from replacing the existing CUDA-tuned
install.

### After install, verify

- `python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"`
- `python -c "import gliner; print('ok')"`

### Practical reminder

- Desktop heavy extraction can prefer the stronger GPU lane.
- Keep GLiNER device/config explicit in config and notes.

## Tesseract / Poppler checks

### Fast checks

```powershell
where.exe tesseract
where.exe pdftoppm
echo $env:TESSERACT_CMD
echo $env:HYBRIDRAG_POPPLER_BIN
```

### Real checks

```powershell
& "$env:TESSERACT_CMD" --version
pdftoppm -h
```

### Better check

Run the workstation precheck, because it captures the actual run-shape truth.

## Concrete traps to avoid

- Do not trust old docs just because they grep first.
- Do not omit `--queries` on `run_production_eval.py`.
- Do not assume GUI is fully operator-ready until the non-author smash pass is done.
- Do not treat a better PASS count as enough if latency or cyber regress badly.
- Do not run blind sanitize-apply across the whole dirty tree.
- Do not let development extraction evidence get mistaken for production
  evidence.

## Concrete reminders moving forward

- Do not confuse commit-ready with demo-ready.
- Do not spend the next authoritative production-workstation run yet.
- Keep `gpt-4o` as the production query path.
- Use `gpt-4o` development extraction only as labeled dev evaluation, not as
  fake production evidence.
- Keep pushing toward:
  - typed metadata
  - row truth
  - honest routing
  - reproducible workstation runs

## Where the next coordinator should leave notes

If new results land tomorrow, update these first:

1. `docs/COORDINATOR_CONTINUITY_NOTES_2026-04-13.md`
2. `docs/REBOOT_HANDOVER_2026-04-13.md`
3. this root file

That keeps the recovery path short and truthful.

## Most important linked docs

- `docs/COORDINATOR_CONTINUITY_NOTES_2026-04-13.md`
- `docs/REBOOT_HANDOVER_2026-04-13.md`
- `docs/SPRINT_SLICE_PRODUCT_COMPLETION_2026-04-13.md`
- `docs/PRODUCTION_WORKSTATION_PROMOTION_AUDIT_2026-04-13.md`
- `docs/FORGE_TO_V2_TYPED_METADATA_MIGRATION_PLAN_2026-04-13.md`
- `docs/LANE1_QA_REPORT_2026-04-13.md`
- `docs/GUI_OPERATOR_READINESS_AUDIT_2026-04-13.md`
- `docs/METADATA_MIGRATION_IMPLEMENTATION_2026-04-13.md`
- `docs/LATEST_READABLE_NOTE_2026-04-13.md`
