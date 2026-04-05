# AWS GovCloud Enrichment Concept — Zero-Cost Processing Pipeline

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Status:** Concept — sample testing required before committing

---

## Concept

Leverage AWS GovCloud AI Toolkit's free GPT-OSS models (20B and 120B) for the computationally expensive enrichment and entity extraction steps. Embed locally on Beast with CUDA for free. Total processing cost: $0.

---

## Architecture

```
LOCAL (Beast)                    AWS GOVCLOUD
=============                    ============

Raw chunks                       S3 Bucket
(Clone1 index or                     |
 CorpusForge output)                 v
     |                         GPT-OSS-20B / 120B
     |--- upload to S3 --->    (OpenAI-compatible API)
                                     |
                                Enrichment:
                                 - Context preambles
                                 - Document summaries
                                 - Entity extraction
                                 - Relationship mapping
                                     |
     |<-- download results ---  enriched_chunks.jsonl
     |                          entities.json
     v
Embed locally
(nomic-embed-text, CUDA, GPU)
60-200 chunks/sec
     |
     v
Import into LanceDB + SQLite
     |
     v
Ready for queries
```

---

## Why This Works

1. **GPT-OSS models are free** through the AWS GovCloud AI Toolkit (Service Catalog provisioned)
2. **GPT-OSS API is OpenAI-compatible** — existing extraction and enrichment code works with an endpoint swap
3. **Embedding must be local** — nomic-embed-text runs on GPU, not available as a cloud API. But embedding is the fastest step (60-200 chunks/sec on a 3090), so this is not a bottleneck
4. **S3 is the natural staging area** — upload chunks, process, download results
5. **No code rewrite needed** — just configuration changes (API endpoint + model name)

---

## What GPT-OSS Processes Per Chunk

Single API call per chunk returns:

```json
{
  "context_preamble": "This excerpt from a Thule Air Base maintenance report...",
  "entities": [
    {"entity_type": "PERSON", "text": "SSgt Marcus Webb", "confidence": 0.95},
    {"entity_type": "SITE", "text": "Thule Air Base", "confidence": 0.98},
    {"entity_type": "PART", "text": "ARC-4471", "confidence": 0.97}
  ],
  "relationships": [
    {"subject": "SSgt Webb", "predicate": "REPLACED_AT", "object": "Thule Air Base"}
  ]
}
```

This combines enrichment (Stage 1 context preambles) and extraction (Stage 3 entities) into one call — halving the number of API calls.

---

## Cost Comparison

| Method | Enrichment | Extraction | Embedding | Total |
|--------|-----------|------------|-----------|-------|
| **AWS GovCloud OSS** | $0 (GPT-OSS free) | $0 (GPT-OSS free) | $0 (local CUDA) | **$0** |
| Local phi4 (Beast) | $0 (electricity only) | $0 (electricity only) | $0 (local CUDA) | ~$75 electricity |
| GPT-4.1 Nano batch | N/A | ~$10-30 | $0 (local CUDA) | $10-30 |
| GPT-4o-mini batch | N/A | ~$50-100 | $0 (local CUDA) | $50-100 |

---

## Constraints

1. **AWS OSS endpoints are internal to AWS** — processing script must run inside AWS (EC2, Lambda, or SageMaker). Cannot call OSS from outside AWS.
2. **OSS access is temporarily free** — AI Toolkit models are free for now but will be charged at some point. Process as much as possible while the meter is off. Enrichment + extraction is a one-time job — once done, the index is permanent and doesn't need OSS again.
3. **S3 upload/download** — requires data transfer between local machine and AWS. On government network this is fast. From home it depends on bandwidth.
4. **Model availability** — GPT-OSS-20B and GPT-OSS-120B are provisioned through Service Catalog. Availability and rate limits TBD through testing.
5. **Data sensitivity** — source chunks may contain controlled information. S3 bucket must be in the correct GovCloud region with appropriate access controls.

---

## Testing Plan

### Sample Test 1: Feasibility (10 chunks)
- Upload 10 diverse chunks to S3
- Call GPT-OSS-20B with enrichment + extraction prompt
- Verify: JSON output valid, entities reasonable, preambles coherent
- Measure: latency per chunk, tokens consumed

### Sample Test 2: Quality Comparison (50 chunks)
- Same 50 chunks used in the phi4 vs GPT-4o A/B test
- Run through GPT-OSS-20B and GPT-OSS-120B
- Compare entity quality against phi4 and GPT-4o baselines
- Decision: which OSS model for production?

### Sample Test 3: Scale (500 chunks)
- Test throughput and rate limits
- Measure: chunks/min sustainable, any throttling
- Test combined enrichment + extraction in single call
- Validate S3 round-trip workflow end to end

### Sample Test 4: Integration (500 chunks end-to-end)
- Upload raw chunks to S3
- Process through GPT-OSS
- Download enriched chunks + entities
- Embed locally on Beast
- Import into LanceDB + SQLite
- Run queries against the imported data
- Verify: answers reference enriched context, entities searchable

---

## Configuration Changes Required

### CorpusForge enricher (endpoint swap)
```yaml
# config/config.yaml
enrich:
  enabled: true
  ollama_url: "https://<govcloud-oss-endpoint>/v1"   # swap from localhost:11434
  model: "gpt-oss-20b"                                # swap from phi4:14b-q4_K_M
```

### V2 entity extractor (endpoint swap)
```yaml
# config/config.yaml
extraction:
  model: "gpt-oss-20b"    # or gpt-oss-120b
llm:
  api_base: "https://<govcloud-oss-endpoint>"
  provider: "openai"       # OSS uses OpenAI-compatible API
```

No code changes — just configuration. Both enricher and extractor already use OpenAI-compatible client libraries.

---

## Mix-and-Match Capability

LanceDB and SQLite are append-friendly. Multiple sources can feed into the same index:

```
Source 1: Clone1 chunks enriched via AWS OSS   → import into V2
Source 2: New files processed by CorpusForge   → import into same V2
Source 3: Additional files later                → import into same V2
```

Dedup by chunk_id at insert time prevents duplicates. The index grows incrementally. Queries automatically search across all imported data regardless of source.

---

## Decision Criteria

Proceed to production if sample tests show:
- GPT-OSS-20B entity quality >= 80% of GPT-4o baseline
- JSON compliance rate >= 90%
- Sustainable throughput (no aggressive throttling)
- S3 round-trip adds < 30% overhead vs direct processing
- Combined enrichment + extraction in single call works reliably

If GPT-OSS-20B quality is insufficient, test GPT-OSS-120B (larger model, likely higher quality, same $0 cost).

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
