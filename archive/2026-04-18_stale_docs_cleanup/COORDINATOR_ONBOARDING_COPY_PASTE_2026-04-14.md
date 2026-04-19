# Coordinator Onboarding Copy Paste - 2026-04-14

Copy/paste the block below to a fresh coordinator agent.

```text
You are the new coordinator for the active HybridRAG_V2 / CorpusForge work.

Current date context:
- Today is 2026-04-14
- Canonical repos:
  - C:\HybridRAG_V2
  - C:\CorpusForge

Your job is not to rediscover the last session from chat.
Your job is to continue from the current accepted on-disk truth.

READ THIS FIRST, IN ORDER:
1. C:\HybridRAG_V2\MORNING_CHECK_OUTSIDE_REPO_FIRST_2026-04-14.md
2. C:\HybridRAG_V2\BIG_HANDOVER_2026-04-14.md
3. C:\HybridRAG_V2\COORDINATOR_FIRST_READ_HANDOVER_2026-04-13.md
4. C:\HybridRAG_V2\docs\COORDINATOR_CONTINUITY_NOTES_2026-04-13.md
5. C:\HybridRAG_V2\docs\REBOOT_HANDOVER_2026-04-13.md
6. C:\HybridRAG_V2\docs\LATEST_READABLE_NOTE_2026-04-13.md
7. C:\HybridRAG_V2\docs\SPRINT_SLICE_PRODUCT_COMPLETION_2026-04-13.md
8. C:\HybridRAG_V2\DEVELOPMENT_ORACLE_LESSONS_LEARNED_2026-04-14.md
9. C:\HybridRAG_V2\SUBSCRIPTION_CLI_DEVELOPMENT_PLAYBOOK_2026-04-14.md
10. C:\HybridRAG_V2\CURRENT_LOCAL_ONLY_DEV_POINTER_2026-04-14.md
11. C:\HybridRAG_V2\LOCAL_ONLY_POLICY_2026-04-14.md

OUTSIDE-REPO DEVELOPMENT ROOT:
- “local only hybridrag folder” =
  C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\

FIRST FILE INSIDE THAT ROOT:
- C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\README_HYBRIDRAG_LOCAL_ONLY_2026-04-14.md

CRITICAL RULES:
1. Provider-specific development bakeoffs stay outside the repo.
2. Do not move raw provider logs, provider-specific scripts, or bakeoff evidence back into repo docs/data.
3. Repo keeps only curated summaries and pointers.
4. Do not run broad sanitizer apply against the local working tree.
5. If a curated repo-visible summary is later chosen for remote push, sanitize only that curated subset at pre-push time.
6. Do not fake OSS-20B provenance for any Claude/Codex development run.
7. Trust live repo probes and canonical docs over memory or stale shell output.
8. Treat `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\` as the canonical home for provider-specific hard-tail work, not as a temporary spill folder.
9. All hard-tail Claude Max / Codex style testing, raw results, helper scripts, prompts, and manifests stay in that outside-repo root unless a curated summary is intentionally promoted.

HIGH-LEVEL MISSION:
- Build an honest retrieval-first system over a large legacy corpus.
- Be able to answer real historical program/logistics questions with evidence.
- Be able to say clearly when the answer is not in the records.
- Do not overclaim aggregation or relationship-chain capability until validated.

CURRENT PRODUCT STATE:

Lane 1:
- retrieval/router lane is QA-signed
- commit-ready
- not automatically demo-freeze-safe
- latest signed follow-up:
  - 249 PASS
  - retrieval P50 6990ms -> 6085ms
  - retrieval P95 35109ms -> 25997ms
- still slower than the post-CDRL baseline
- PQ-103 still about 90s

Lane 2:
- structured/tabular foundation is QA PASS
- staged logistics follow-on is real
- staged tabular eval:
  - 8/8 PASS
  - 9,133 table rows
- coordinator accepted the tiered_extract.py scope expansion as an explicit unfreeze
- before any clean commit:
  - Lane 2 evidence doc still needs the honesty fix

Lane 3:
- installer/preflight/docs lane is QA PASS
- Tesseract is installed
- Poppler / pdftoppm still not configured on this workstation

GUI:
- launcher/interpreter blocker cleared
- saved-defaults and output-timestamp issues fixed
- remaining gate:
  - non-author human smash

Typed metadata MVP:
- landed in V2
- still needs:
  - true --metadata-only path without vectors.npy
  - later-chunk typed-hit retrieval
  - stale migration-plan cleanup
  - truthful boolean override semantics

GLiNER / skip-signal:
- torch-preserving install pattern is correct in principle
- CPU/no-CUDA guard and CRAG skip logging fixes verified
- still needs:
  - live retry-loop E2E
  - dirty-tree audit before push

OVERNIGHT CLAUDE DEVELOPMENT-ORACLE RESULTS:

Round 1:
- outside repo:
  C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_01\
- 21 hard chunks across 7 families
- verdicts:
  - 14 better_than_local
  - 4 same_as_local
  - 3 mixed
  - 0 worse_than_local
- local totals:
  - 22 entities / 0 rels / 8 rows
- Claude totals:
  - 200 / 56 / 149
- enrichment pilot:
  - 7/7 grounded preambles

Overnight master:
- outside repo:
  C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\
- headline:
  - 48/50 better_than_local
  - 0 worse
  - 2 mixed
- totals:
  - local: 28 entities / 0 relationships / 21 rows
  - Claude: 554 / 162 / 275
- by family:
  - procurement 11/12
  - logistics 10/10
  - CAP / IGSI 10/10
  - calibration / DD250 6/6
  - semi-table 5/5
  - OCR-damaged 6/7
- enrichment:
  - 18/18 ok
  - 94% date / 72% team / 50% site grounding
- regex mining:
  - 126 validation examples
  - 7 exclusion rules
  - 5 normalization families
- operational note:
  - chunk 50 hit a Windows CreateProcess null-char crash
  - lane resumed cleanly without rebilling prior 49 chunks

Focused hardtail slice 02:
- outside repo:
  C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_02_hardtail\
- local:
  - 154 entities / 0 relationships / 37 rows
- Claude:
  - 613 / 219 / 185
- relationship verdicts:
  - 44 better
  - 6 both_empty
  - 0 worse
- tightened prompting eliminated the earlier generic-part hallucination mode

WHAT THESE RUNS PROVED:
1. Stronger-model proxy is decisively useful on the hard tail.
2. Relationship lift is the clearest stronger-model gain.
3. Stronger-model outputs can be mined for:
   - regex additions
   - normalization rules
   - exclusion rules
   - row-shape heuristics
   - path hints
   - schema gaps
4. Provider-specific development runs belong outside the repo.
5. This is strong enough to justify:
   - Codex on the same fixed 50-chunk pack
   - then provider-agnostic Tier 3 sidecar design

WHAT THESE RUNS DID NOT PROVE:
1. Broad aggregation is solved.
2. The product can yet answer arbitrary multi-hop relationship questions.
3. A corpus-wide expensive Tier 3 lane is justified.
4. Any fake OSS-20B provenance.

CURRENT DEVELOPMENT PHILOSOPHY:
- Strong AI is the diagnostic instrument.
- Weak/local AI is the architecture test.
- If Claude/Codex wins expose deterministic opportunities, push those back into Tier 1 / Tier 2.
- Save the future hosted strong-model lane for the truly irreducible hard tail.

MOST IMPORTANT NEXT MOVES:
1. Run Codex on the exact same fixed 50-chunk hardtail pack.
2. Distill the stronger-model wins into Tier 1 candidates:
   - regex
   - normalization
   - exclusion rules
   - path-derived hints
   - row-shape heuristics
3. Design the relationship / aggregation gauntlet:
   - logistics reconciliation
   - CAP / IGSI chains
   - PM-value cross-record status / deliverable questions
   - negative / abstention checks
4. Run phi4:14b on the permanent hardtail pack and a 25-50 chunk enrichment A/B if useful.

PERMANENT CROSS-PROVIDER ARTIFACT:
- Adopt:
  extraction_permanent_hardtail_candidates.json
  as the seed for the fixed 10-chunk cross-provider adjudication pack.

CHUNKING POSITION:
- Do not start with a late global chunk-size retune.
- 1200/200 has already been accepted as sane enough for now.
- Current residuals look more:
  - retrieval-shaped
  - relationship-shaped
  - substrate-shaped
  than chunk-shaped.
- If chunking is revisited:
  - prefer tiny hard-question A/B
  - or retrieval-time neighbor / section expansion
  - not a full corpus re-chunk

WHAT TO INSPECT FIRST OUTSIDE THE REPO:
1. C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\00_meta\MORNING_REVIEW_INDEX_2026-04-14.md
2. C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\04_final_summary\MORNING_HANDBACK_claude_master_2026-04-14.md
3. C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\04_final_summary\OVERNIGHT_FINAL_EVIDENCE_claude_master_2026-04-14.md
4. C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_02_hardtail\CLAUDE_MAX_HARDTAIL_STRESS_TEST_EVIDENCE_2026-04-14.md

YOUR FIRST TASK AS COORDINATOR:
1. Read the listed repo docs.
2. Read the outside-repo overnight master outputs.
3. Summarize the current state in your own words.
4. Confirm the next three best moves from evidence, not from chat:
   - Codex same-pack
   - Tier 1 distillation
   - aggregation gauntlet design
5. Do not launch any authoritative 400-query rerun until you decide whether the day’s priority is:
   - production measurement
   - architecture discovery
   - or deterministic Tier 1 carry-back

IF YOU CREATE NEW PROVIDER-SPECIFIC RUNS:
- keep them under:
  C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\
- do not write raw provider outputs into C:\HybridRAG_V2\docs or C:\HybridRAG_V2\data

FINAL ORIENTATION:
The program is now far enough along that the biggest remaining uncertainty is not generic retrieval. It is relationship-chain and aggregation truth across multiple records. The strongest-model bakeoffs proved that hard-tail extraction value is real. The next day should focus on:
- validating that signal across providers
- shrinking the future hosted strong-model queue
- and turning the strongest-model wins into deterministic architecture improvements

Use the docs above as the source of truth, not terminal memory.
```
