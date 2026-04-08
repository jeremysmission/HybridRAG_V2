# Tuning Research — Entity Extraction, Chunk Enrichment, Retrieval Pipeline

**Date:** 2026-04-08 MDT
**Author:** Jeremy Randall (CoPilot+)
**Purpose:** Industry best practices research to inform V2 tuning scripts

---

## 1. Chunk Enrichment Tuning

### Anthropic Contextual Retrieval (Gold Standard)

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

**Source:** Anthropic Contextual Retrieval, MDKeyChunker (arXiv 2603.23533), COLING 2025 RAG best practices, Chroma chunking research

---

## 2. Entity Extraction Tuning

*(Research pending — section will be populated when findings arrive)*

### Expected Tuning Dimensions

| Parameter | Range | How to Measure |
|-----------|-------|---------------|
| GLiNER confidence threshold | 0.3 - 0.9 | Precision/recall on annotated sample |
| Entity type whitelist | Domain-specific types | Coverage vs noise ratio |
| phi4 extraction prompt | Variants | Entity count, type diversity, hallucination rate |
| Post-extraction dedup | Exact, fuzzy, canonical | Unique entity count |

---

## 3. Retrieval Pipeline Tuning

*(Research pending — section will be populated when findings arrive)*

### Expected Tuning Dimensions

| Parameter | Current V2 | Range to Sweep |
|-----------|-----------|---------------|
| top_k | 10 | 5, 10, 15, 20 |
| candidate_pool | 30 | 20, 30, 50, 100 |
| reranker_top_n | 30 | 10, 20, 30, 50 |
| hybrid alpha (vector:BM25) | default | 0.3, 0.5, 0.7, 0.9 |
| nprobes (IVF_PQ) | 20 | 10, 20, 40, 80 |
| temperature (generation) | 0.08 | 0.01, 0.05, 0.08, 0.12, 0.20 |

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

## 5. Implementation Priority

1. **tune_retrieval.py** — highest ROI, fastest to build from V1 pattern
2. **tune_generation.py** — direct port of V1 generation_autotune_live.py
3. **tune_enrichment.py** — new, needs A/B framework for enriched vs baseline
4. **tune_extraction.py** — new, needs annotated entity sample for scoring

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
