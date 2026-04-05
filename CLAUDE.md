# HybridRAG V2 — Agent Instructions

## Project Overview
HybridRAG V2 is an online-only, tri-store RAG system for querying IGS/NEXION military maintenance and operations documents. It consumes pre-built chunks from a separate EmbedEngine (nightly pipeline) and provides semantic, entity, aggregation, and tabular query capabilities.

## Architecture
- **Store 1:** LanceDB (vector + BM25 hybrid search + metadata filtering)
- **Store 2:** SQLite entities (quality-gated, normalized via controlled vocabularies)
- **Store 3:** SQLite relationships (entity-relationship triples for multi-hop queries)
- **Query Router:** GPT-4o classifies queries → routes to appropriate store(s)
- **Reranker:** FlashRank (4MB, sub-20ms, CPU)
- **LLM:** GPT-4o / GPT-OSS-120B (online only, no offline models)

## Code Rules
- **500 lines max per class** (comments excluded) — keeps code AI-reviewable and modular
- **No offline mode** — online-only, single code path
- **No mode switching** — 1 mode, 2 hardware presets (beast, laptop)
- **Pin openai SDK to v1.x** — NEVER upgrade to 2.x
- **DO NOT use `pip install sentence-transformers[onnx]`** — it nukes CUDA torch

## Waiver Compliance
- All new packages must be MIT/Apache 2.0/BSD from USA or NATO allies
- Check `docs/Requested_Waivers_2026-04-04.md` before adding any dependency
- Banned: LangChain, ChromaDB, Milvus, BGE, Qwen, DeepSeek, Meta Llama, DuckDB+VSS
- See `HybridRAG3_Educational/docs/05_security/waiver_reference_sheet.md` for full list

## File Naming Convention
All files use: `Intuitive_Title_YYYY-MM-DD` format (e.g., `V2_Design_Proposal_2026-04-04.md`)

## Testing
- Golden eval queries in `tests/golden_eval/`
- Run tests: `pytest tests/`
- Target: 20+ golden queries passing by demo

## Key Paths
- Config: `config/config.yaml`
- LanceDB: `data/index/`
- SQLite entities: `data/index/entities.sqlite3`
- EmbedEngine output: `data/source/` (nightly landing zone)
