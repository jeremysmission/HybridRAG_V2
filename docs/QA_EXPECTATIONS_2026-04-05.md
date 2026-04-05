# HybridRAG V2 — QA Expectations

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Applies to:** Every sprint exit, every PR, every demo gate

---

## Philosophy

QA is not "run pytest and see green." QA proves the system works on **real hardware, with real data, under real conditions**. Virtual-only tests prove code compiles. Real tests prove it ships.

---

## 1. Environment Requirements

Before any QA pass:

```bash
# Single GPU to emulate Blackwell workstations at work
set CUDA_VISIBLE_DEVICES=0

# Activate repo-local venv
cd C:\HybridRAG_V2
.venv\Scripts\activate

# Verify CUDA
python -c "import torch; assert torch.cuda.is_available(), 'NO CUDA'; print(f'GPU: {torch.cuda.get_device_name(0)}')"
```

**Rule:** If CUDA is not available, QA is invalid. Do not proceed with CPU-only results and call it "passing."

---

## 2. Five QA Pillars

Every sprint QA must cover all five. No exceptions, no "we'll test that later."

### Pillar 1: Boot & Config
**Proves:** System starts up, config validates, stores initialize.

| Check | Command | Expected |
|-------|---------|----------|
| Config loads | `python scripts/boot.py` | No errors, prints summary |
| Bad config caught | Add `bogus_field: true` to config.yaml, boot | Pydantic error, clear message |
| Missing config | Rename config.yaml, boot | Warning, falls back to defaults |

### Pillar 2: Core Pipeline (real GPU, real API)
**Proves:** The primary query path works end-to-end on real hardware.

| Check | Command | Expected |
|-------|---------|----------|
| Embedding on CUDA | `Embedder()` loads, `embed_query("test")` returns 768-dim vector | Mode: cuda, shape: (768,) |
| LLM client connects | `LLMClient()` with API key, `call("say hello")` | Response text, token counts |
| Router classifies | 5 query types through live GPT-4o | 5/5 correct |
| Full query pipeline | POST /query with real question | Answer with confidence + sources |
| Streaming works | POST /query/stream | metadata → tokens → done events |

### Pillar 3: 3-Tier Test Corpus
**Proves:** System handles clean, messy, and adversarial inputs correctly.

| Tier | Files | Expected |
|------|-------|----------|
| **Tier 1 (smoke)** | `tests/test_corpus/tier1_smoke/` | Clean extraction: entities, relationships, tables. All golden queries find expected facts. |
| **Tier 2 (stress)** | `tests/test_corpus/tier2_stress/` | Handles messy email chains, OCR garbage, spreadsheet fragments. Extraction still finds key entities. |
| **Tier 3 (negative)** | `tests/test_corpus/tier3_negative/` | Empty files → 0 entities. Binary → graceful skip. Prompt injection → no leakage. Foreign language → no hallucination. |

**Rule:** Every tier must be tested. A sprint that only tests tier 1 has not been QA'd.

### Pillar 4: Real Data Pass
**Proves:** System works on actual production IGS documents, not just synthetic test files.

| Check | Expected |
|-------|----------|
| Import real corpus subset (50-100 files) | Ingest completes, no crashes, no OOM |
| Embed real documents on GPU 0 | Batch embedding completes, GPU memory stays under 20GB |
| Extract entities from real docs | Entities, relationships, table rows populated |
| Query real data | Answers reference real document content, not hallucinated |

**Rule:** If no real production data is available yet, note it as a gap — do not skip this pillar silently.

### Pillar 5: Graceful Degradation
**Proves:** System fails safely when things are missing or wrong.

| Check | Expected |
|-------|----------|
| No API key | Server boots, reports "LLM not configured", returns 503 on queries |
| No CUDA | Falls back to ONNX CPU embedding (slower but functional) |
| Empty LanceDB store | Returns "No data loaded" 503, does not crash |
| Empty entity store | Lookup returns empty list, pipeline falls back to vector-only |
| Corrupted input file | Parser skips gracefully, logs warning, continues with next file |

---

## 3. Golden Eval Gate

Golden eval queries are the minimum bar for demo readiness.

| Sprint | Target | Query File |
|--------|--------|------------|
| Sprint 1 | 10/10 retrieval | `tests/golden_eval/golden_queries.json` (GQ-001 through GQ-010) |
| Sprint 2 | 20/20 retrieval, 10/20 generation | `tests/golden_eval/golden_queries.json` (GQ-001 through GQ-020) |
| Sprint 3 | 15/20 full end-to-end | Same file |
| Sprint 4 (demo) | 20/20 full end-to-end | Same file + new queries from real corpus |

**Retrieval pass:** Expected facts appear in the retrieved context (does not require LLM generation).
**Generation pass:** LLM answer contains expected facts with correct confidence level.

---

## 4. QA Report Template

Every sprint QA produces a report. Copy this template:

```
# Sprint [N] QA Report
Date: YYYY-MM-DD
Tester: [name]
Hardware: [Beast single GPU / laptop / other]
API: [commercial OpenAI / Azure / none]

## Environment
- Python: [version]
- torch: [version], CUDA: [yes/no], GPU: [name]
- CUDA_VISIBLE_DEVICES: [value]
- venv: [fresh / existing]

## Pillar 1: Boot & Config
- [ ] Config loads cleanly
- [ ] Bad config caught by Pydantic
- [ ] Missing config falls back to defaults

## Pillar 2: Core Pipeline
- [ ] Embedding on CUDA: mode=[cuda/onnx], dim=[768]
- [ ] LLM client: provider=[openai/azure], available=[true/false]
- [ ] Router: [X]/5 correct classifications
- [ ] Full query: answer received with confidence
- [ ] Streaming: metadata + tokens + done

## Pillar 3: 3-Tier Corpus
- [ ] Tier 1 (smoke): [X] entities, [X] relationships, [X] table rows
- [ ] Tier 2 (stress): [X] entities from messy input
- [ ] Tier 3 (negative): empty=0, binary=skip, injection=safe

## Pillar 4: Real Data
- [ ] Import: [X] files ingested
- [ ] Embedding: completed, GPU peak=[X]GB
- [ ] Extraction: [X] entities, [X] relationships
- [ ] Query: answers reference real content
- [ ] (or) SKIPPED — no real data available, noted as gap

## Pillar 5: Graceful Degradation
- [ ] No API key: 503, no crash
- [ ] Empty store: 503, no crash
- [ ] Corrupted input: skipped, logged

## Golden Eval
- Retrieval: [X]/20 passing
- Generation: [X]/20 passing (or N/A if no API key)

## Issues Found
1. [description, severity, steps to reproduce]

## Verdict
- [ ] PASS — ready for next sprint
- [ ] CONDITIONAL — minor issues, fix and retest [list items]
- [ ] FAIL — blocking issues [list items]

Signed: [name] | [repo] | [date] MDT
```

---

## 5. QA Frequency

| Event | QA Required |
|-------|-------------|
| Sprint exit | Full 5-pillar QA |
| PR to main | Pillar 1 + 2 minimum |
| Demo gate | Full 5-pillar + golden eval generation pass |
| Dependency upgrade | Pillar 1 + 2 + GPU memory check |
| New parser/format | Pillar 3 (all tiers) |

---

## 6. GUI QA (Sprint 3+)

When a GUI is present, add the full GUI QA protocol from `docs/QA_GUI_HARNESS_2026-04-05.md`:

- **Tier A:** Scripted functional tests (automated event injection)
- **Tier B:** Smart monkey (targeted chaos on query submit, index, settings)
- **Tier C:** Dumb monkey (60s random clicks, 0 crashes/freezes tolerance)
- **Tier D:** Human button smash (10 min, non-developer tries to break it)

**Rule:** Demo gate requires a human button smash by someone who didn't write the code.

---

## 7. While QA Is Running: Next-Sprint Prep Protocol

QA time is not idle time. While QA executes tests, the engineering team runs this protocol in parallel:

### Step 1: Re-read Architecture Docs
- Review `docs/Architecture_Pseudocode_2026-04-04.md` for next sprint's pseudocode
- Review `docs/Sprint_Plan_2026-04-04.md` for next sprint's slices and exit criteria
- Identify any gaps between the plan and what was actually built

### Step 2: Web Research (mandatory — never guess)
- For each slice in the next sprint, web search current best practices (2025-2026)
- Search for failure modes and pitfalls specific to the techniques being used
- Search for production implementation patterns (not just theory)
- Document findings with source links

### Step 3: Game Plan
- Write out the slice breakdown with estimated effort
- Identify parallelizable work (what can subagents do simultaneously?)
- Map dependencies (what blocks what?)
- List risks and mitigations
- Identify pre-sprint checklist items (models to pull, creds to set, data to stage)

### Step 4: Capture
- Save the game plan so the sprint starts immediately when QA passes
- No re-discovery, no cold starts — the plan is ready to execute

**Rule:** Every sprint QA period must produce a next-sprint game plan. QA and planning happen in parallel, not sequentially.

---

## 8. What QA Does NOT Cover (Out of Scope)

- Production deployment (Azure/GovCloud) — separate ops checklist
- Security pen testing — separate engagement
- Performance benchmarking (P50/P95 latency) — Sprint 4 activity

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
