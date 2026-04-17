# Token Pricing Reference — 2026-04-05

**See also:** `docs/token_pricing_reference_2026-04-05.jpg` (screenshot of model pricing chart)

## Budget Constraint

- Under $50: no issues
- $50-100: needs justification
- Over $100: problematic

## OpenAI Models (per 1M tokens)

| Model | Input | Output | Batch Input | Batch Output |
|-------|-------|--------|-------------|--------------|
| GPT-4o | $2.50 | $10.00 | $1.25 | $5.00 |
| GPT-4o-mini | $0.15 | $0.60 | $0.075 | $0.30 |
| GPT-4.1 Nano | $0.10 | $0.40 | $0.05 | $0.20 |
| o3-mini | $1.10 | $4.40 | $0.55 | $2.20 |

*Batch API = 50% discount. Prompt caching = additional 90% off cached tokens.*

## Azure Enterprise (work pricing — quoted by user)

| Model | Input | Output |
|-------|-------|--------|
| GPT-4o | $6.25/1M | ? |
| GPT-4o-mini | $0.207/1M | ? |

*Azure pricing may differ from commercial OpenAI.*

## Local Models (Ollama, $0 API cost)

| Model | Size | VRAM | Speed (3090) | Cost |
|-------|------|------|-------------|------|
| phi4:14b-q4_K_M | 9.1 GB | ~10 GB | ~40-55 tok/s | $0 |
| phi4-mini | 2.5 GB | ~3 GB | ~80+ tok/s | $0 |
| nomic-embed-text | 274 MB | ~1 GB | N/A (embedding) | $0 |

*Electricity cost: ~$0.15/hr running GPU at full load.*

## Extraction Cost Estimates (1.5M chunks, after dedup may be 89K-300K)

| Method | Est. Tokens | Est. Cost | Time |
|--------|-------------|-----------|------|
| phi4 local (Ollama) | N/A | $0 | ~500 hrs |
| phi4 local (SGLang) | N/A | $0 | ~170 hrs |
| GPT-4.1 Nano batch | ~500M in + 150M out | ~$35 | hours |
| GPT-4o-mini batch | ~500M in + 150M out | ~$56 | hours |
| Tiered (regex+GLiNER+Nano) | ~100M in + 30M out (LLM portion) | ~$10-30 | hours |
| GPT-4o (DO NOT USE for bulk) | ~500M in + 150M out | ~$1,875 | hours |

**Recommended strategy:** Tiered extraction (regex + GLiNER first pass, GPT-4.1 Nano batch for remainder). Estimated cost: $10-50 depending on corpus size after dedup.

## Key Rules

- GPT-4o: user-facing queries ONLY (demo day). Never bulk extraction.
- GPT-4o-mini / GPT-4.1 Nano: bulk extraction at work if budget approved.
- phi4:14b: free local extraction for dev/testing on primary workstation. Quality validation via A/B test.
- Batch API: always use batch (50% off) for bulk work. Never real-time for extraction.
- Tiered approach: regex + GLiNER handle 60-80% of entities for free, LLM only for hard cases.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
