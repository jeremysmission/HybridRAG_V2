# HybridRAG V2 — Design Proposal

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-04 MDT
**Origin:** Design review and competitive evaluation of 6 architecture proposals
**Constraint:** All software must pass waiver sheet; all origins USA or NATO allies

---

## 1. Executive Summary

HybridRAG V1 proved that retrieval is the bottleneck, not the LLM. GPT-4o is wired in and queries still fail because the retrieval architecture feeds garbage to the LLM. V2 fixes three structural failures V1 cannot touch:

1. **Cannot aggregate** — "How many preamp failures at Guam?" requires counting across thousands of documents. Top-5 chunk retrieval is mathematically incapable.
2. **Cannot extract entities** — "Who is the POC for Thule?" requires structured extraction, not semantic similarity.
3. **Cannot query structured data** — Spreadsheet data (logistics parts, service reports) needs SQL, not vector search.

**The critical finding that shaped this design:** V1's structured tables (`service_events`, `document_catalog`) are not empty — they contain 1,902 and 187,204 rows respectively. But the data is garbage. Site names are full document titles ("Pre-Site Survey To Thule AB, 10-20 July 13" instead of "Thule"). POC data exists for only 10 of 187K documents. Zero part numbers are populated in service_events. V1 attempted extraction and produced structurally valid rows with semantically worthless content.

This means V2's extraction pipeline must not just extract — it must **validate and normalize**. That is the core differentiator of this design.

---

## 2. Evidence Base

All evidence was gathered from independent testing on the production 27.6M-chunk index (187GB, ~420K source files, 187K producing chunks).

### 2.1 V1 Query Failures (Measured)

| Query | V1 Returns | The Problem |
|---|---|---|
| "maintenance service report 2025" | JIRA CSV metadata rows mentioning MSRs | Finds the tracker, not the tracked items. Cannot count reports. |
| "Nexion part failure" | Contingency plan prose: "A NEXION unit may experience failure" | Returns the concept of failure, not actual failure instances |
| "point of contact Thule" | Scorecard spreadsheet fragments mentioning Thule | Never extracts the actual POC name |
| "how many service reports filed" | Red Hat Satellite admin docs about vacuumdb | Complete miss — BM25 matched "reports" + "filed" in unrelated IT docs |
| "parts shipped received logistics" | Weekly hours variance spreadsheets with "NEXION LOGISTICS" job codes | Adjacent data, not actual parts tracking |
| "Learmonth site visit" | Items-needed checklist for visits | Correct topic but cannot aggregate across visits |
| "antenna calibration alignment" | Trip report mentioning antenna pad alignment | Returns one instance, cannot compare across sites |
| "ionogram quality degraded" | NEXION Configuration Procedures doc | Returns configuration guidance, not quality incidents |

### 2.2 V1 Structured Table Analysis (The Garbage Data Finding)

**service_events (1,902 rows, 32 columns):**
- Zero populated `part_number` fields
- Zero populated `failure_mode` fields
- `site_canonical` contains 450+ distinct values — nearly all are full document filenames, not site names
- Examples: "(13-0026) Trip Report, Pre-Site Survey To Thule AB, 10-20 July 13", "Briefing Slides", "18 Aug 10"

**document_catalog (187,204 rows, 28 columns):**
- Only 10 documents have `poc_name` populated — all the same person (Annette Parsons)
- Phone numbers bleed into the name field: "Annette Parsons, (970) 986-2551"
- `site_canonical` is garbage: "1" (25,446 docs), "Stats" (1,834), "BIT" (1,295), "Cart" (79)
- `poc_title`, `poc_org`, `poc_phone`, `poc_email`: effectively empty across 187K rows

**Conclusion:** V1 built the right schema and ran some form of extraction. The extraction produced junk. V2 must treat extraction quality as a first-class architectural concern.

### 2.3 Scale Measurements

- 27,607,262 chunks indexed
- ~420,000 source files; 187,204 produced chunks (55% parse failure or skip)
- 768-dim nomic-embed-text v1.5 embeddings (float16)
- FTS5 keyword search latency: 12-24 seconds on 27.6M chunks (measured during testing)
- FAISS vector search: 2-5ms warm queries (proven in V1)
- 54% of files are `_1` suffix duplicates (measured during index analysis)
- Corpus spans 13+ years, 25+ IGS/NEXION sites, 67+ file formats

### 2.4 Debate Insights Incorporated

From the design review, the strongest ideas from each evaluated proposal were incorporated:

| Idea Adopted | Why |
|---|---|
| LanceDB replacing FAISS + FTS5 + memmap | Eliminates 12-24s FTS5 bottleneck; single system replaces 3 |
| Contextual chunk enrichment (proven research technique) | 67% retrieval failure reduction |
| Free enrichment via phi4:14B on EmbedEngine | Zero API cost, zero rate limiting, runs offline nightly |
| Deduplication of _1 suffix files at EmbedEngine | 54% file bloat eliminated before entering query system |
| Knowledge graph as SQLite relationship tables | Multi-hop queries via SQL JOINs, zero new deps |
| CRAG verification loop (adapted) | Self-correcting retrieval for Sprint 3 quality layer |
| GPT-4o for complex entity extraction | Superior on military domain text ("Replaced upper HOF board SN 157 with SN 139") |
| Conservative build order / demo-first | Phase 1 must produce a working system, not a framework |
| Streaming token display as highest-impact UX | Reduces perceived wait time by 50-70% |

---

## 3. Architecture

### 3.1 System Separation

Two hard-separated planes:

**Nightly Ingest Plane (EmbedEngine — separate app):**
- Downloader updates source holdings
- EmbedEngine hashes, deduplicates (_1 suffix detection), parses, chunks
- Contextual enrichment via phi4:14B (free, offline, unlimited)
- Embeds via nomic-embed-text v1.5 (768-dim, CUDA)
- GLiNER2 first-pass entity extraction (CPU)
- Exports package: chunks + vectors + candidate_entities.jsonl

**Daytime Query Plane (HybridRAG V2 — this repo):**
- No indexing during query time
- No offline LLM generation
- No mode switching
- Online-only generation via GPT-4o / GPT-OSS-120B / GPT-OSS-20B
- Consumes EmbedEngine output, builds tri-store, serves queries

### 3.2 Tri-Store Architecture

```
                              User Question
                                   |
                                   v
                    +------------------------------+
                    |   1. QUERY ROUTER (GPT-4o)    |
                    |                                |
                    |   Classify:                     |
                    |   - SEMANTIC -> Store 1         |
                    |   - ENTITY_LOOKUP -> Store 2    |
                    |   - AGGREGATION -> Store 2      |
                    |   - TABULAR -> Store 2          |
                    |   - COMPLEX -> decompose,       |
                    |     route sub-queries to        |
                    |     multiple stores              |
                    |                                |
                    |   Also: expand synonyms,        |
                    |   rephrase for retrieval         |
                    +-------------+----------------+
                                  |
                    +-------------+-------------+
                    v             v             v
         +--------------+ +----------+ +--------------+
         | STORE 1      | | STORE 2  | | STORE 3      |
         | LanceDB      | | SQLite   | | SQLite       |
         |              | | Entities | | Relationships|
         | Vector kNN   | |          | |              |
         | + BM25 hybrid| | Quality- | | person       |
         | + metadata   | | gated    | |  is_poc_for  |
         | + FlashRank  | | entities,| |  site        |
         | reranking    | | extracted| | part         |
         |              | | tables   | |  failed_at   |
         | (Tantivy FTS)| | (Docling)| |  site on date|
         +--------------+ +----------+ +--------------+
                    |             |             |
                    +-------------+-------------+
                                  |
                                  v
                    +------------------------------+
                    |   2. CONTEXT BUILDER           |
                    |   - Merge results from stores  |
                    |   - Deduplicate                 |
                    |   - Parent chunk expansion      |
                    |   - Quality weighting           |
                    |   - Top 15-25 chunks + SQL data |
                    +-------------+----------------+
                                  |
                                  v
                    +------------------------------+
                    |   3. GENERATOR (GPT-4o)        |
                    |   - Graduated confidence:       |
                    |     HIGH / PARTIAL / NOT_FOUND  |
                    |   - Citations per claim          |
                    |   - Structured data as tables    |
                    |   - Reasoning trace              |
                    +------------------------------+
```

### 3.3 Quality-Gated Extraction Pipeline (Core Differentiator)

This is the architectural feature that prevents V2 from repeating V1's garbage extraction:

```
  EmbedEngine Output (chunks + candidate_entities.jsonl)
       |
       v
  STEP 1: FIRST-PASS EXTRACTION (GLiNER2, CPU, free)
  - Part numbers, people, sites, dates, orgs
  - Fast, zero API cost
  - Handles 80% of entities (structural patterns)
       |
       v
  STEP 2: SECOND-PASS EXTRACTION (GPT-4o, API)
  - Complex failure narratives
  - Maintenance diary entries
  - Relationship extraction ("POC for X is Y")
  - Handles 20% of entities (semantic understanding)
  - Cost: ~$200 one-time for corpus
       |
       v
  STEP 3: VALIDATION
  - Confidence score per entity (0.0-1.0)
  - Entities below 0.7 -> review queue
  - Prevents "Briefing Slides" from becoming a site name
  - Prevents "(970) 986-2551" from being part of a person name
       |
       v
  STEP 4: NORMALIZATION
  - Site names matched against controlled vocabulary:
    Thule, Alpena, Learmonth, Guam, Ascension, Eglin,
    San Vito, Osan, Eielson, Loring, Fairford, Wake,
    Eareckson, Lualualei, Djibouti, UAE/Al Dhafra,
    Selfridge, Sagamore Hill, Misawa, Singapore, Azores, etc.
  - "Pre-Site Survey To Thule AB" -> "Thule"
  - Part numbers validated against known patterns (ARC-NNNN, IGSI-NNNN)
  - Person names deduplicated and phone/email separated
       |
       v
  STEP 5: PROMOTE
  - Only validated, normalized entities enter production tables
  - Rejected candidates logged for human review
  - Audit report: "Extracted 14,000 part mentions, 8,200 passed validation"
```

### 3.4 Contextual Chunk Enrichment

At EmbedEngine ingest time, phi4:14B prepends document-level context to each chunk:

```
"[From: Ascension_Maintenance_Report_2024Q1.pdf, Section 4.2 Equipment Failures]
 The connector failed twice in March and once in April. Replacement ordered."
```

- published research: up to 67% reduction in retrieval failures
- Cost: $0 (phi4:14B runs offline on dedicated GPU)
- Rate limiting: none (local inference)
- Enriched text goes into LanceDB's BM25 index alongside original vectors

### 3.5 Query Latency Targets

| Query Type | Target | Breakdown |
|---|---|---|
| Semantic (simple) | 3-5s | LanceDB 50ms + FlashRank 20ms + GPT-4o 2-4s |
| Entity lookup | 1-2s | SQLite <10ms + GPT-4o 1-2s |
| Aggregation | 2-4s | SQLite <50ms + GPT-4o 2-3s |
| Tabular | 1-3s | SQLite <10ms + GPT-4o 1-2s |
| Complex (multi-path) | 5-8s | Router 0.5s + parallel retrieval + GPT-4o 3-5s |

Industry standard: P50 < 3s, P95 < 10s. We meet both with streaming.

---

## 4. Technology Stack

### 4.1 Carry Forward (Already Approved)

| Package | Version | License | Origin | Role |
|---|---|---|---|---|
| Python | 3.11.9 | PSF-2.0 | USA | Runtime |
| numpy | 1.26.4 | BSD-3 | USA | Vector math |
| httpx | 0.28.1 | BSD-3 | UK | HTTP client |
| pydantic | 2.11.1 | MIT | USA | Config validation |
| pyyaml | 6.0.2 | MIT | USA | Config parsing |
| fastapi | 0.115.0 | MIT | USA | API server |
| uvicorn | 0.41.0 | BSD-3 | UK | ASGI server |
| structlog | 24.4.0 | MIT | Germany | Logging |
| sqlite3 | stdlib | Public domain | USA | Entity/table store |
| openai | 1.109.1 | MIT | USA | LLM client (PINNED v1.x) |
| tiktoken | 0.8.0 | MIT | USA | Token counting |
| pdfplumber | 0.11.9 | MIT | USA | PDF text extraction |
| pytesseract | 0.3.13 | Apache 2.0 | USA | OCR bridge |
| python-docx | 1.2.0 | MIT | USA | Word reader |
| openpyxl | 3.1.5 | MIT | USA | Excel reader |
| pillow | 12.1.0 | HPND | USA | Image processing |
| rich | 13.9.4 | MIT | UK | Console formatting |
| tqdm | 4.67.3 | MIT | USA | Progress bars |
| keyring | 23.13.1 | MIT | USA | Credential storage |
| pytest | 9.0.2 | MIT | Germany | Testing |
| psutil | 7.2.2 | BSD-3 | USA | Process monitoring |
| All 32 V1 parsers | Various | MIT/BSD/Apache | USA/UK | Document parsing |

### 4.2 New Waivers Required (4 packages)

| Package | Version | License | Origin | Role | Waiver Risk |
|---|---|---|---|---|---|
| lancedb | 0.29.2+ | Apache 2.0 | LanceDB Inc./USA (SF) | Vector + BM25 + metadata store | LOW — already BLUE on waiver sheet |
| gliner | latest | Apache 2.0 | France (academic) | Zero-shot NER, 205M params, CPU | LOW — Apache 2.0, NATO ally |
| docling | 2.x | MIT | IBM/USA | Table extraction, 258M params | LOW — IBM is enterprise |
| flashrank | latest | Apache 2.0 | Open source | 4MB CPU reranker, sub-20ms | LOW — tiny footprint, no torch |

### 4.3 LLM Stack (Online Only)

| Backend | Model | Cost | Use Case |
|---|---|---|---|
| AI Toolbox (default) | GPT-OSS-120B | FREE | All queries, bulk enrichment fallback |
| Azure OpenAI (premium) | GPT-4o | ~$0.04/query | Complex queries, entity extraction |
| AI Toolbox (budget) | GPT-OSS-20B | FREE | CRAG verification, query routing |

### 4.4 Embedding (EmbedEngine — Separate App)

| Component | Detail |
|---|---|
| Model | nomic-embed-text v1.5 |
| Dimensions | 768 |
| Runtime | phi4:14B for enrichment + nomic for embedding, both CUDA |
| Output | Pre-built chunks + vectors + candidate_entities.jsonl |
| Schedule | Nightly |

---

## 5. What Gets Stripped from V1

| Component | Why Strip | Replacement |
|---|---|---|
| Offline LLM mode | Cross-contamination, doubles every bug | Online-only |
| Ollama dependency | Not needed without offline mode | Direct API calls |
| NetworkGate | No offline mode = no gate needed | Remove |
| 6 user modes | Config complexity | 1 mode, 2 hardware presets |
| Mode switching code | Eliminated | Single config path |
| FAISS + memmap + FTS5 | 3 systems, FTS5 bottleneck at scale | LanceDB (1 system) |
| phi4 reranker (130s) | Unusable latency | FlashRank (20ms) |
| Tkinter complexity | 80+ commits of UI debt | Carry aesthetic, simplify internals |
| Embedder in query app | Per user decision | Separate EmbedEngine repo |

---

## 6. V2 File Structure

```
HybridRAG_V2/
  src/
    __init__.py
    config/
      __init__.py
      schema.py              # Pydantic config validation (load once, immutable)
      config.yaml            # Single config, no modes
      presets/
        beast.yaml           # Beast workstation overrides
        laptop.yaml          # Laptop overrides
    ingest/
      __init__.py
      chunk_loader.py        # Read EmbedEngine output
      entity_extractor.py    # GLiNER2 first-pass + GPT-4o second-pass
      entity_normalizer.py   # Controlled vocabulary matching
      quality_gate.py        # Confidence thresholds, reject/promote
      table_extractor.py     # Docling table extraction
      indexer.py             # Orchestrate full ingest pipeline
    store/
      __init__.py
      lance_store.py         # LanceDB: vectors + BM25 + metadata
      entity_store.py        # SQLite: validated entities
      relationship_store.py  # SQLite: entity-relationship triples
      table_store.py         # SQLite: extracted table rows
    query/
      __init__.py
      router.py              # GPT-4o query classification + planning
      decomposer.py          # Sub-query generation for COMPLEX
      vector_retriever.py    # LanceDB hybrid search
      entity_retriever.py    # SQLite entity/aggregation lookup
      table_retriever.py     # SQLite table query (Text2SQL)
      reranker.py            # FlashRank reranking
      context_builder.py     # Merge, dedupe, score, assemble
      generator.py           # LLM generation + graduated confidence
    llm/
      __init__.py
      client.py              # Unified LLM client (openai SDK)
      prompts.py             # All prompt templates
    api/
      __init__.py
      server.py              # FastAPI app
      routes.py              # /query, /query/stream, /health, /audit
      models.py              # Request/response Pydantic models
    gui/
      __init__.py
      app.py                 # Main Tkinter app (carry V1 aesthetic)
      query_panel.py         # Query input + response display
      source_panel.py        # Expandable source citations
      theme.py               # Dark/light color scheme (from V1)
  tests/
    test_router.py
    test_entity_extractor.py
    test_normalizer.py
    test_quality_gate.py
    test_reranker.py
    test_context_builder.py
    test_generator.py
    golden_eval/
      eval_runner.py
      golden_queries.json
      results/
  scripts/
    setup.py                 # Python-based setup
    import_embedengine.py    # Import nightly EmbedEngine output
    audit_extraction.py      # "What did we extract?" quality report
    migrate_v1_index.py      # Import V1 FAISS/SQLite into LanceDB
  docs/
    (this document and others)
  config/
    config.yaml
  data/
    index/                   # LanceDB + SQLite stores
    source/                  # EmbedEngine output landing zone
  requirements.txt
  requirements_approved.txt
  CoPilot+.md
  README.md
```

**Design rule:** Every source file stays under 500 lines of code (comments excluded). This keeps modules reviewable by AI agents, portable, and modular. V1 followed this convention and it enabled significant code reuse — especially for parsers and embedding modules.

---

## 7. GovCloud Mapping

| V2 Local Component | GovCloud Service | Notes |
|---|---|---|
| LanceDB | OpenSearch Managed (kNN + BM25) | Same hybrid search, different backend |
| SQLite entity_store | OpenSearch doc fields or DynamoDB | Entity/relationship as documents |
| SQLite table_store | DynamoDB or OpenSearch | Extracted table rows |
| nomic-embed-text (EmbedEngine) | SageMaker Serverless endpoint | Same model |
| FastAPI | Lambda + API Gateway | Same route structure |
| GPT-OSS-120B (AI Toolbox) | AI Toolbox (same) | Already provisioned |
| Local filesystem | S3 `igs-rag-index` bucket | Already provisioned |

**Cloud cost estimate:** ~$65-90/mo (same as V1 estimate). V2 adds capability, not cost.

---

## 8. Acknowledged Tradeoffs and Justifications

### T1: Four new waivers (vs alternative proposals with zero to two)

**Justification:** V1 already proved that zero-new-dependency extraction (regex/heuristics) produces garbage. The `service_events` and `document_catalog` tables are the evidence. GLiNER2, Docling, LanceDB, and FlashRank each solve a measured failure mode:
- GLiNER2: entity extraction that regex cannot handle on 67 file formats
- Docling: 97.9% table accuracy vs pdfplumber's 32% on complex tables
- LanceDB: eliminates 12-24s FTS5 bottleneck at 27.6M chunks
- FlashRank: replaces V1's unusable 130-second reranker with 20ms

Every waiver has a fallback if denied. All are MIT/Apache 2.0, all USA or NATO allies.

### T2: Hybrid extraction (GLiNER2 + GPT-4o) is more complex than single-extractor

**Justification:** The split is clean and deliberate. GLiNER2 handles pattern-based entities (part numbers, dates, site names from file paths) — 80% of the volume, zero API cost. GPT-4o handles natural language entities (failure narratives, maintenance diary entries, relationship extraction) — 20% of the volume, ~$200 one-time. This gets GLiNER2's speed where it works and GPT-4o's comprehension where it matters.

### T3: Entity normalization requires building controlled vocabularies

**Justification:** The site list is known (25 IGS sites). Part number patterns are known (ARC-NNNN, IGSI-NNNN, PO-YYYY-NNNN). These are simple lookup tables, not ML models. The alternative — no normalization — is what V1 did, and the result is "Pre-Site Survey To Thule AB" as a site name. The vocabulary build is a one-time effort measured in hours, not weeks.

### T4: Quality gates reject some real entities (false negatives)

**Justification:** Better to miss 5% of real entities than to pollute tables with garbage like V1 did. Rejected entities go to a review queue with an audit report. The audit report is itself a deliverable — it tells the team exactly what the extraction pipeline found and what it rejected.

### T5: LanceDB is newer than FAISS at this scale

**Justification:** LanceDB is already BLUE on the waiver sheet. It uses Apache Arrow and Lance format (columnar, disk-backed). Benchmarks show 25ms vector search, 50ms with metadata filtering. Tantivy FTS handles 41M Wikipedia docs in sub-second. FAISS remains as fallback if LanceDB has issues. The migration path is documented.

### T6: Contextual enrichment on 27.6M chunks takes compute time

**Justification:** Runs on phi4:14B on the dedicated EmbedEngine GPU. Zero API cost. Incremental (only new/changed files) means minutes per nightly run. Full corpus enrichment is a one-time investment. The 67% retrieval failure reduction (published research) is the single highest-ROI improvement available.

### T7: CRAG verification adds latency

**Justification:** Adopted as a Sprint 3 quality layer, not a core architectural dependency. Adds ~300-500ms per query for verification. Retry only triggers on low-confidence responses (estimated <15% of queries). The quality improvement justifies the latency for a production demo where wrong answers are worse than slow answers.

---

## 9. Sign-Off

This design emerged from a structured competitive evaluation where six architecture proposals were tested against evidence from the production 27.6M-chunk index. The quality-gated extraction pipeline is the unique contribution — the architectural response to V1's proven extraction failure. Every other component (LanceDB, contextual enrichment, FlashRank, query routing) draws on the strongest ideas from the full review process.

The design is ambitious but the build order is incremental. Every sprint produces a working system. The architecture serves the demo first and scales to production second.

Jeremy Randall | HybridRAG_V2 | 2026-04-04 MDT
