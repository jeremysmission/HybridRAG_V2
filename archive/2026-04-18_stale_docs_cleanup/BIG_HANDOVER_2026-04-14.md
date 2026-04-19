# Big Handover — 2026-04-14

## Purpose

This is the consolidated handover for the current HybridRAG_V2 / CorpusForge state after the overnight development-oracle runs.

Read this if you want one file that answers:

- what is done
- what is still risky
- what the overnight Claude runs proved
- what should happen next
- what should not be re-litigated
- where the real artifacts live

This file is push-safe. Provider-specific raw materials remain outside the repo.

## Canonical Repos

- `C:\HybridRAG_V2`
- `C:\CorpusForge`

## Local-Only Rule

Provider-specific development bakeoffs now belong in the:

- `local only hybridrag folder`
- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\`

Do not move provider-specific raw logs, manifests, scripts, or evidence notes back into the repo.

Repo policy from here:

- repo keeps pointers and curated summaries
- outside-repo folder keeps raw provider-specific materials
- sanitize only curated repo-visible material at pre-push time
- never run broad sanitizer apply against the local tree or the outside-repo bakeoff roots

## Mission

Near-term mission:

- recover operational value from a large legacy corpus
- let users ask real questions about forgotten historical records
- answer with grounded evidence when the answer exists
- answer clearly when the answer is not in the records

Phase-1 product truth:

- retrieval truth first
- structured truth second
- relationship-chain truth next
- broad aggregation only after substrate is honest

## Biggest Current Program Truths

- Broad diagnosis is no longer the blocker.
- The next high-value work is targeted:
  - relationship / aggregation truth
  - Tier 1 distillation
  - same-pack provider comparison
  - metadata / row-truth cleanup
- Strong AI is now the best diagnostic instrument for architecture gaps.
- Weaker/local AI is still the best proof of whether the architecture is carrying enough structure.

## Repo Status Snapshot

### Lane 1 — Retrieval / Router

- QA signed
- commit-ready
- still not automatically demo-freeze-safe
- latest signed follow-up:
  - `249 PASS`
  - retrieval `P50 6990ms -> 6085ms`
  - retrieval `P95 35109ms -> 25997ms`
- still slower than the post-CDRL baseline
- `PQ-103` still roughly `90s`
- cyber improved on some useful IDs, but demo suitability still needs judgment

### Lane 2 — Structured / Tabular

- QA PASS
- staged logistics follow-on is real
- staged table eval:
  - `8/8 PASS`
  - `9,133` table rows
- coordinator accepted the `tiered_extract.py` scope expansion as an explicit unfreeze
- before any clean commit:
  - evidence doc still needs the honesty fix

### Lane 3 — Installer / Preflight / Docs

- QA PASS
- Tesseract is installed and handled honestly
- Poppler / `pdftoppm` still missing or not configured on this workstation

### GUI

- launcher/interpreter blocker cleared
- saved-defaults behavior fixed
- output timestamp regeneration fixed
- remaining real gate:
  - non-author human smash

### Typed Metadata MVP

- landed in V2
- still needs:
  - true `--metadata-only` path without `vectors.npy`
  - later-chunk retrieval for typed hits
  - stale migration-doc cleanup
  - truthful boolean override semantics

### GLiNER / Skip-Signal

- torch-preserving 2-pass install pattern is correct in principle
- CPU/no-CUDA guard fix verified
- CRAG manual-skip logging fix verified
- still needs:
  - live retry-loop E2E
  - dirty-tree audit before push
  - keep unrelated sanitizer regression out of the lane

## Overnight Development-Oracle Results

These are development-only and not-for-push.

### Round 1 Claude Bakeoff

Location:

- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_01\`

Headline:

- `21` hard chunks across `7` families
- verdicts:
  - `14 better_than_local`
  - `4 same_as_local`
  - `3 mixed`
  - `0 worse_than_local`
- totals:
  - local: `22 entities / 0 rels / 8 rows`
  - Claude: `200 / 56 / 149`
- enrichment pilot:
  - `7/7` grounded preambles

### Overnight Master Run

Location:

- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\`

Headline:

- `48/50 better_than_local`
- `0 worse`
- `2 mixed`

Totals:

- local: `28 entities / 0 relationships / 21 rows`
- Claude: `554 / 162 / 275`

By family:

- procurement `11/12`
- logistics `10/10`
- CAP / IGSI `10/10`
- calibration / DD250 `6/6`
- semi-table `5/5`
- OCR-damaged `6/7`

Enrichment:

- `18/18` ok
- grounding:
  - `94%` date
  - `72%` team
  - `50%` site

Regex mining:

- `126` validation examples
- `7` exclusion rules
- `5` normalization families

Important operational note:

- chunk `50` hit a Windows CreateProcess null-char crash
- the lane resumed cleanly without rebilling the prior `49` chunks

### Focused Hardtail Slice 02

Location:

- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_02_hardtail\`

Headline:

- local: `154 entities / 0 relationships / 37 rows`
- Claude: `613 / 219 / 185`
- relationship verdicts:
  - `44 better`
  - `6 both_empty`
  - `0 worse`

Most important quality result:

- tightened prompting eliminated the earlier generic-part hallucination mode
- reported generic-part hallucinations: `0`

## What The Claude Runs Proved

- stronger-model proxy is very valuable on the hard tail
- relationship lift is the clearest stronger-model win
- stronger-model outputs can be mined for:
  - regex additions
  - normalization rules
  - exclusion rules
  - row-shape heuristics
  - path hints
  - schema gaps
- provider-specific development runs belong outside the repo
- this is strong enough to justify:
  - Codex on the same fixed pack
  - then provider-agnostic Tier 3 sidecar design

## What They Did Not Prove

- they did not prove broad aggregation is solved
- they did not prove the live product can answer arbitrary multi-hop questions yet
- they did not justify a corpus-wide expensive Tier 3 lane
- they did not justify fake `OSS-20B` provenance

## Most Important Next Moves

### 1. Codex Same-Pack Compare

Run Codex on the exact same fixed `50`-chunk hardtail pack.

Why:

- confirms whether the stronger-model signal is provider-specific
- strengthens the case for a provider-agnostic Tier 3 sidecar

### 2. Tier 1 Distillation

Use the stronger-model wins to produce a deterministic backlog:

- regex additions
- normalization families
- exclusion rules
- path-derived hints
- semi-table row heuristics

Why:

- this is the fastest way to shrink the future hosted strong-model queue

### 3. Relationship / Aggregation Gauntlet

Design a separate hard eval pack for:

- relationship-chain questions
- logistics ordered-vs-received reconciliation
- CAP / IGSI chains
- PM-value status / deliverable traceability
- negative / abstention checks

Why:

- this is now the biggest remaining product truth gap
- simple one-off retrieval is no longer the main unknown

### 4. `phi4` Proof Pass

Run:

- `phi4:14b` on the permanent hardtail pack
- `25-50` chunk enrichment A/B against the stronger-model enrichment outputs

Why:

- good architecture should let weaker/local models carry common relationship questions acceptably

## Permanent Cross-Provider Artifact

Adopt:

- `extraction_permanent_hardtail_candidates.json`

as the seed for the fixed `10`-chunk cross-provider adjudication pack.

## Chunking / Tier 1 Position

Current position:

- do **not** start with a late global chunk-size retune
- `1200 / 200` has already been accepted as sane on prior chunking review
- the current residuals look more:
  - retrieval-shaped
  - relationship-shaped
  - substrate-shaped
  than chunk-shaped

If chunking is revisited at all:

- prefer a tiny hard-question A/B
- or retrieval-time neighbor / section expansion
- not a full corpus re-chunk

## What Not To Waste Time On

- broad new research without a concrete question
- rewriting the 400 pack for score gain
- presenting aggregation as solved
- moving provider-specific dev materials back into repo docs/data
- broad sanitizer apply on the local working tree
- a large random batch when a stratified sample would teach more

## Best Morning Start

Open first:

1. `MORNING_CHECK_OUTSIDE_REPO_FIRST_2026-04-14.md`
2. `docs/LATEST_READABLE_NOTE_2026-04-13.md`
3. this file

Then inspect:

- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\00_meta\MORNING_REVIEW_INDEX_2026-04-14.md`
- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\04_final_summary\MORNING_HANDBACK_claude_master_2026-04-14.md`
- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_02_hardtail\CLAUDE_MAX_HARDTAIL_STRESS_TEST_EVIDENCE_2026-04-14.md`

## Final Summary

Current best read:

- retrieval is materially better than it was
- tabular substrate is now real enough to matter
- stronger-model hardtail extraction is decisively useful
- relationship extraction is the clearest lift
- the next real frontier is relationship-chain / aggregation truth
- the next best day should focus on:
  - Codex same-pack compare
  - Tier 1 distillation
  - aggregation gauntlet design

That is the most direct path toward the actual mission:

- answer hard historical questions from the legacy record
- with evidence
- and with honest abstention when the evidence is not there
