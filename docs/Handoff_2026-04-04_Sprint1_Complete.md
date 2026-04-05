# Session Handoff — 2026-04-04 Night Session

**Author:** Jeremy (CoPilot+)
**Date:** 2026-04-04 ~22:15 MDT
**Repos:** CorpusForge + HybridRAG V2
**Demo Target:** 2026-05-02

---

## What Got Done Tonight

Knocked out Sprint 0 + Sprint 1 in one session (originally planned for Days 1-8).

### Sprint 0 — COMPLETE (18/18 QA)
- **Slice 0.1:** Pydantic config schemas + boot validation for both repos
- **Slice 0.2:** CorpusForge minimal pipeline (txt parser, chunker, chunk IDs, embedder, packager — all ported from V1)
- **Slice 0.3:** V2 import + LanceDB store + query pipeline (retriever, context builder, generator with graduated confidence)
- **Slice 0.4:** First 5 golden eval queries — 5/5 retrieval passing

### Sprint 1 — COMPLETE (12/12 QA)
- **Slice 1.1:** 21-format parser stack (PDF multi-stage + OCR, DOCX, XLSX, PPTX, CSV, MSG, HTML, RTF, JSON, XML + dispatcher)
- **Slice 1.2:** SHA-256 hash + dedup (_1 suffix detection, incremental skip — verified 0 files on re-run)
- **Slice 1.3:** FlashRank reranking (4MB model, sub-20ms, wired into context builder)
- **Slice 1.4:** SSE streaming endpoint (POST /query/stream)
- **Slice 1.5:** Scale test on 5 files (12 chunks), golden eval expanded to 10/10 passing

---

## Current State

### CorpusForge
- **Pipeline:** download → hash/dedup → parse (21 formats) → chunk (1200/200) → embed (nomic 768d CUDA) → export
- **Tested:** 5 files → 12 chunks → 768d float16 vectors → export package
- **Dedup verified:** unchanged files skipped, _1 suffix duplicates detected
- **Git:** master pushed to remote, sanitized

### HybridRAG V2
- **Store:** LanceDB v0.30.2 (hybrid vector + BM25 via Tantivy)
- **Query pipeline:** embedder → LanceDB hybrid search → FlashRank rerank → context builder → GPT-4o generator
- **API:** FastAPI with POST /query, POST /query/stream (SSE), GET /health
- **Golden eval:** 10/10 retrieval passing (Thule + Riverside cross-document)
- **LLM generation:** Wired but needs `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` env vars
- **Git:** master pushed to remote, sanitized

### Packages Installed (waiver-pending, dev testbed)
- lancedb 0.30.2
- flashrank (ms-marco-MiniLM-L-12-v2, 4MB)

---

## What's Next — Sprint 2 (Days 9-15)

| Slice | What | Repo |
|---|---|---|
| 2.1 | Contextual enrichment (phi4:14B via Ollama) | CorpusForge |
| 2.2 | GLiNER2 entity extraction (zero-shot NER) | CorpusForge |
| 2.3 | Quality gates + normalization (controlled vocab) | V2 |
| 2.4 | Entity + relationship SQLite stores | V2 |
| 2.5 | Query router + structured retrieval | V2 |

### Blockers / Needs
- **API creds:** Set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` to unlock LLM generation tests
- **Ollama:** Needs phi4:14B pulled for enrichment (`ollama pull phi4:14b-q4_K_M`)
- **GLiNER:** `pip install gliner` when ready (waiver shared with V2)
- **Real corpus:** Point pipeline at production files for proper scale test

---

## Rules Established This Session

1. **Push workflow:** local commit → `python sanitize_before_push.py --apply` → push sanitized to remote
2. **sanitize_before_push.py** is in .gitignore — NEVER push it to remote
3. **No AI attribution:** No mention of anthropic/claude/agent in code, docs, or git. Use "CoPilot+". Commits by Jeremy only.
4. **extra="forbid"** on both config schemas — catches YAML typos
5. **Install waiver-pending packages** on dev testbed — don't delay for waivers unless hard no

---

## File Counts

| Repo | Python files | Max lines | Total lines |
|---|---|---|---|
| CorpusForge | 21 | 246 | ~1,315 |
| HybridRAG V2 | 24 | 249 | ~1,987 |

All files under 500-line limit.

---

Jeremy | HybridRAG_V2 + CorpusForge | 2026-04-04 MDT
