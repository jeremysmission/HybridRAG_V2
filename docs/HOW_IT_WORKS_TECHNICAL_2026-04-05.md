# How HybridRAG V2 Works — Technical Theory of Operations

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT

---

## System Architecture

Two independent repos form a producer-consumer pipeline:

```
==========================================================================
                        BLOCK DIAGRAM
==========================================================================

  SOURCE FILES (700GB)         CLONE1 INDEX (75GB SQLite)
  PDF, DOCX, XLSX, EML...     27.6M pre-chunked texts from V1
       |                              |
       v                              |
  +-----------+                       |
  |CORPUSFORGE|                       |
  | (Stage 1) |                       |
  +-----------+                       |
       |                              |
       | 8 parallel                   |
       | parser threads               |
       v                              |
  [Parse] -> [Chunk] -> [Enrich*] -> [Embed]  -> [Export]
   27 parsers  1200 char   phi4:14b    CUDA GPU    chunks.jsonl
   CPU bound   200 overlap  optional   60-200/sec  vectors.npy
               700K/sec    3/min                    
       |                              |
       v                              |
  EXPORT PACKAGE                      |
  chunks.jsonl + vectors.npy          |
       |                              |
       v                              |
  +-----------+                       |
  |HYBRIDRAG  |                       |
  |    V2     |                       |
  | (Stage 2) |                       |
  +-----------+                       |
       |                              |
       v                              v
  [Import]                    [Extract Entities]
  LanceDB batch insert        phi4 via Ollama (current)
  1000 chunks/batch           OR SGLang (planned, 3-5x)
  ~10K/sec                    OR GPT-4.1 Nano batch API
       |                      OR GLiNER first pass + LLM
       |                              |
       v                              v
  +----------+                +--------------+
  | LanceDB  |                |   SQLite     |
  | Vector + |                |  entity_store|
  | BM25     |                |  rel_store   |
  | Store    |                |              |
  +----------+                +--------------+
  Hybrid search               Entities: PERSON, PART, SITE,
  768-dim vectors              DATE, PO, ORG, CONTACT
  IVF_PQ index                Relationships: POC_FOR,
  FTS5 text index              WORKS_AT, REPLACED_AT, etc.
       |                              |
       +----------+  +----------------+
                  |  |
                  v  v
            +-------------+
            | QUERY       |
            | PIPELINE    |
            +-------------+
                  |
                  v
            [Query Router]  <-- GPT-4o classifies query type
                  |
          +-------+-------+--------+--------+
          |       |       |        |        |
          v       v       v        v        v
       SEMANTIC ENTITY AGGREGATE TABULAR COMPLEX
       vector   SQLite  count    table   decompose
       search   lookup  across   row     into sub-
       + BM25   + rels  docs     query   queries
          |       |       |        |        |
          +-------+-------+--------+--------+
                  |
                  v
            [Reranker]  <-- FlashRank CPU, top-K selection
                  |
                  v
            [Context Builder]  <-- Assembles chunks + entities for LLM
                  |
                  v
            [Generator]  <-- GPT-4o produces answer with citations
                  |
                  v
            [CRAG Verifier]  <-- Optional: grades answer, may re-retrieve
                  |
                  v
            ANSWER + CONFIDENCE + CITATIONS


==========================================================================
                    DATA FLOW SUMMARY
==========================================================================

  Files --[CorpusForge]--> chunks.jsonl + vectors.npy
                               |
                          [V2 Import]
                               |
                               v
                          LanceDB (vector search + BM25)
                               |
  Chunks --[V2 Extract]------> SQLite (entities + relationships)
                               |
                               v
  Question --[V2 Query]------> Answer + Citations

==========================================================================
```

---

## Component Details

### CorpusForge Pipeline (C:\CorpusForge)

| Component | File | Technology | Notes |
|-----------|------|------------|-------|
| Pipeline orchestrator | src/pipeline.py | ThreadPoolExecutor(8) | Parallel parse, sequential embed |
| File dispatcher | src/parse/dispatcher.py | Routes by extension | 27 parsers, 50+ extensions |
| Parsers | src/parse/parsers/*.py | pdfplumber, python-docx, openpyxl, etc. | Each parser isolated, errors don't cascade |
| Skip manager | src/skip/skip_manager.py | YAML config | Hash all, skip deferred formats |
| Deduplicator | src/download/deduplicator.py | SHA-256 file hash | Exact dedup at file level |
| Chunker | src/chunk/chunker.py | Sliding window, sentence boundary | 1200 chars, 200 overlap |
| Contextual enricher | src/enrichment/contextual_enricher.py | phi4:14b via Ollama | Optional, 50-100 token preamble per chunk |
| Embedder | src/embed/embedder.py | sentence-transformers + CUDA | nomic-embed-text-v1.5, 768-dim, fp16 |
| Batch manager | src/embed/batch_manager.py | Token-budget packing | 49K token budget, OOM backoff |
| Packager | src/export/packager.py | JSONL + numpy | chunks.jsonl + vectors.npy |
| Config | src/config/schema.py | Pydantic v2, extra=forbid | Single YAML, validated at boot |

### HybridRAG V2 (C:\HybridRAG_V2)

| Component | File | Technology | Notes |
|-----------|------|------------|-------|
| LanceDB store | src/store/lance_store.py | LanceDB 0.30+ | Vector + BM25 hybrid, batch insert |
| Entity store | src/store/entity_store.py | SQLite3 + WAL | Entities + extracted tables |
| Relationship store | src/store/relationship_store.py | SQLite3 + WAL | Subject-predicate-object triples, multi-hop |
| Entity extractor | src/extraction/entity_extractor.py | GPT-4o structured output | JSON schema enforced, regex pre-extraction |
| Quality gate | src/extraction/quality_gate.py | Site vocabulary + confidence | Normalizes, deduplicates, filters |
| Query router | src/query/query_router.py | GPT-4o classification | SEMANTIC/ENTITY/AGGREGATE/TABULAR/COMPLEX |
| Vector retriever | src/query/vector_retriever.py | LanceDB hybrid search | Vector + BM25 fusion |
| Entity retriever | src/query/entity_retriever.py | SQLite lookups + traversal | Direct entity/relationship queries |
| Reranker | src/query/reranker.py | FlashRank | 4MB CPU model, sub-20ms |
| Context builder | src/query/context_builder.py | Text assembly | Prefers enriched_text over raw |
| Generator | src/query/generator.py | GPT-4o | Graduated confidence: HIGH/PARTIAL/NOT_FOUND |
| CRAG verifier | src/query/crag_verifier.py | LLM-as-judge | Grade → strip refinement → re-retrieve |
| Pipeline | src/query/pipeline.py | Orchestrator | Router → retrieve → context → generate → CRAG |
| LLM client | src/llm/client.py | openai SDK v1.x | Azure/OpenAI/Ollama auto-detection |
| Config | src/config/schema.py | Pydantic v2, extra=forbid | Single YAML, validated at boot |
| REST API | src/api/server.py + routes.py | FastAPI + Uvicorn | /query, /query/stream (SSE), /health |
| GUI | src/gui/*.py | Tkinter | Query panel, entity panel, settings |

---

## Entity Extraction Methods (Current and Planned)

| Method | Technology | Speed | Cost | Status |
|--------|-----------|-------|------|--------|
| Regex pre-extraction | Python re module | Instant | $0 | Active |
| phi4:14b via Ollama | Ollama HTTP → CUDA | 2.6 chunks/min | $0 | Active (Beast dev) |
| phi4:14b via SGLang | SGLang direct CUDA | ~10-20 chunks/min (est.) | $0 | Planned (Sprint 6) |
| GLiNER zero-shot NER | 500M param model, CUDA | 2,400-7,500 chunks/sec | $0 | Waiver pending |
| GPT-4o structured output | OpenAI API | Fast (parallel) | $2.50/1M in | Active (quality baseline) |
| GPT-4.1 Nano batch | OpenAI batch API | Fast (parallel) | $0.05/1M in | Planned (production) |
| GPT-4o-mini batch | OpenAI batch API | Fast (parallel) | $0.075/1M in | Fallback |
| Distilled phi4 | Fine-tuned on GPT-4o output | Same as phi4 | $0 | Research (Sprint 9) |

**Recommended production pipeline:**
1. Regex (instant, free) → catches dates, emails, phones, POs, part numbers
2. GLiNER on GPU (when waiver clears) → catches people, orgs, sites
3. GPT-4.1 Nano batch API → relationships and complex entities
4. Total cost: $10-50 for full corpus

---

## Storage Architecture

```
C:\HybridRAG_V2\data\index\
├── lancedb/              <-- Vector + BM25 search (LanceDB)
│   └── chunks.lance/     <-- 768-dim vectors + chunk text + metadata
└── entities.sqlite3      <-- Entity store + relationship store + tables
                              WAL mode, 64MB cache, mmap 256MB
```

**LanceDB** stores: chunk_id, text, enriched_text, vector (768-dim), source_path, chunk_index, parse_quality
**SQLite entities** stores: entity_type, text, raw_text, confidence, chunk_id, source_path, context
**SQLite relationships** stores: subject, predicate, object, confidence, chunk_id, context

Entities link back to chunks via chunk_id. Queries can go:
- Vector search → chunks → answer (SEMANTIC)
- Entity lookup → entity → linked chunks → answer (ENTITY)
- Entity aggregation → count across documents (AGGREGATE)
- Table query → extracted table rows (TABULAR)
- Decompose → sub-queries → merge (COMPLEX)

---

## GPU Assignment (Beast: Dual RTX 3090)

| GPU | Default Use | VRAM Used | VRAM Free |
|-----|------------|-----------|-----------|
| GPU 0 | CorpusForge embedding OR phi4 extraction | 10-14 GB | 10-14 GB |
| GPU 1 | Available for second instance | 0 GB | 24 GB |

**Rule:** One repo per GPU. No sharing. Set `CUDA_VISIBLE_DEVICES=0` or `=1` before launching. Hardcode GPU 0, temporarily set GPU 1 when needed.

**Work desktop:** Single GPU. Both repos use GPU 0 (never run simultaneously).

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
