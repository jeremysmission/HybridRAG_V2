# Tuning Research — Entity Extraction, Chunk Enrichment, Retrieval Pipeline

**Date:** 2026-04-08 MDT
**Author:** Jeremy Randall (CoPilot+)
**Purpose:** Industry best practices research to inform V2 tuning scripts

---

## 1. Chunk Enrichment Tuning

### approved vendor Contextual Retrieval (Gold Standard)

For every chunk, pass the full source document + chunk to an LLM and generate a 50-100 token "situating context" prepended to the chunk before embedding.

**Canonical prompt:**
```
<document> {{WHOLE_DOCUMENT}} </document>
Here is the chunk we want to situate within the whole document
<chunk> {{CHUNK_CONTENT}} </chunk>
Please give a short succinct context to situate this chunk within the overall
document for the purposes of improving search retrieval of the chunk.
Answer only with the succinct context and nothing else.
```

**Results:**
- 35% reduction in top-20 retrieval failure rate (enrichment alone)
- 67% reduction combined with reranking
- Cost: ~$1.02/M document tokens (prompt caching cuts this significantly)

**V2 status:** We already use phi4:14b preambles — this IS contextual retrieval. The tuning opportunity is prompt variant A/B testing.

### Enrichment Prompt Tuning Parameters

| Parameter | Recommended | Why |
|-----------|------------|-----|
| Temperature | 0.0-0.3 | Deterministic, factual context — not creative |
| Output length | 50-100 tokens | Longer enrichment dilutes embedding signal |
| Prompt style | "Answer only with the succinct context" | Prevents filler/preamble |
| Purpose framing | "for improving search retrieval" | Orients toward searchable terms |

### What to A/B Test

1. **Keywords vs summaries vs questions-the-chunk-answers** — each helps different retrieval modes
2. **BM25 enrichment vs dense enrichment** — what helps keyword search may differ from vector search
3. **With vs without entity mentions** — adding extracted entities to enrichment may help entity queries
4. **Heading breadcrumb** — "Chapter 3 > Section 3.2 > Maintenance Procedure" path

### Chunking Parameter Baseline

| Parameter | Default | Range to Sweep |
|-----------|---------|---------------|
| Chunk size | 256-512 tokens | 128, 256, 512, 1024 |
| Overlap | 10-20% | 0%, 10%, 20%, 30% |
| Strategy | Semantic (heading-aware) | Fixed, semantic, proposition |

**Key finding:** Chunking strategy choice has impact comparable to or greater than embedding model choice. Always test chunking changes with model-swap rigor.

### Impact Hierarchy (research-validated)

1. Chunking strategy (semantic vs fixed) — largest impact
2. Contextual enrichment (prepended context) — second largest
3. Chunk size tuning — significant but query-type dependent
4. Overlap tuning — diminishing returns beyond 20%
5. Reranking on enriched retrieval — final 15-20%

**Source:** approved vendor Contextual Retrieval, MDKeyChunker (arXiv 2603.23533), COLING 2025 RAG best practices, Chroma chunking research

### V2 Reranker Finding (Measured 2026-04-08)

**The reranker provides zero accuracy improvement on the current V2 corpus.**

| Config | Accuracy | P50 | P95 | Avg |
|--------|----------|-----|-----|-----|
| WITH reranker | 25/25 | 22ms | 56ms | 34ms |
| NO reranker | 25/25 | 19ms | 57ms | 25ms |

**Why:** With the entity store handling 60% of queries (ENTITY/AGGREGATE/TABULAR) via direct lookup, only SEMANTIC queries (40%) even reach the reranker. On a 17K-chunk corpus with a strong embedding model (nomic 768d), the vector top-10 are already well-ranked.

**V1 lesson:** Reranker was prohibitively slow on V1 and was disabled. V2 FlashRank is fast (~9ms overhead) but still provides no accuracy gain at current scale.

**Recommendation:** Keep reranker config toggle (`reranker_enabled: true/false`) for future scale. At 100K+ chunks, reranker value increases as vector top-10 quality degrades. For demo, reranker can be disabled for faster queries.

---

## 2. Entity Extraction Tuning

### GLiNER Confidence Threshold Selection

| Use Case | Threshold | Trade-off |
|----------|-----------|-----------|
| High recall (capture everything) | 0.2-0.3 | More false positives |
| Balanced (production default) | 0.3-0.5 | Good starting point |
| High precision (fewer errors) | 0.5-0.6 | Misses some entities |
| Relation extraction | 0.7-0.9 | For GLiNER-relex models |

**V2 current setting:** `min_confidence: 0.7` in config. Research suggests this may be too aggressive -- consider lowering to 0.5 for entity extraction, keep 0.7 for relationship extraction.

### How to Find YOUR Threshold (Without Ground Truth)

1. **Sweep and plot:** Run GLiNER at thresholds 0.1-0.7 in 0.05 steps on 200 chunks. Plot entity count vs threshold -- look for the "elbow" where noise falls off
2. **Silver labels:** Run GPT-4o on 300 representative chunks to extract entities (~$2-5 cost). Use as pseudo ground truth to compute precision/recall at each threshold
3. **Cross-model agreement:** Run both GLiNER and phi4 on same chunks. Entities found by both at high confidence = likely correct. Disagreements = manual review candidates
4. **Confidence distribution:** Plot histogram of scores. Bimodal = model is discriminating well (threshold at valley). Flat = model uncertain (consider fine-tuning)

### Per-Entity-Type Thresholds

Different entity types have different confidence profiles. Set separate thresholds:

| Entity Type | Suggested Threshold | Rationale |
|-------------|-------------------|-----------|
| PART (part numbers) | 0.4 | Pattern-based, high-signal tokens |
| PERSON | 0.5 | Named entities usually high-confidence |
| SITE | 0.4 | Known vocabulary, pattern-matchable |
| DATE | 0.3 | Low noise, high recall needed |
| PO | 0.3 | Pattern-based (PO-XXXX-XXXX) |
| ORG | 0.5 | More ambiguous, need higher threshold |
| CONTACT | 0.3 | Email/phone patterns, low noise |

### Evaluation Metrics for Entity Extraction

| Metric | What It Tells You | Tool |
|--------|------------------|------|
| Entity Precision | % extracted entities that are correct | nervaluate, manual sample |
| Entity Recall | % true entities found | Requires reference set |
| Span-level F1 | Combined P/R at entity boundaries | nervaluate or seqeval |
| Entity Type Accuracy | % assigned correct type | Confusion matrix |
| Entity Density | Entities per chunk (sanity) | count / chunk_count |
| Cross-chunk Consistency | Same entity recognized across chunks | Dedup ratio |
| Orphan Node % | Entities with no relationships | KG stats |

**Critical:** Use span-level evaluation (nervaluate), not token-level F1. Token-level penalizes partial boundary matches twice.

### Batch Processing Notes

- Split long documents into ~160-word chunks for GLiNER
- Batch in groups of 8 for `batch_predict_entities`
- The bi-encoder variant (`knowledgator/gliner-bi-large-v2.0`) offers up to 130x throughput by pre-computing entity embeddings once
- `flat_ner=True` selects only non-overlapping spans (highest score wins)

### Fine-Tuning (If Zero-Shot Insufficient)

- Synthetic data: GLiNER's `synthetic_data_generation.ipynb` generates training data via GPT for custom entity types
- Dataset size: ~5K-50K annotated examples
- Fine-tuned GLiNER on cybersecurity data: P=89.7%, R=74.3%, F1=80.5% (beat GPT zero-shot)
- Runs on consumer hardware (no high-end GPU required for base model)

**Source:** GLiNER NAACL 2024, knowledgator gliner-bi-large-v2.0, nervaluate, seqeval, RAGAS entity_recall metric

---

## 3. Retrieval Pipeline Tuning

### What to Sweep and How to Score

**Retrieve broadly, rerank precisely:** The proven pattern is top-50 to top-100 candidates from retrieval, reranked down to top-3 to top-5 for the LLM. A three-stage pipeline (BM25 + dense + rerank) shows 48% improvement over single-method retrieval.

**Key finding:** Chunking config has as much influence on retrieval quality as embedding model choice (Vectara, NAACL 2025) -- a 9% recall gap between best and worst chunking on the same corpus.

### Retrieval Parameter Grid

| Parameter | Current V2 | Range to Sweep | Notes |
|-----------|-----------|---------------|-------|
| top_k (final) | 10 | 3, 5, 8, 10, 15, 20 | What LLM sees |
| candidate_pool | 30 | 20, 30, 50, 100 | What retriever returns pre-rerank |
| nprobes (IVF_PQ) | 20 | 10, 20, 40, 80 | More probes = better recall, slower |
| hybrid alpha | default (RRF) | 0.0 (BM25) to 1.0 (vector) in 0.1 | Convex combination outperforms RRF when tuned |
| reranker on/off | enabled | True, False | V2 measured: zero accuracy gain at 17K chunks |

### Reranker Tiers

| Reranker | Latency | Best For |
|----------|---------|----------|
| FlashRank (MiniLM) | <20ms for 50 candidates (CPU) | Tight latency budget |
| Cross-encoder (Cohere, Voyage) | ~150ms for 100 docs | Max accuracy with GPU |
| ColBERT (late interaction) | 180x fewer FLOPs than BERT at k=10 | Large candidate pools |

**V2 status:** Using FlashRank MiniLM-L-12-v2. Measured zero accuracy gain on 17K corpus. Keep toggle for scale.

### Hybrid Search Weight (Alpha)

`score(d) = alpha * dense(d) + (1-alpha) * BM25(d)`

- **Default:** Start with RRF (Reciprocal Rank Fusion) at k=60
- **With 50+ labeled queries:** Grid-search alpha in 0.1 steps. Convex combination outperforms RRF when alpha is tuned (Bruch et al., ACM TOIS 2023)
- **Cutting edge:** DAT (Dynamic Alpha Tuning, arxiv 2503.23013) uses LLM to dynamically calibrate alpha per query type

### Generation-Side Tuning

| Parameter | Recommended | Range |
|-----------|------------|-------|
| Temperature | 0.0-0.1 for factual RAG | 0.01, 0.05, 0.08, 0.12 |
| System prompt | "Answer only from provided context" | Variants |
| Context window | 256-512 token chunks, k=5 for <50K chunks | k=3,5,8,10 |
| Presence penalty | 0.0 | 0.0, 0.1, 0.2 |

**"Lost in the Middle" caveat:** LLMs attend poorly to middle chunks. Keep k small and chunks well-ranked.

### Evaluation Frameworks

| Framework | Strengths | Metrics |
|-----------|----------|---------|
| RAGAS | Lightweight, research-backed | Faithfulness, ContextRecall, AnswerRelevancy |
| DeepEval | pytest-style, 14+ metrics | ContextualPrecision, debuggable LLM judge |
| Custom graders | Domain-specific, deterministic | Fact-hit rate, keyword presence |

**Most important metrics (in order):**
1. Faithfulness -- answers grounded in retrieved context? (catches hallucinations)
2. Context Recall -- did retrieval find the right chunks?
3. Answer Relevance -- does response answer the question?
4. Context Precision -- is retrieved context noise-free?

### The Autotune Pattern (LlamaIndex ParamTuner)

1. Build 50-100 golden Q&A pairs (we have 30 + 400-Q tuning corpus)
2. Define scoring function (fact-hit rate + latency + cost)
3. Grid search: chunk_size x top_k x alpha x reranker
4. Score each combination
5. Pick Pareto-optimal (best score within latency budget)

**Source:** Pinecone rerankers guide, DAT (arxiv 2503.23013), Bruch et al. ACM TOIS 2023, Vectara NAACL 2025, LlamaIndex ParamTuner, RAGAS, DeepEval

---

## 4. V2 Tuning Script Architecture

### Repurpose from V1

The V1 `generation_autotune_live.py` provides a proven sweep pattern:

```
for bundle in BUNDLES:
    apply_settings(config, bundle)
    for query in golden_subset:
        result = pipeline.query(query)
        score = fact_hit_rate(result, expected_facts)
    rank_bundle(bundle, scores)
report_leaderboard()
```

### V2 Sweep Scripts Needed

| Script | Sweeps | Scores Against |
|--------|--------|---------------|
| `tune_retrieval.py` | top_k, candidate_pool, hybrid alpha, nprobes | 30 golden queries (retrieval fact-hit) |
| `tune_generation.py` | temperature, top_p, max_tokens, system prompt | 30 golden queries (generation fact-hit + faithfulness) |
| `tune_enrichment.py` | enrichment prompt variants, temperature | A/B retrieval recall on enriched vs baseline chunks |
| `tune_extraction.py` | confidence threshold, entity types, prompt | Precision/recall on annotated entity sample |

### Scoring Dimensions (per industry standard)

| Dimension | Metric | Tool |
|-----------|--------|------|
| Factual correctness | Fact-hit rate (substring match) | Built-in |
| Retrieval quality | Recall@k, MRR, NDCG@10 | Custom grader |
| Context use | Did answer cite retrieved chunks? | LLM-as-judge |
| Consistency | Variance across 3 runs | Built-in |
| Latency | P50, P95 | Built-in |
| Cost | Tokens x price | Built-in |
| Safety | No prompt leakage, no hallucinated PII | Adversarial queries |

---

## 5. Stress Test Corpus Design

The current golden eval (30 queries) is mostly "happy path." A reranker stress test needs 100 hard queries that expose ranking quality differences:

### Proposed Stress Test Categories

| Category | Count | Purpose | Reranker Expected Impact |
|----------|-------|---------|------------------------|
| Multi-hop aggregation | 20 | "List all parts across all sites" | HIGH -- needs broad retrieval + precise ranking |
| Relationship chain | 15 | "Who ordered the part for the site where X failed?" | HIGH -- multi-doc evidence assembly |
| Canary/injection | 15 | SQL injection, prompt injection, jailbreak | LOW -- should be filtered regardless |
| Trick questions | 10 | "What color is the radar?" (unanswerable) | MEDIUM -- reranker should rank irrelevant chunks low |
| Near-miss ambiguity | 15 | "Torres" vs "Torres field report" vs "Torres email" | HIGH -- disambiguation needs precise ranking |
| Noisy source | 10 | Queries against OCR garbage, email chain fragments | HIGH -- reranker filters noise from signal |
| Cross-format | 15 | Facts split across PDF + XLSX + TXT | MEDIUM -- format-aware ranking |

### Scoring Protocol

Run all 100 queries with and without reranker at each candidate_pool size (20, 50, 100):
- **Hypothesis:** Reranker value increases with candidate_pool size and query difficulty
- **If reranker helps on hard queries:** Keep enabled, consider per-query-type toggle
- **If reranker doesn't help on hard queries either:** Remove from pipeline entirely

### Source: V1 400-Q Corpus

The existing 400-question tuning corpus already has 41 injection queries, 59 unanswerable, and 22 ambiguous -- we can extract those plus add domain-specific multi-hop questions.

---

## 6. Implementation Priority

1. **tune_retrieval.py** -- DONE (committed). Overnight sweep, reranker on/off, leaderboard
2. **Stress test corpus** -- Build 100-question hard corpus from V1 400-Q + new multi-hop queries
3. **tune_generation.py** -- Port V1 generation_autotune_live.py to V2 pipeline
4. **tune_enrichment.py** -- A/B framework for enriched vs baseline chunks
5. **tune_extraction.py** -- GLiNER threshold sweep with silver labels from GPT-4o

---

## Citations

### Chunk Enrichment
- approved vendor. "Introducing Contextual Retrieval." approved vendor.com/news/contextual-retrieval (2024)
- approved vendor Cookbook. "Contextual Embeddings Guide." platform.CoPilot+.com/cookbook
- MDKeyChunker. arXiv:2603.23533 (March 2026)
- COLING 2025. "Enhancing RAG: A Study of Best Practices." arXiv:2501.07391
- Chroma Research. "Evaluating Chunking Strategies." research.trychroma.com
- Vectara NAACL 2025. Chunking configuration impact study
- NVIDIA. "Finding the Best Chunking Strategy." developer.nvidia.com/blog
- Weaviate. "Chunking Strategies for RAG." weaviate.io/blog
- PMC. "Clinical Decision Support Chunking Evaluation." PMC12649634
- arXiv. "Evaluating Advanced Chunking for RAG." arXiv:2504.19754 (April 2025)

### Entity Extraction
- GLiNER. NAACL 2024. aclanthology.org/2024.naacl-long.300
- GLiNER GitHub. github.com/urchade/GLiNER
- knowledgator/gliner-bi-large-v2.0. huggingface.co
- knowledgator/gliner-relex-large-v1.0. huggingface.co
- nervaluate. "Entity-Level NER Evaluation." github.com/MantisAI/nervaluate
- seqeval. "Sequence Labeling Evaluation." github.com/chakki-works/seqeval
- RAGAS. "Automated Evaluation of RAG." arXiv:2309.15217
- Conformal Prediction for NER. arXiv:2601.16999 (2025)
- Weak Supervision for NER. ACL 2020. aclanthology.org/2020.acl-main.139

### Retrieval Pipeline
- Pinecone. "Rerankers and Two-Stage Retrieval." pinecone.io/learn/series/rag/rerankers
- DAT: Dynamic Alpha Tuning. arXiv:2503.23013 (March 2025)
- Bruch et al. ACM TOIS 2023. Convex combination vs RRF for hybrid search
- LlamaIndex. "Hyperparameter Optimization for RAG." docs.llamaindex.ai
- FlashRank + Query Expansion. arXiv:2601.03258 (2026)
- ICLR 2025. "Long-Context LLMs Meet RAG." proceedings.iclr.cc
- DeepEval. "RAG Evaluation Guide." deepeval.com/guides
- RAGAS Documentation. docs.ragas.io
- Google Cloud. "Optimizing RAG Retrieval." cloud.google.com/blog

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
