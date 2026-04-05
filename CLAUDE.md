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
- **No offline mode for generation** — online-only for query answers (GPT-4o / Azure)
- **Ollama phi4 is TEST-ONLY infrastructure** — saves API costs during development. Use for architecture/stress/unit tests where LLM response content is agnostic (parsing, routing, chunking). NEVER for golden eval, QA, demo, or operational use. Do NOT wire Ollama into the operational pipeline — V1 dual-mode was a mistake we are not repeating.
- **No mode switching** — 1 mode, 2 hardware presets (beast, laptop)
- **Pin openai SDK to v1.x** — NEVER upgrade to 2.x
- **DO NOT use `pip install sentence-transformers[onnx]`** — it nukes CUDA torch
- **Dual LLM provider support** — Commercial OpenAI at home (OPENAI_API_KEY), Azure OpenAI at work (AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY). Provider auto-detected from URL. Never hardcode either.

## LLM Provider Config
- **Home/Dev:** `export OPENAI_API_KEY=sk-...` (commercial OpenAI, GPT-4o)
- **Work/Prod:** `export AZURE_OPENAI_ENDPOINT=https://... && export AZURE_OPENAI_API_KEY=...`
- **Stress Tests:** Ollama phi4 via `HYBRIDRAG_API_PROVIDER=ollama` (free, local)
- Provider auto-detect: Azure URLs → Azure client, else → OpenAI client, localhost:11434 → Ollama

## Waiver Compliance
- All new packages must be MIT/Apache 2.0/BSD from USA or NATO allies
- Check `docs/Requested_Waivers_2026-04-04.md` before adding any dependency
- Banned: LangChain, ChromaDB, Milvus, BGE, Qwen, DeepSeek, Meta Llama, DuckDB+VSS
- See `HybridRAG3_Educational/docs/05_security/waiver_reference_sheet.md` for full list

## Push Workflow (MANDATORY)
1. Commit locally (all work stays on local repo)
2. Run `python sanitize_before_push.py --apply` before ANY push to remote
3. Only the sanitized version goes to the remote/work repo
4. The remote repo is what gets zipped for deployment — no surprises in the zip
5. **NEVER push unsanitized code to remote**
6. **NEVER push `sanitize_before_push.py` itself to remote** — it contains replacement patterns and is in `.gitignore`
7. **Git commits: author is Jeremy only** — no Co-Authored-By, no AI attribution
8. **No mention of approved vendor, CoPilot+, agent, or AI in any committed code/docs** — use "CoPilot+" when referring to AI assistance

## File Naming Convention
All files use: `Intuitive_Title_YYYY-MM-DD` format (e.g., `V2_Design_Proposal_2026-04-04.md`)

## Testing
- Golden eval queries in `tests/golden_eval/`
- Run tests: `pytest tests/`
- Target: 20+ golden queries passing by demo
- **3-Tier Test Corpus (MANDATORY):**
  - `tests/test_corpus/tier1_smoke/` — easy clean files, must always pass
  - `tests/test_corpus/tier2_stress/` — messy real-world: OCR garbage, email chains, fragments
  - `tests/test_corpus/tier3_negative/` �� files system must reject: empty, binary, injections
  - Every end-to-end test must exercise all three tiers. No shortcuts, no skipping tiers.
- **Real hardware testing mandatory** — Every sprint QA must include a Beast hardware pass (dual 3090, real corpus, real API calls). Virtual/mock tests are necessary but insufficient. V1 lesson: virtual-only tests miss GPU OOM, CUDA conflicts, and performance issues that cascade.
- **QA uses real data on real hardware whenever possible** — Don't just QA against the 5-file test corpus. When Beast is available, QA should import and test against real production IGS documents (the 700GB corpus or a representative subset). Synthetic tests prove the code compiles; real data proves it works.
- **Single-GPU testing to emulate work Blackwell workstations** — Beast has dual 3090s but work machines have single Blackwell GPUs. QA must test with `CUDA_VISIBLE_DEVICES=0` (single GPU only) to catch issues that won't surface on dual-GPU rigs. The work deployment target is single-GPU Blackwell — test accordingly.

## Python Version
- **Python 3.11 or 3.12 required.** Python 3.14 is NOT supported (dependency compat issues).
- Beast workstation has 3.14 as default — use `py -3.12 -m venv .venv` when creating venvs.

## Key Paths
- Config: `config/config.yaml`
- LanceDB: `data/index/`
- SQLite entities: `data/index/entities.sqlite3`
- EmbedEngine output: `data/source/` (nightly landing zone)
