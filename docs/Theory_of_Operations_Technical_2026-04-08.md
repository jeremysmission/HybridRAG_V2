# HybridRAG V2 — Theory of Operations (Technical)

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-08 MDT
**Audience:** Software engineers, system administrators, integration team
**Status:** Current — reflects Sprint 15 architecture with CorpusForge integration proven

---

## 1. System Architecture Overview

HybridRAG V2 is a two-plane system: a nightly **ingest plane** (CorpusForge, separate repo) and a daytime **query plane** (this application). The planes are fully decoupled — they share only an export package written to disk.

### 1.1 Ingest Plane (CorpusForge — Separate Application)

Runs nightly on a dedicated workstation with GPU. Processes source documents into query-ready artifacts.

**Pipeline stages:**

```
Source Files (420K files, 700GB, 60+ formats)
    |
    v
[1] HASH AND DEDUPLICATE
    SHA-256 content hashing for change detection
    _1 suffix duplicate detection (49.7% of corpus is duplicated)
    Skip unchanged files (incremental processing)
    |
    v
[2] SKIP AND DEFER
    Config-driven format decisions (skip_list.yaml + defer_extensions)
    Deferred files hashed and recorded in skip manifest
    OCR sidecar junk filtered (17 suffix patterns)
    |
    v
[3] PARSE
    31 parser types for 60+ formats: PDF, Office, email, text, CAD, etc.
    Per-file timeout: 60 seconds
    Parse quality scoring: 0.0-1.0
    OCR fallback for scanned PDFs (requires Tesseract + Poppler)
    |
    v
[4] CHUNK
    Fixed-size: 1200 characters, 200 character overlap
    Smart boundary splitting at sentence boundaries
    Deterministic chunk IDs: SHA-256(file_path + chunk_index)
    |
    v
[5] CONTEXTUAL ENRICHMENT (optional)
    phi4:14B (local GPU, free) prepends document-level context
    67% retrieval quality improvement measured in A/B testing
    |
    v
[6] EMBED
    nomic-embed-text v1.5 (768 dimensions, CUDA)
    Token-budget batching with OOM backoff
    Output: float16 vectors. Throughput: 305 chunks/sec on RTX 3090.
    |
    v
[7] ENTITY EXTRACTION (two-pass)
    Pass 1: Regex (15 patterns, 3,311 chunks/sec, 94.2% coverage)
    Pass 2: GLiNER2 (selective, CPU, for PERSON/ORG/SITE in prose)
    Outputs candidate entities with confidence scores
    |
    v
[8] EXPORT
    Package: chunks.jsonl, vectors.npy, entities.jsonl, manifest.json
    Plus run_report.txt and skip_manifest.json
```

**Performance characteristics (measured on 90GB production sample):**
- Text-first pipeline (no OCR, no enrichment): ~55 minutes for full corpus
- Incremental nightly: minutes (only new/changed files)
- Full re-index with OCR and enrichment: 2-4 days

### 1.2 Query Plane (HybridRAG V2 — This Application)

Runs on operator workstations during the day. Consumes CorpusForge exports and serves queries.

**Startup sequence:**

```
[1] BOOT
    Load config.yaml (Pydantic validation, hardware preset)
    Validate paths, check LanceDB/SQLite stores exist
    |
    v
[2] IMPORT (if new CorpusForge export detected)
    Load new chunks + vectors into LanceDB
    Run entity extraction (regex first, then selective GPT-4o)
    Apply quality gates (confidence >= 0.7)
    Normalize entities against controlled vocabularies
    Promote validated entities to production SQLite tables
    Generate extraction audit report
    |
    v
[3] READY
    All three stores loaded and indexed
    FastAPI server listening on configured port
    Tkinter GUI launched (if desktop mode)
```

---

## 2. Query Pipeline (Per-Request)

### 2.1 Request Flow

```
User Question
    |
    v
[ROUTER] GPT-4o classification call (~100 tokens, ~0.5s)
    Classifies: SEMANTIC | ENTITY_LOOKUP | AGGREGATION | TABULAR | COMPLEX
    Expands synonyms
    For COMPLEX: decomposes into 2-5 sub-queries
    |
    v
[RETRIEVE] Route to appropriate store(s)
    |
    +--> STORE 1: LanceDB (for SEMANTIC queries)
    |    Vector kNN search (top-30 candidates)
    |    + BM25 full-text search (top-30 candidates)
    |    + RRF fusion (built-in)
    |    + Metadata filtering (site, date range, doc type)
    |    Latency: 25-50ms
    |
    +--> STORE 2: SQLite Entities (for ENTITY_LOOKUP, AGGREGATION)
    |    Direct SQL query against validated entity tables
    |    GPT-4o generates SQL from natural language (Text2SQL)
    |    SQL validated: only SELECT allowed, no mutations
    |    Latency: 5-50ms
    |
    +--> STORE 3: SQLite Relationships (for multi-hop queries)
         Entity-relationship triple lookup via SQL JOINs
         Latency: 10-100ms
    |
    v
[RERANK] FlashRank (for SEMANTIC path results)
    4MB quantized model, CPU inference
    Reranks top-30 candidates to top-10
    Latency: <20ms for 30 candidates
    |
    v
[CONTEXT BUILD]
    Merge results from all stores
    Deduplicate (same chunk from vector + keyword paths)
    Quality weighting (prefer higher parse-quality chunks)
    Assemble context: top 15-25 chunks + SQL results
    |
    v
[GENERATE] GPT-4o generation call
    Graduated confidence prompt (HIGH / PARTIAL / NOT_FOUND)
    Citation requirement (every claim cites source document + section)
    Streaming output (SSE for API, callback for GUI)
    Latency: 2-4s simple, 3-6s complex (streaming TTFT ~0.5s)
    |
    v
[OPTIONAL: CRAG VERIFICATION]
    Grades response against retrieved sources
    If confidence < 0.8: rewrite query, re-retrieve, re-generate
    Maximum 2 retries
    |
    v
[RESPONSE]
    {
      answer: "streamed text",
      confidence: "HIGH" | "PARTIAL" | "NOT_FOUND",
      sources: [{path, section, relevance_score}],
      query_path: "SEMANTIC" | "ENTITY_LOOKUP" | "AGGREGATION" | ...,
      latency_ms: 3500,
      tokens_used: {input: 4200, output: 850},
      cost_usd: 0.04
    }
```

### 2.2 Latency Budget

| Stage | P50 | P95 | Notes |
|-------|-----|-----|-------|
| Router classification | 300ms | 800ms | Single GPT-4o call |
| LanceDB hybrid search | 30ms | 80ms | Tantivy FTS + vector kNN |
| SQLite entity/aggregate | 5ms | 50ms | Indexed queries |
| FlashRank reranking | 15ms | 40ms | 4MB model, CPU |
| Context building | 5ms | 20ms | In-memory merge |
| GPT-4o generation | 2000ms | 4000ms | Streaming TTFT ~500ms |
| CRAG verification | 300ms | 500ms | Optional |
| **Total (simple)** | **~2.5s** | **~5s** | |
| **Total (complex)** | **~4s** | **~8s** | |

**Measured:** P50=20ms retrieval, P95=57ms retrieval (Sprint 15). Generation dominates latency.

---

## 3. Data Stores

### 3.1 Store 1: LanceDB (Vector + Full-Text Hybrid)

Apache 2.0, embedded serverless database using Apache Arrow / Lance columnar format with Tantivy full-text engine. Single Lance directory, disk-backed, memory-mapped.

### 3.2 Store 2: SQLite Entity Tables (Quality-Gated)

SQLite3 (stdlib). Validated entities with normalized text, type, confidence, and provenance tracking. Controlled vocabulary matching for sites and part number patterns.

### 3.3 Store 3: SQLite Relationship Tables

Entity-relationship triples (subject-predicate-object) for multi-hop queries.

---

## 4. Quality-Gated Extraction Pipeline

### 4.1 Three-Pass Extraction

**Pass 1: Regex (instant, free)**
- 15 compiled patterns for CONTACT, DATE, PART_NUMBER, PO, labeled SITE/PERSON
- 94.2% chunk coverage at 3,311 chunks/sec

**Pass 2: GLiNER2 (selective, free, CPU)**
- Zero-shot NER for PERSON, ORG, SITE in prose text
- Run on chunks where regex found zero entities
- 82 unique entities found that regex missed in 100-chunk comparison

**Pass 3: GPT-4o (complex chunks, API cost)**
- For chunks with complex narratives, failure descriptions, relationship statements
- Structured event extraction with action, component, serial numbers
- ~$200 one-time cost for full corpus

### 4.2 Quality Gate

Confidence >= 0.7 required. Type-specific validation (site vocabulary matching, part number pattern validation, person name separation from contact info). All rejections logged to review queue with audit trail.

---

## 5. Security Model

### 5.1 Data Flow

- **Ingest (local):** No data leaves the machine. phi4:14B, nomic embedding, and GLiNER all run locally.
- **Query (outbound):** Only query text + retrieved context chunks sent to GPT-4o API (Azure endpoint, HTTPS). No source files or full index transmitted.
- **Response:** Not stored externally.

### 5.2 Protections (Current State)

- Injection guard: prompt template prevents prompt injection echo
- Query history logged locally for audit, never transmitted
- API keys stored in Windows Credential Manager (keyring)
- **Gap:** No outbound PII scrubber is implemented. Raw chunk text and user queries are sent to the LLM API without redaction. A PII scrub/redact layer is a planned future enhancement.

---

## 6. Deployment Model

### 6.1 Local Deployment (Primary)

- Beast workstation: dual GPU, runs CorpusForge nightly + V2 query daytime
- Laptop: no GPU, receives index export via file share, query app only

### 6.2 Cloud Deployment (Fallback)

- AWS GovCloud: OpenSearch Managed + SageMaker Serverless + Lambda + S3
- Cost: ~$65-90/month
- Not primary path for demo

---

## 7. Failure Modes and Recovery

| Failure | Impact | Recovery |
|---------|--------|---------|
| API endpoint down | No new queries (retrieval still works locally) | Fail-fast with error message. Operator retries manually when connectivity returns. |
| LanceDB corruption | No vector/BM25 search | Re-import from CorpusForge export |
| SQLite corruption | No entity/aggregation queries | Re-run extraction pipeline |
| CorpusForge crash mid-run | Partial nightly update | Deterministic chunk IDs enable safe resume |
| GPU OOM during embedding | Embedding batch fails | Token-budget batching with automatic OOM backoff |

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
