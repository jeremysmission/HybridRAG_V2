# HybridRAG V2 — Theory of Operations (Technical)

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-04 MDT
**Audience:** Software engineers, system administrators, integration team
**Status:** Preliminary — capturing initial design intent while fresh

---

## 1. System Architecture Overview

HybridRAG V2 is a two-plane system: a nightly **ingest plane** (EmbedEngine) and a daytime **query plane** (this application). The planes are fully decoupled — they share only an export package written to disk.

### 1.1 Ingest Plane (EmbedEngine — Separate Application)

Runs nightly on a dedicated workstation with GPU. Processes source documents into query-ready artifacts.

**Pipeline stages:**

```
Source Files (420K files, 700GB, 67+ formats)
    |
    v
[1] DOWNLOAD & SYNC
    Fetch new/updated files from network sources
    |
    v
[2] HASH & DEDUPLICATE
    SHA-256 content hashing for change detection
    _1 suffix duplicate detection (54% of corpus is duplicated)
    Skip unchanged files (incremental processing)
    |
    v
[3] PARSE
    32+ format parsers: PDF (pdfplumber + OCR), DOCX, XLSX, PPTX,
    CSV, JSON, XML, TXT, MSG, HTML, RTF, etc.
    Parse timeout: 60 seconds per file
    Parse quality scoring: 0.0-1.0 per file
    |
    v
[4] CHUNK
    Fixed-size chunking: 1200 characters, 200 character overlap
    Smart boundary splitting at sentence boundaries
    Deterministic chunk IDs: SHA-256(file_path + chunk_index)
    |
    v
[5] CONTEXTUAL ENRICHMENT
    phi4:14B (local, GPU, free) prepends document-level context:
    "[From: {filename}, Section: {heading}, Topic: {summary}]"
    Published research shows up to 67% retrieval failure reduction
    |
    v
[6] EMBED
    nomic-embed-text v1.5 (768 dimensions, CUDA)
    Token-budget batching for GPU memory efficiency
    Output: float16 vectors (50% size reduction, negligible quality loss)
    |
    v
[7] FIRST-PASS ENTITY EXTRACTION
    GLiNER2 (205M params, CPU, zero-shot NER)
    Extracts: part numbers, people, sites, dates, organizations
    Outputs candidate entities with confidence scores
    |
    v
[8] EXPORT
    Package written to disk:
    - chunks.jsonl (text, metadata, enriched_text, source_path)
    - vectors (768-dim float16, LanceDB-ready or FAISS-ready)
    - candidate_entities.jsonl (GLiNER2 first-pass results)
    - manifest.json (chunk count, model info, timestamp, hash)
```

**Performance characteristics:**
- Incremental: only new/changed files processed (minutes per nightly run)
- Full re-index: ~2-4 days on dual 3090 GPU workstation
- Memory: GPU VRAM managed via token-budget batching with OOM backoff
- Storage: ~187GB index for 27.6M chunks (40GB embeddings + 77GB FAISS + 70GB SQLite)

### 1.2 Query Plane (HybridRAG V2 — This Application)

Runs on operator workstations during the day. Consumes EmbedEngine exports and serves queries.

**Startup sequence:**

```
[1] BOOT
    Load config.yaml (Pydantic validation, single mode, hardware preset)
    Validate paths, check LanceDB/SQLite stores exist
    |
    v
[2] IMPORT (if new EmbedEngine export detected)
    Load new chunks + vectors into LanceDB
    Run GPT-4o second-pass extraction on complex chunks
    Apply quality gates (confidence >= 0.7)
    Normalize entities against controlled vocabularies
    Promote validated entities to production SQLite tables
    Run Docling table extraction on spreadsheet/PDF sources
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
    Expands synonyms (e.g., "calibration" -> "alignment protocol")
    For COMPLEX: decomposes into 2-5 sub-queries
    |
    v
[RETRIEVE] Route to appropriate store(s)
    |
    +---> STORE 1: LanceDB (for SEMANTIC queries)
    |     Vector kNN search (top-30 candidates)
    |     + BM25 full-text search (top-30 candidates)
    |     + RRF fusion (built-in)
    |     + Metadata filtering (site, date range, doc type)
    |     Latency: 25-50ms
    |
    +---> STORE 2: SQLite Entities (for ENTITY_LOOKUP, AGGREGATION)
    |     Direct SQL query against validated entity tables
    |     GPT-4o generates SQL from natural language (Text2SQL)
    |     SQL validated: only SELECT allowed, no mutations
    |     Latency: 5-50ms
    |
    +---> STORE 3: SQLite Relationships (for multi-hop queries)
          Entity-relationship triple lookup via SQL JOINs
          e.g., Person X is_poc_for Site Y, Part Z failed_at Site W
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
    Parent chunk expansion (retrieve child, return parent for context)
    Quality weighting (prefer higher parse-quality chunks)
    Assemble context: top 15-25 chunks + SQL results + table data
    |
    v
[GENERATE] GPT-4o generation call
    Graduated confidence prompt (HIGH / PARTIAL / NOT_FOUND)
    Citation requirement (every claim cites source document + section)
    Structured data rendered as tables
    Streaming output (SSE for API, callback for GUI)
    Latency: 2-4s for simple, 3-6s for complex (streaming TTFT ~0.5s)
    |
    v
[OPTIONAL: CRAG VERIFICATION] (Sprint 3+)
    GPT-OSS-20B grades response against retrieved sources
    If confidence < 0.8: rewrite query, re-retrieve, re-generate
    Maximum 2 retries
    If still low: return response with [LOW CONFIDENCE] flag
    Latency: +300-500ms per verification, +2-4s per retry
    |
    v
[RESPONSE]
    {
      answer: "streamed text",
      confidence: "HIGH" | "PARTIAL" | "NOT_FOUND",
      sources: [{path, section, relevance_score}],
      query_path: "SEMANTIC" | "ENTITY_LOOKUP" | "AGGREGATION" | ...,
      structured_data: {counts, table_rows, entity_cards},
      latency_ms: 3500,
      tokens_used: {input: 4200, output: 850},
      cost_usd: 0.04
    }
```

### 2.2 Latency Budget

| Stage | P50 | P95 | Notes |
|---|---|---|---|
| Router classification | 300ms | 800ms | Single GPT-4o call, small prompt |
| LanceDB hybrid search | 30ms | 80ms | Tantivy FTS + vector kNN |
| SQLite entity/aggregate | 5ms | 50ms | Indexed queries on normalized data |
| FlashRank reranking | 15ms | 40ms | 4MB model, CPU, 30 candidates |
| Context building | 5ms | 20ms | In-memory merge and assembly |
| GPT-4o generation | 2000ms | 4000ms | Streaming TTFT ~500ms |
| CRAG verification | 300ms | 500ms | Optional, GPT-OSS-20B |
| **Total (simple)** | **~2.5s** | **~5s** | Single-path, no retry |
| **Total (complex)** | **~4s** | **~8s** | Multi-path + decomposition |

Industry standard: enterprise RAG P50 < 3s, P95 < 10s. We meet both.

---

## 3. Data Stores

### 3.1 Store 1: LanceDB (Vector + Full-Text Hybrid)

**Technology:** LanceDB (Apache 2.0, USA), embedded serverless database using Apache Arrow / Lance columnar format with Tantivy full-text engine.

**Schema:**
```
Table: chunks
  chunk_id       TEXT (primary key, SHA-256)
  text           TEXT (original chunk text)
  enriched_text  TEXT (contextually enriched text for BM25)
  vector         VECTOR[768] (nomic-embed-text v1.5, float16)
  source_path    TEXT
  chunk_index    INTEGER
  file_hash      TEXT
  parse_quality  REAL (0.0-1.0)
  doc_type       TEXT (pdf, docx, xlsx, msg, etc.)
  created_at     TIMESTAMP
```

**Index types:**
- IVF-PQ or HNSW for vector search (configurable)
- Tantivy inverted index for BM25 full-text search
- B-tree for metadata filtering (source_path, doc_type, parse_quality)

**Storage:** Single Lance directory, disk-backed, memory-mapped. ~4MB idle RAM footprint.

### 3.2 Store 2: SQLite Entity Tables (Quality-Gated)

**Technology:** SQLite3 (stdlib, no new dependency)

**Tables:**

```sql
-- Validated entities (quality-gated, normalized)
CREATE TABLE entities (
    id              INTEGER PRIMARY KEY,
    entity_text     TEXT NOT NULL,      -- normalized: "Thule" not "Pre-Site Survey Thule AB"
    entity_type     TEXT NOT NULL,      -- PART_NUMBER | PERSON | SITE | DATE | ORG | FAILURE_MODE
    raw_text        TEXT,               -- original extracted text
    confidence      REAL NOT NULL,      -- extraction confidence 0.0-1.0
    chunk_id        TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    extractor       TEXT NOT NULL,      -- "gliner" | "gpt4o"
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Extracted spreadsheet/table rows (Docling output)
CREATE TABLE extracted_tables (
    id              INTEGER PRIMARY KEY,
    source_path     TEXT NOT NULL,
    sheet_name      TEXT,
    headers         TEXT NOT NULL,      -- JSON array
    row_data        TEXT NOT NULL,      -- JSON object {column: value}
    row_index       INTEGER,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookup
CREATE INDEX idx_entity_text ON entities(entity_text);
CREATE INDEX idx_entity_type ON entities(entity_type);
CREATE INDEX idx_entity_source ON entities(source_path);
CREATE INDEX idx_table_source ON extracted_tables(source_path);
```

### 3.3 Store 3: SQLite Relationship Tables

```sql
-- Entity-relationship triples for multi-hop queries
CREATE TABLE relationships (
    id              INTEGER PRIMARY KEY,
    subject_text    TEXT NOT NULL,       -- "SSgt Marcus Webb"
    subject_type    TEXT NOT NULL,       -- PERSON
    predicate       TEXT NOT NULL,       -- "is_poc_for"
    object_text     TEXT NOT NULL,       -- "Thule"
    object_type     TEXT NOT NULL,       -- SITE
    confidence      REAL NOT NULL,
    chunk_id        TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rel_predicate ON relationships(predicate);
CREATE INDEX idx_rel_subject ON relationships(subject_text);
CREATE INDEX idx_rel_object ON relationships(object_text);
```

---

## 4. Quality-Gated Extraction Pipeline

This is the critical subsystem that prevents the garbage-in/garbage-out problem demonstrated by V1's `service_events` and `document_catalog` tables.

### 4.1 Two-Pass Extraction

**Pass 1 (GLiNER2 — fast, free, CPU):**
- Zero-shot NER model, 205M parameters
- Handles structurally predictable entities: part numbers (regex-matchable patterns), dates, site names from file paths, organization names
- Processes ~80% of all entities
- Confidence scores per entity

**Pass 2 (GPT-4o — accurate, API cost, per-chunk):**
- Triggered only for chunks that contain complex narratives (failure descriptions, maintenance diary entries, relationship statements)
- Handles: "Replaced upper HOF board SN 157 with SN 139" → structured event with action, component, removed_serial, installed_serial
- Handles relationship extraction: "POC for Thule is SSgt Webb" → (SSgt Webb, is_poc_for, Thule)
- Processes ~20% of entities, ~$200 one-time cost for full corpus

### 4.2 Quality Gate

```
Input: RawEntity(text, type, confidence, extractor)
    |
    v
[Confidence Check] confidence >= 0.7?
    No  --> REJECT (log to review queue)
    Yes --> continue
    |
    v
[Type-Specific Validation]
    SITE: match against controlled vocabulary (25 known enterprise program sites + aliases)
          "Pre-Site Survey To Thule AB" --> "Thule" (match on alias)
          "Briefing Slides" --> REJECT (no site match)
    PART_NUMBER: validate against known patterns (ARC-\d{4}, IGSI-\d+, PO-\d{4}-\d{4})
          "ARC-4471" --> ACCEPT
          "1509Z" --> REJECT (time, not part number)
    PERSON: separate phone/email from name field
          "Annette Parsons, (970) 986-2551" --> name="Annette Parsons", phone="(970) 986-2551"
    |
    v
[Normalize] apply canonical form
    |
    v
[Promote] insert into production entity tables
    |
    v
[Audit] log extraction stats:
    "Extracted 14,000 part mentions, 8,200 passed validation (58.6% acceptance rate)"
    "Top rejection reasons: low_confidence (32%), unknown_site (14%), invalid_part_format (12%)"
```

### 4.3 Controlled Vocabularies

Site vocabulary (maintained as YAML config):
```yaml
Thule:       [thule, thule ab, thule afb, thule air base]
Alpena:      [alpena, alpena crtc, alpena combat readiness]
Learmonth:   [learmonth, learmonth raaf]
Guam:        [guam, andersen, andersen afb]
Ascension:   [ascension, ascension island]
# ... 25 total sites with known aliases
```

Part number patterns:
```yaml
patterns:
  - "ARC-\\d{4}"
  - "IGSI-\\d+"
  - "PO-\\d{4}-\\d{4}"
  - "SN \\d+"
  - "SEMS3D-\\d+"
```

---

## 5. Security Model

### 5.1 Data Flow

```
INBOUND (ingest):
  Source files -> EmbedEngine (local) -> export package (local disk)
  No data leaves the machine during ingest (phi4:14B + nomic are local)

OUTBOUND (query):
  User query + retrieved context -> GPT-4o API (Azure endpoint, HTTPS)
  Only the query text and context chunks are sent
  No source files or full index data leaves the machine

RESPONSE:
  GPT-4o response -> local application -> user display
  Response is not stored externally
```

### 5.2 PII Protection

- PII scrubber runs on all outbound API calls (regex-based detection of SSN, email, phone, IPv4, credit card)
- Injection guard: 9-rule prompt template prevents prompt injection echo
- Query history logged locally (SQLite) for audit, never transmitted

### 5.3 Access Control

- Local application: operator's Windows credentials
- API access: Azure OpenAI API key stored in Windows Credential Manager (keyring)
- No multi-user access control in V2 MVP (single-operator workstation model)

---

## 6. Deployment Model

### 6.1 Local Deployment (Primary)

```
Beast Workstation (primary):
  - Dual GPU (3090 FE, 24GB each)
  - 128GB RAM
  - 2TB NVMe (C: drive)
  - Runs EmbedEngine nightly + V2 query app daytime
  - Both apps on same machine, different processes

Laptop Deployment (secondary):
  - No GPU (FAISS fallback if LanceDB needs GPU)
  - 16-32GB RAM
  - Receives index export via file share
  - Runs V2 query app only
```

### 6.2 Cloud Deployment (Fallback — GovCloud)

```
AWS GovCloud:
  - OpenSearch Managed (replaces LanceDB) — kNN + BM25, FedRAMP High
  - SageMaker Serverless (replaces local embedder) — nomic-embed-text
  - Lambda (replaces local FastAPI) — query + ingest functions
  - S3 (replaces local filesystem) — enterprise program-rag-index bucket
  - AI Toolbox GPT-OSS (same) — LLM endpoint
  - Cost: ~$65-90/month
```

---

## 7. Monitoring and Observability

### 7.1 Query Metrics (logged per request)

- Query text (scrubbed of PII)
- Query type classification
- Retrieval path used
- Number of chunks retrieved and scored
- Final chunk count sent to LLM
- Confidence level returned
- Latency breakdown (retrieval, reranking, generation)
- Token usage and estimated cost
- Whether CRAG retry was triggered

### 7.2 Extraction Metrics (logged per ingest run)

- Files processed / skipped / failed
- Chunks created
- Entities extracted / validated / rejected
- Tables extracted
- Rejection reasons breakdown
- Processing time

### 7.3 Index Health (on-demand audit)

- Total chunks in LanceDB
- Total entities in SQLite (by type)
- Total relationships
- Total extracted table rows
- Coverage: what percentage of source files produced entities
- Staleness: when was the last ingest run

---

## 8. Failure Modes and Recovery

| Failure | Impact | Recovery |
|---|---|---|
| API endpoint down | No new queries (retrieval still works locally) | Queue queries, retry on reconnection |
| LanceDB corruption | No vector/BM25 search | Re-import from EmbedEngine export |
| SQLite corruption | No entity/aggregation queries | Re-run extraction pipeline |
| EmbedEngine crash mid-run | Partial nightly update | Deterministic chunk IDs enable crash-safe resume |
| GPU OOM during embedding | Embedding batch fails | Token-budget batching with automatic OOM backoff |
| Extraction produces garbage | Bad structured query results | Quality gates reject, audit report surfaces issues |

---

Jeremy Randall | HybridRAG_V2 | 2026-04-04 MDT
