# HybridRAG V2 — Architecture Pseudocode & Block Diagram

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-04 MDT
**Design Rule:** All classes < 500 lines of code (comments excluded)

---

## 1. System Block Diagram

```
 NIGHTLY (EmbedEngine - separate app)          DAYTIME (HybridRAG V2 - this repo)
 ====================================          =====================================

 +------------+     +----------------+         +----------------------------------+
 | Downloader |---->| EmbedEngine    |         |          USER INTERFACE           |
 | (updates)  |     |                |         |  Tkinter GUI  |  FastAPI /query   |
 +------------+     | 1. Hash+Dedup  |         +-------+----------+---------------+
                    | 2. Parse (32   |                  |          |
                    |    formats)    |                  v          v
                    | 3. Chunk       |         +----------------------------------+
                    |    (1200/200)  |         |        QUERY ROUTER               |
                    | 4. Enrich      |         |        (GPT-4o classify)          |
                    |    (phi4:14B)  |         |                                   |
                    | 5. Embed       |         |  SEMANTIC | ENTITY | AGGREGATE   |
                    |    (nomic 768) |         |  TABULAR  | COMPLEX              |
                    | 6. GLiNER2 NER |         +-----+--------+--------+----------+
                    |    (first-pass)|               |        |        |
                    +-------+--------+               v        v        v
                            |              +---------+--+ +---+----+ +-+----------+
                            |              | STORE 1    | | STORE 2| | STORE 3    |
                            v              | LanceDB    | | SQLite | | SQLite     |
                    +----------------+     | vector+BM25| | entity | | relations  |
                    | Export Package |     | +FlashRank | | +tables| | (triples)  |
                    |                |     +-----+------+ +---+----+ +-----+------+
                    | chunks.jsonl   |           |            |            |
                    | vectors.lance  |           v            v            v
                    | entities.jsonl |     +----------------------------------+
                    | manifest.json  |     |        CONTEXT BUILDER            |
                    +-------+--------+     |  merge + dedupe + quality weight  |
                            |              |  parent chunk expansion           |
                            |              |  top 15-25 chunks + SQL results   |
                            v              +---------------+------------------+
                    +----------------+                     |
                    | V2 IMPORT      |                     v
                    |                |     +----------------------------------+
                    | 1. Load LanceDB|     |        GENERATOR (GPT-4o)         |
                    | 2. GPT-4o 2nd  |     |  graduated confidence:            |
                    |    pass extract|     |  HIGH | PARTIAL | NOT_FOUND       |
                    | 3. Validate    |     |  + citations + structured data    |
                    | 4. Normalize   |     +----------------------------------+
                    | 5. Promote     |                     |
                    | 6. Docling     |                     v
                    |    tables      |     +----------------------------------+
                    +----------------+     |  RESPONSE (streaming)             |
                                          |  { answer, sources[], confidence, |
                                          |    query_path, latency_ms,        |
                                          |    structured_data{} }            |
                                          +----------------------------------+
```

---

## 2. Module Pseudocode

### 2.1 Config Schema (`src/config/schema.py`)

```python
class V2Config(BaseModel):
    """Single config, no modes. Validated once at boot, immutable after."""

    class Retrieval(BaseModel):
        top_k: int = 10               # chunks to return to LLM
        candidate_pool: int = 30      # chunks to retrieve before reranking
        min_score: float = 0.1
        reranker_enabled: bool = True
        reranker_top_n: int = 30

    class LLM(BaseModel):
        model: str = "gpt-4o"
        deployment: str = "gpt-4o"
        context_window: int = 128000
        max_tokens: int = 16384
        temperature: float = 0.08
        timeout_seconds: int = 180

    class Paths(BaseModel):
        lance_db: Path               # LanceDB directory
        entity_db: Path              # SQLite entity/relationship store
        embedengine_output: Path     # Where EmbedEngine drops nightly exports

    class ExtractionQuality(BaseModel):
        min_confidence: float = 0.7
        site_vocabulary_path: Path
        part_patterns: list[str] = ["ARC-\\d{4}", "IGSI-\\d+", "PO-\\d{4}-\\d{4}"]

    retrieval: Retrieval
    llm: LLM
    paths: Paths
    extraction: ExtractionQuality
    hardware_preset: str = "beast"   # "beast" or "laptop"
```

### 2.2 LanceDB Store (`src/store/lance_store.py`)

```python
class LanceStore:
    """Vector + BM25 + metadata search via LanceDB. Single store replaces FAISS + FTS5 + memmap."""

    def __init__(self, db_path: str):
        self.db = lancedb.connect(db_path)
        self.table = self.db.open_table("chunks")

    def hybrid_search(self, query_vector: list[float], query_text: str,
                      top_k: int = 30, filters: dict = None) -> list[ChunkResult]:
        """Run vector kNN + BM25 full-text + optional metadata filter. Returns fused results."""
        search = self.table.search(query_vector, query_type="hybrid")
        if query_text:
            search = search.text(query_text)
        if filters:
            search = search.where(build_filter_expr(filters))
        results = search.limit(top_k).to_list()
        return [ChunkResult(id=r["chunk_id"], text=r["text"], score=r["_score"],
                            source_path=r["source_path"], enriched_text=r["enriched_text"])
                for r in results]

    def ingest_chunks(self, chunks: list[dict]):
        """Bulk insert chunks with vectors, text, metadata, enriched_text."""
        self.table.add(chunks)

    def count(self) -> int:
        return len(self.table)
```

### 2.3 Entity Store (`src/store/entity_store.py`)

```python
class EntityStore:
    """SQLite store for validated, normalized entities and extracted table rows."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY,
        entity_text TEXT NOT NULL,          -- normalized: "Thule" not "Pre-Site Survey Thule AB"
        entity_type TEXT NOT NULL,          -- PART_NUMBER, PERSON, SITE, DATE, ORG, FAILURE_MODE
        raw_text TEXT,                      -- original extracted text before normalization
        confidence REAL NOT NULL,           -- extraction confidence 0.0-1.0
        chunk_id TEXT NOT NULL,
        source_path TEXT NOT NULL,
        extractor TEXT NOT NULL,            -- "gliner" or "gpt4o"
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS extracted_tables (
        id INTEGER PRIMARY KEY,
        source_path TEXT NOT NULL,
        sheet_name TEXT,
        headers TEXT NOT NULL,              -- JSON array of column headers
        row_data TEXT NOT NULL,             -- JSON object of {column: value}
        row_index INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_entity_text ON entities(entity_text);
    CREATE INDEX IF NOT EXISTS idx_entity_type ON entities(entity_type);
    """

    def lookup_entity(self, entity_type: str, query: str) -> list[dict]:
        """Direct entity lookup. For ENTITY_LOOKUP queries."""
        return self.conn.execute(
            "SELECT * FROM entities WHERE entity_type = ? AND entity_text LIKE ?",
            (entity_type, f"%{query}%")
        ).fetchall()

    def aggregate(self, sql: str) -> list[dict]:
        """Execute validated SQL for AGGREGATION queries. SQL generated by GPT-4o."""
        # Safety: only SELECT allowed, no mutations
        if not sql.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries allowed")
        return self.conn.execute(sql).fetchall()
```

### 2.4 Relationship Store (`src/store/relationship_store.py`)

```python
class RelationshipStore:
    """SQLite store for entity-relationship triples. Enables multi-hop queries via JOINs."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS relationships (
        id INTEGER PRIMARY KEY,
        subject_text TEXT NOT NULL,         -- "SSgt Marcus Webb"
        subject_type TEXT NOT NULL,         -- PERSON
        predicate TEXT NOT NULL,            -- "is_poc_for"
        object_text TEXT NOT NULL,          -- "Thule"
        object_type TEXT NOT NULL,          -- SITE
        confidence REAL NOT NULL,
        chunk_id TEXT NOT NULL,
        source_path TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_rel_predicate ON relationships(predicate);
    CREATE INDEX IF NOT EXISTS idx_rel_subject ON relationships(subject_text);
    CREATE INDEX IF NOT EXISTS idx_rel_object ON relationships(object_text);
    """

    def find_relationships(self, entity: str, predicate: str = None) -> list[dict]:
        """Find relationships involving an entity. For ENTITY and multi-hop queries."""
        if predicate:
            return self.conn.execute(
                "SELECT * FROM relationships WHERE (subject_text LIKE ? OR object_text LIKE ?) AND predicate = ?",
                (f"%{entity}%", f"%{entity}%", predicate)
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM relationships WHERE subject_text LIKE ? OR object_text LIKE ?",
            (f"%{entity}%", f"%{entity}%")
        ).fetchall()
```

### 2.5 Entity Extractor (`src/ingest/entity_extractor.py`)

```python
class EntityExtractor:
    """Hybrid extraction: GLiNER2 for structural entities, GPT-4o for semantic entities."""

    def __init__(self, config: V2Config):
        self.gliner_model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
        self.llm_client = LLMClient(config.llm)
        self.entity_labels = ["PART_NUMBER", "PERSON", "SITE", "DATE",
                              "ORGANIZATION", "FAILURE_MODE", "ACTION"]

    def extract_structural(self, chunk_text: str) -> list[RawEntity]:
        """First-pass: GLiNER2 zero-shot NER. Handles 80% of entities. Free, fast, CPU."""
        entities = self.gliner_model.predict_entities(chunk_text, self.entity_labels)
        return [RawEntity(text=e["text"], type=e["label"],
                          confidence=e["score"], extractor="gliner")
                for e in entities]

    def extract_semantic(self, chunk_text: str, source_path: str) -> list[RawEntity]:
        """Second-pass: GPT-4o for complex entities. Handles 20% (failure narratives, relationships)."""
        prompt = EXTRACTION_PROMPT.format(text=chunk_text, source=source_path)
        response = self.llm_client.call(prompt, response_format="json")
        return parse_gpt4o_extraction(response)

    def extract(self, chunk_text: str, source_path: str) -> list[RawEntity]:
        """Run both passes. GLiNER first (fast), GPT-4o for chunks with complex narratives."""
        entities = self.extract_structural(chunk_text)
        if needs_semantic_extraction(chunk_text, entities):
            entities.extend(self.extract_semantic(chunk_text, source_path))
        return deduplicate_entities(entities)
```

### 2.6 Quality Gate (`src/ingest/quality_gate.py`)

```python
class QualityGate:
    """Validates and filters extracted entities. Prevents V1's garbage data problem."""

    def __init__(self, config: V2Config):
        self.min_confidence = config.extraction.min_confidence  # 0.7
        self.site_vocab = load_vocabulary(config.extraction.site_vocabulary_path)
        self.part_patterns = [re.compile(p) for p in config.extraction.part_patterns]
        self.rejected = []  # for audit report

    def validate(self, entity: RawEntity) -> ValidatedEntity | None:
        """Returns validated entity or None if rejected."""
        # Confidence gate
        if entity.confidence < self.min_confidence:
            self.rejected.append((entity, "low_confidence"))
            return None

        # Type-specific validation
        if entity.type == "SITE":
            normalized = self.normalize_site(entity.text)
            if normalized is None:
                self.rejected.append((entity, "unknown_site"))
                return None
            return ValidatedEntity(**entity.dict(), normalized_text=normalized)

        if entity.type == "PART_NUMBER":
            if not any(p.match(entity.text) for p in self.part_patterns):
                self.rejected.append((entity, "invalid_part_format"))
                return None
            return ValidatedEntity(**entity.dict(), normalized_text=entity.text.upper())

        if entity.type == "PERSON":
            cleaned = self.clean_person_name(entity.text)
            return ValidatedEntity(**entity.dict(), normalized_text=cleaned)

        return ValidatedEntity(**entity.dict(), normalized_text=entity.text)

    def normalize_site(self, raw: str) -> str | None:
        """Match raw text against controlled vocabulary of 25 IGS sites."""
        raw_lower = raw.lower()
        for canonical, aliases in self.site_vocab.items():
            if any(alias in raw_lower for alias in aliases):
                return canonical
        return None  # unknown site — reject

    def clean_person_name(self, raw: str) -> str:
        """Separate phone/email from name. Fix V1's 'Annette Parsons, (970) 986-2551' problem."""
        # Strip phone numbers, emails, titles from name field
        name = re.sub(r'[,;]\s*[\d(][\d\s\-()]+', '', raw)  # remove phone
        name = re.sub(r'[,;]\s*\S+@\S+', '', raw)            # remove email
        return name.strip().strip(',').strip()

    def audit_report(self) -> dict:
        """Generate extraction quality report for human review."""
        return {
            "total_extracted": self.total_processed,
            "total_accepted": self.total_accepted,
            "total_rejected": len(self.rejected),
            "rejection_reasons": Counter(r[1] for r in self.rejected),
            "acceptance_rate": self.total_accepted / max(self.total_processed, 1),
            "sample_rejections": self.rejected[:50]
        }
```

### 2.7 Entity Normalizer (`src/ingest/entity_normalizer.py`)

```python
# Site vocabulary (controlled)
SITE_VOCABULARY = {
    "Thule":       ["thule", "thule ab", "thule afb", "thule air base"],
    "Alpena":      ["alpena", "alpena crtc", "alpena combat readiness"],
    "Learmonth":   ["learmonth", "learmonth raaf"],
    "Guam":        ["guam", "andersen", "andersen afb"],
    "Ascension":   ["ascension", "ascension island"],
    "Eglin":       ["eglin", "eglin afb"],
    "San Vito":    ["san vito", "san vito dei normanni"],
    "Osan":        ["osan", "osan ab"],
    "Eielson":     ["eielson", "eielson afb", "eieslon"],  # note: V1 typo in data
    "Loring":      ["loring"],
    "Fairford":    ["fairford", "raf fairford"],
    "Wake":        ["wake", "wake island"],
    "Eareckson":   ["eareckson", "eareckson as", "shemya"],
    "Lualualei":   ["lualualei", "lll", "nrtf"],
    "Djibouti":    ["djibouti"],
    "UAE":         ["uae", "al dhafra", "al dhafra ab"],
    "Selfridge":   ["selfridge", "selfridge angb"],
    "Sagamore Hill": ["sagamore", "sagamore hill"],
    "Misawa":      ["misawa", "misawa ab"],
    "Singapore":   ["singapore"],
    "Azores":      ["azores", "lajes", "lajes field"],
    "Vandenberg":  ["vandenberg", "vafb"],
    "Kaena Point": ["kaena", "kaena point"],
    "Palehua":     ["palehua"],
    "Maui":        ["maui"],
}
```

### 2.8 Query Router (`src/query/router.py`)

```python
class QueryRouter:
    """Classifies user queries and generates retrieval plans. Single GPT-4o call."""

    ROUTER_PROMPT = """
    You are a query classifier for a technical document search system about
    military radar/ionosonde maintenance and operations (IGS/NEXION systems).

    Classify the query and generate a retrieval plan.

    QUERY TYPES:
    - SEMANTIC: Conceptual, explanatory, procedural questions
    - ENTITY_LOOKUP: Looking up a specific fact (who, what, where)
    - AGGREGATION: Counting, summarizing across multiple documents
    - TABULAR: Looking up structured data from spreadsheets/tables
    - COMPLEX: Requires multiple types combined

    OUTPUT (JSON):
    {
      "query_type": "SEMANTIC|ENTITY_LOOKUP|AGGREGATION|TABULAR|COMPLEX",
      "sub_queries": ["expanded query 1", "expanded query 2"],
      "stores_to_query": ["vector", "entity", "relationship", "table"],
      "expected_answer_type": "text|number|name|list|table",
      "synonyms": {"user_term": "domain_term"}
    }
    """

    def route(self, user_query: str) -> QueryPlan:
        response = self.llm_client.call(
            self.ROUTER_PROMPT + f"\n\nUser query: {user_query}",
            response_format="json"
        )
        return QueryPlan.parse(response)

    def execute_plan(self, plan: QueryPlan) -> list[RetrievalResult]:
        """Execute retrieval plan across stores. Parallel where possible."""
        results = []
        if "vector" in plan.stores:
            results.extend(self.vector_retriever.search(plan))
        if "entity" in plan.stores:
            results.extend(self.entity_retriever.search(plan))
        if "relationship" in plan.stores:
            results.extend(self.relationship_retriever.search(plan))
        if "table" in plan.stores:
            results.extend(self.table_retriever.search(plan))
        return results
```

### 2.9 Context Builder (`src/query/context_builder.py`)

```python
class ContextBuilder:
    """Merges results from all stores into a single context for the generator."""

    def build(self, results: list[RetrievalResult], plan: QueryPlan) -> GeneratorContext:
        # 1. Deduplicate (same chunk from vector + keyword)
        unique = deduplicate_by_chunk_id(results)

        # 2. Rerank with FlashRank
        if self.config.retrieval.reranker_enabled:
            unique = self.reranker.rerank(plan.original_query, unique,
                                          top_n=self.config.retrieval.top_k)

        # 3. Separate structured results (SQL counts, entity lookups, table rows)
        structured = [r for r in unique if r.result_type in ("sql", "entity", "table")]
        chunks = [r for r in unique if r.result_type == "chunk"]

        # 4. Parent chunk expansion (if available)
        chunks = expand_parent_chunks(chunks)

        # 5. Quality weighting (prefer higher parse-quality chunks)
        chunks = weight_by_quality(chunks)

        # 6. Assemble context string
        context = format_context(chunks[:self.config.retrieval.top_k], structured)

        return GeneratorContext(
            context_text=context,
            sources=[c.source_path for c in chunks],
            structured_results=structured,
            chunk_count=len(chunks),
            query_plan=plan
        )
```

### 2.10 Generator (`src/query/generator.py`)

```python
class Generator:
    """LLM generation with graduated confidence and citations."""

    GENERATOR_PROMPT = """
    You are a technical document assistant for IGS/NEXION military systems.
    Answer based ONLY on the provided context.

    CONFIDENCE LEVELS (required in every response):
    - HIGH: Answer is directly stated in sources. Quote relevant text.
    - PARTIAL: Some information found, gaps exist. State what you found AND what is missing.
    - NOT_FOUND: Sources do not contain this information. Say so clearly. Do NOT guess.

    RULES:
    - Every claim must cite a source [Source: filename, section]
    - Numbers must come from sources, never estimated
    - If aggregation data is provided, show the count AND list each source
    - If structured data is available, present it as a table
    - If the query path was SQL, show the query result alongside narrative explanation
    """

    def generate(self, context: GeneratorContext, user_query: str) -> QueryResponse:
        prompt = self.GENERATOR_PROMPT + f"\n\nContext:\n{context.context_text}\n\nQuestion: {user_query}"
        response = self.llm_client.call(prompt, stream=True)

        return QueryResponse(
            answer=response.text,
            sources=context.sources,
            confidence=parse_confidence(response.text),
            query_path=context.query_plan.query_type,
            structured_data=context.structured_results,
            chunks_used=context.chunk_count,
            latency_ms=elapsed
        )
```

### 2.11 V2 Import Pipeline (`scripts/import_embedengine.py`)

```python
def import_nightly(export_dir: Path, config: V2Config):
    """Import EmbedEngine nightly export into V2 stores."""

    # 1. Load chunks + vectors into LanceDB
    lance_store = LanceStore(config.paths.lance_db)
    chunks = read_jsonl(export_dir / "chunks.jsonl")
    lance_store.ingest_chunks(chunks)
    print(f"Loaded {len(chunks)} chunks into LanceDB")

    # 2. Second-pass extraction (GPT-4o on complex chunks)
    extractor = EntityExtractor(config)
    candidate_entities = read_jsonl(export_dir / "entities.jsonl")  # GLiNER first-pass
    for chunk in chunks_needing_semantic_extraction(chunks, candidate_entities):
        candidate_entities.extend(extractor.extract_semantic(chunk.text, chunk.source_path))

    # 3. Quality gate + normalization
    gate = QualityGate(config)
    validated = []
    for entity in candidate_entities:
        result = gate.validate(entity)
        if result:
            validated.append(result)

    # 4. Promote to production stores
    entity_store = EntityStore(config.paths.entity_db)
    entity_store.bulk_insert(validated)

    # 5. Docling table extraction (for spreadsheets/PDFs with tables)
    table_extractor = TableExtractor()
    for source_file in find_table_sources(chunks):
        tables = table_extractor.extract(source_file)
        entity_store.insert_tables(tables)

    # 6. Audit report
    report = gate.audit_report()
    print(f"Extraction: {report['total_accepted']}/{report['total_extracted']} accepted "
          f"({report['acceptance_rate']:.1%})")
    save_report(export_dir / "audit_report.json", report)
```

---

## 3. Data Flow Summary

```
SOURCE FILES (420K, 700GB)
         |
         | [Nightly - EmbedEngine]
         v
    Hash + Dedup (_1 suffix)
    Parse (32 formats + OCR)
    Chunk (1200 char / 200 overlap)
    Enrich (phi4:14B context prefix - FREE)
    Embed (nomic-embed-text v1.5, 768-dim)
    GLiNER2 first-pass NER
         |
         v
    EXPORT PACKAGE
    (chunks.jsonl + vectors + entities.jsonl + manifest.json)
         |
         | [On startup or triggered - V2 Import]
         v
    GPT-4o second-pass extraction (complex chunks only, ~$200)
    Quality Gate (confidence >= 0.7)
    Normalize (controlled vocabulary)
    Docling table extraction
         |
         +---> LanceDB (vectors + enriched BM25 text)
         +---> SQLite entities (validated, normalized)
         +---> SQLite relationships (entity triples)
         +---> SQLite tables (extracted spreadsheet rows)
         |
         | [Per query - Daytime]
         v
    Router (GPT-4o classify) -> Store 1/2/3
    Retrieve -> FlashRank rerank -> Context build
    Generate (GPT-4o) -> Graduated confidence
    Stream response to GUI/API
```

---

Jeremy Randall | HybridRAG_V2 | 2026-04-04 MDT
