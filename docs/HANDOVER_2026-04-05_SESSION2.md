# Session Handover — 2026-04-05 Evening

**From:** Session 2 (marathon session, ~8 hours)
**To:** Session 3
**Priority:** Complete Sprint 5 QA + Sprint 6 coding

---

## What's Running Right Now

- **GPU 0:** `start_overnight_extraction.bat` — phi4 extracting entities from Clone1 chunks into V2 SQLite. ~2.6 chunks/min. Check progress: `cd C:\HybridRAG_V2 && .venv\Scripts\python.exe scripts\overnight_extraction.py --status`
- **GPU 1:** Available

---

## What Got Done This Session

### Code (both repos pushed and clean)

**CorpusForge (C:\CorpusForge) @ ed6eb80:**
- Pipeline rewritten with 8-worker ThreadPoolExecutor (ported from V1)
- GUI progress callback wired (update_current_file)
- CRLF bat files fixed
- Setup script: `tools/setup_beast_2026-04-05.bat` (14 steps, verified PASS)
- Verification scripts: verify_cuda_embedding.py, verify_parallel_pipeline.py, benchmark_pipeline.py
- requirements.txt: einops added, numpy<2.0, install order docs
- Venv created and verified: 26 PASS, 0 FAIL

**HybridRAG V2 (C:\HybridRAG_V2) @ 476eb6c:**
- Setup script: `tools/setup_beast_2026-04-05.bat` (18 steps, verified PASS)
- A/B extraction test: `scripts/ab_extraction_test.py` (phi4 tested: 9/10 success, 48 entities, 2.6 chunks/min)
- Overnight extraction: `scripts/overnight_extraction.py` + `start_overnight_extraction.bat`
- import_embedengine.py hardened: batch inserts (1000/batch), mmap large vectors, --source required
- lance_store.py: batched ingest, efficient dedup scanner, progress logging
- extract_entities.py: Ollama auto-detection for phi4
- LLM client fix: Ollama no longer blocked by missing API key
- requirements.txt: sentence-transformers 5.3.0, numpy<2.0, pyarrow pin, flashrank 0.2.9
- GPU isolation: GPU 0 = CorpusForge, GPU 1 = V2 (temp set, hardcode 0)

### Docs Written
- SPRINT_PLAN_REVISED_2026-04-05.md — 5 parallel tracks (A-E), 31+ slices
- SPRINT_6_GAMEPLAN_2026-04-05.md — 12 slices, research-backed
- HOW_IT_WORKS_NONTECHNICAL_2026-04-05.md — plain language guide
- HOW_IT_WORKS_TECHNICAL_2026-04-05.md — full block diagram, component table
- PIPELINE_STAGES_AND_THROUGHPUT_2026-04-05.md — 3 stages, speeds, costs, commands
- TOKEN_PRICING_REFERENCE_2026-04-05.md — model costs, budget rules
- AWS_GOVCLOUD_ENRICHMENT_CONCEPT_2026-04-05.md — free OSS processing concept
- QA_EXPECTATIONS updated with agentic eval practices (Section 8)

### Key Findings
- Clone1 dedup: 27.6M chunks but only 89K unique hashes (99.7% duplicates)
- phi4 on 3090: 2.6 chunks/min via Ollama (40-55 tok/sec generation)
- Tiered extraction (regex + GLiNER + GPT-4.1 Nano batch) = $10-50 for full corpus
- SGLang would be 3-5x over Ollama for local extraction
- AWS GovCloud OSS = potentially $0 for all enrichment + extraction
- V1 parallel pipeline: 60-200 chunks/sec proven (ported to CorpusForge)

### Memories Saved
- project_beast_dev_only.md — Beast=dev, work=production
- project_extraction_long_pole.md — extraction is critical path
- project_dedup_strategy_needed.md — 99.7% duplication in V1
- project_v1_parsing_lessons.md — OCR/PDF/encoding edge cases
- feedback_gpu_isolation.md — one GPU per repo
- feedback_ps51_python_embed.md — never embed Python in PS here-strings
- project_rag_research_findings.md — updated with phi4 throughput data

---

## Sprint 5 Status

**Coding: COMPLETE. QA: PENDING.**

| Track | Status |
|-------|--------|
| A: CorpusForge on Beast | Setup verified (26 PASS). Pipeline coded. GUI not yet tested on real files. |
| B: V2 Pipeline | Import hardened. First real query NOT YET DONE (needs CorpusForge export first). |
| C: phi4 Validation | A/B test ran (phi4 only, 9/10 success). GPT-4o comparison not yet run (needs API key set). |
| D: Clone1 Learning | Dedup analysis done (99.7% dupes). Parsing/chunking analysis deferred. |
| E: Environment | Both setups verified. Ollama installed. API key NOT set. Tesseract/Poppler NOT installed. |

**Sprint 5 QA checklist:** In docs/SPRINT_PLAN_REVISED_2026-04-05.md under "Sprint 5 QA Checklist"

**Waiver from user:** QA Sprint 5 and Sprint 6 together when user returns. Proceed to Sprint 6 coding.

---

## Sprint 6: What To Do Next

**Game plan:** docs/SPRINT_6_GAMEPLAN_2026-04-05.md (12 slices, fully planned)

**Priority slices for next agent:**

1. **6.1** Run CorpusForge on 100+ source files from `C:\HybridRAG_V2\data\source\role_corpus_golden` (14 files) or a larger subset
2. **6.3** Import the CorpusForge export into V2 LanceDB
3. **6.4** Build IVF_PQ index on LanceDB (sqrt(N) partitions, nprobes=20)
4. **6.6** MinHash dedup pipeline (datasketch library, 5-gram shingles, LSH banding)
5. **6.7** Golden eval on real data — run 25-query set
6. **6.9** Benchmark: full pipeline throughput report
7. **6.10** Package wheels for work machine deployment

**Research already done:** LanceDB scaling, MinHash vs SimHash, golden eval practices, production ingestion patterns, work machine deployment. All in SPRINT_6_GAMEPLAN.

---

## Key Rules (from memory, non-negotiable)

- Never mention claude/anthropic/agent/AI in repos — use "CoPilot+" only
- Never modify global shell config (registry, PATH, profiles)
- Never commit config.yaml changes without approval
- Sanitize before push: local commit -> sanitize -> push
- PS 5.1: never embed Python in here-strings, use temp file + WriteAllText pattern
- All bat files must have CRLF line endings
- All PS files must be ASCII-only (no em-dashes or Unicode)
- Beast = dev only, work = production
- GPU isolation: hardcode GPU 0, temp set GPU 1 when needed
- Research before implementing — web search, never guess
- phi4 for stress tests, GPT-4o for accuracy/demo only
- Under $50 budget for extraction = no issues

---

## Files That Matter

| File | What |
|------|------|
| C:\HybridRAG_V2\docs\SPRINT_PLAN_REVISED_2026-04-05.md | Active sprint plan |
| C:\HybridRAG_V2\docs\SPRINT_6_GAMEPLAN_2026-04-05.md | Next sprint plan |
| C:\HybridRAG_V2\docs\PIPELINE_STAGES_AND_THROUGHPUT_2026-04-05.md | How the 3 stages work |
| C:\HybridRAG_V2\docs\HOW_IT_WORKS_TECHNICAL_2026-04-05.md | Full architecture |
| C:\HybridRAG_V2\config\config.yaml | V2 config |
| C:\CorpusForge\config\config.yaml | CorpusForge config |
| C:\CorpusForge\src\pipeline.py | Parallel pipeline (just ported) |
| C:\HybridRAG_V2\src\llm\client.py | LLM client (Azure/OpenAI/Ollama) |
| C:\HybridRAG_V2\scripts\overnight_extraction.py | Currently running on GPU 0 |

---

## User Context

- Demo target: May 2, 2026 for civilian defense contractors
- User is visiting family for a few hours
- User approved: skip Sprint 5 QA, proceed to Sprint 6, QA both together on return
- User likes parallel agent work, maximum productivity
- User wants research before action, structured sprints, no dark work
- AWS agent is working in parallel on GovCloud OSS integration (separate session)

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
