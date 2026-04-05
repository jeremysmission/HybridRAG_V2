# HybridRAG V2 — Requested Software Waivers

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-04 MDT
**Reference:** Waiver Reference Sheet (`HybridRAG3_Educational/docs/05_security/waiver_reference_sheet.md`)

---

## Summary

HybridRAG V2 requires **4 new software waivers**. All packages are:
- Open source (MIT or Apache 2.0 license)
- From USA or NATO ally countries
- Zero telemetry, zero outbound network activity during operation
- In-process libraries (no server processes, no daemons)

---

## Waiver Request 1: LanceDB

| Field | Detail |
|-------|--------|
| Package | lancedb |
| Version | 0.29.2 (or latest stable) |
| License | Apache 2.0 |
| Publisher | LanceDB Inc. / USA (San Francisco, YC-backed) |
| pip install | `pip install lancedb` |
| Purpose | All-in-one embedded vector database replacing FAISS + SQLite FTS5 + numpy memmap. Provides dense vector search, BM25 full-text search (via Tantivy/Rust), metadata filtering, and built-in reranking in a single embedded database. |
| Data Flow | In-process embedded DB, file-based storage (Lance columnar format), zero network activity. Fully offline, like SQLite. |
| Server Required | No — fully embedded, serverless |
| Current Status | BLUE on waiver reference sheet (recommended for next phase, not yet installed) |
| Dependencies | pyarrow (Apache 2.0, Apache Foundation/USA), pydantic (MIT, already GREEN), numpy (BSD-3, already GREEN), tqdm (MIT, already GREEN) |
| Why Required | SQLite FTS5 keyword search takes 12-24 seconds on the production 27.6M chunk index. LanceDB's Tantivy engine (Rust) handles 41M+ documents in sub-second. At production scale, FTS5 is a bottleneck that prevents acceptable query latency. LanceDB also eliminates the need to manage 3 separate storage systems (FAISS index file + SQLite database + numpy memmap file). |
| Security | Zero CVEs on NVD. No telemetry. No outbound connections. File-based storage can be encrypted at rest via OS-level encryption. |
| Fallback if Denied | Revert to FAISS-cpu + SQLite FTS5 (V1 stack). Lose built-in hybrid search and accept 12-24s keyword search latency. |

**Justification Template:**
```
lancedb v0.29.2 is an Apache 2.0-licensed Python package published by
LanceDB Inc. (San Francisco, USA). It is used by HybridRAG V2 as an
embedded vector database providing dense vector search, BM25 keyword
search, and metadata filtering in a single in-process library. Zero
telemetry, zero outbound network activity. lancedb has zero known CVEs
on the NVD and is not on the CISA KEV list. LanceDB is designed as
"the SQLite of vector databases" — fully embedded, serverless, and
file-based.
```

---

## Waiver Request 2: GLiNER

| Field | Detail |
|-------|--------|
| Package | gliner |
| Version | Latest stable |
| License | Apache 2.0 |
| Publisher | Academic research / France (NAACL 2024 paper, Knowledgator) |
| pip install | `pip install gliner` |
| Purpose | Zero-shot named entity recognition (NER) for extracting part numbers, people, sites, dates, and failure modes from document chunks at index time. 205M parameters, runs on CPU. No fine-tuning required. |
| Data Flow | In-process library, runs entirely in local memory. Zero network activity. Model weights loaded from local disk. |
| Server Required | No — in-process inference |
| Current Status | Not on waiver sheet (NEW request) |
| Dependencies | torch (BSD-3, already in stack for EmbedEngine CUDA), transformers (Apache 2.0, Hugging Face/USA) |
| Why Required | V1 attempted entity extraction using regex/heuristic methods. The result: service_events table with 1,902 rows but zero populated part numbers, zero failure modes, and garbage site names. GLiNER performs zero-shot NER without fine-tuning, handling the 67+ file formats and inconsistent naming conventions in the IGS corpus. It handles 80% of entity extraction at zero API cost, with GPT-4o handling the remaining 20% of complex extractions. |
| Security | Apache 2.0 license. France is a NATO ally. Model weights are fully auditable. No telemetry. No network calls during inference. |
| Fallback if Denied | Use GPT-4o for all entity extraction. Higher cost (~$935 vs ~$200 for hybrid approach) but zero new dependencies for the extraction pipeline. |

**Justification Template:**
```
gliner is an Apache 2.0-licensed Python package for zero-shot named
entity recognition. It is used by HybridRAG V2 to extract structured
entities (part numbers, personnel, sites, dates) from document chunks
at index time. 205M parameter model running on CPU. Zero telemetry,
zero outbound network activity during operation. Processes text
entirely in-process using local model weights. Published under
academic research from France (NATO ally), presented at NAACL 2024.
```

---

## Waiver Request 3: Docling

| Field | Detail |
|-------|--------|
| Package | docling |
| Version | 2.x (latest stable) |
| License | MIT |
| Publisher | IBM Research / USA (Zurich lab, Apache 2.0 model) |
| pip install | `pip install docling` |
| Purpose | Extracts tables from PDFs, scanned documents, and spreadsheets as structured data (rows and columns) rather than prose text. Uses IBM's Granite-Docling-258M vision-language model for layout analysis. |
| Data Flow | In-process library, runs entirely in local memory. Zero network activity. Model weights loaded from local disk. |
| Server Required | No — in-process inference |
| Current Status | Not on waiver sheet (NEW request) |
| Dependencies | torch (BSD-3, already in stack), transformers (Apache 2.0, HuggingFace/USA), safetensors (Apache 2.0, HuggingFace/USA), docling-core (MIT, IBM) |
| Why Required | The IGS corpus contains extensive structured data in spreadsheets and PDFs: parts received/requested/shipped, maintenance service reports, diagnostics results, logistics trackers. V1's pdfplumber achieves ~32% accuracy on complex tables. Docling achieves 97.9% accuracy. This difference determines whether tabular queries ("Status of PO-2024-0891?") work or fail. |
| Security | MIT license. IBM is an established US defense contractor with existing FedRAMP authorizations. Granite-Docling-258M model is Apache 2.0. No telemetry. No outbound connections. |
| Fallback if Denied | Use openpyxl (already GREEN) for Excel files + pdfplumber (already GREEN) for PDF tables. Lower accuracy on complex/scanned tables but functional for well-formatted spreadsheets. |

**Justification Template:**
```
docling v2.x is an MIT-licensed Python package published by IBM
Research (USA). It is used by HybridRAG V2 to extract structured
table data from PDFs and spreadsheets with 97.9% accuracy on complex
tables. Uses the Granite-Docling-258M model (Apache 2.0, IBM). Zero
telemetry, zero outbound network activity. Processes documents
entirely in-process. IBM is an established US defense contractor with
existing FedRAMP authorizations. docling has zero known CVEs on the
NVD.
```

---

## Waiver Request 4: FlashRank

| Field | Detail |
|-------|--------|
| Package | flashrank |
| Version | Latest stable |
| License | Apache 2.0 |
| Publisher | Open source (Prithiviraj Damodaran) |
| pip install | `pip install flashrank` |
| Purpose | Ultra-fast document reranking for improving retrieval precision. 4MB quantized model, sub-20ms latency for 50 candidates on CPU. Replaces V1's phi4:14B reranker (130 seconds per query — unusable). |
| Data Flow | In-process library. 4MB model file loaded from disk. Zero network activity. No GPU required. |
| Server Required | No — in-process inference |
| Current Status | Not on waiver sheet (NEW request) |
| Dependencies | Minimal — no torch, no transformers, no sentence-transformers. Single pip install. |
| Why Required | V1's reranker (phi4:14B via Ollama, 130 seconds per query) was disabled because it was unusable. FlashRank achieves 95-98% of cross-encoder accuracy at sub-20ms latency on CPU. This enables reranking 30-50 candidates per query within the latency budget. The alternative (no reranking) reduces retrieval precision by 15-18% MRR. |
| Security | Apache 2.0 license. 4MB model footprint — easily auditable. No telemetry. No network calls. No heavy dependencies (no torch, no transformers). |
| Fallback if Denied | Use LanceDB's built-in reranking API (linear combination or RRF). Zero additional dependencies but less accurate than FlashRank's learned reranking. |

**Justification Template:**
```
flashrank is an Apache 2.0-licensed Python package for ultra-fast
document reranking. It is used by HybridRAG V2 to rerank retrieval
candidates in sub-20ms on CPU, replacing V1's unusable 130-second
reranker. Uses a 4MB quantized model with no torch or transformers
dependency. Zero telemetry, zero outbound network activity. Runs
entirely in-process. flashrank has zero known CVEs on the NVD.
```

---

## Waiver Priority

| Priority | Package | Blocking? | Phase Needed |
|---|---|---|---|
| 1 | lancedb | Yes — core storage | Sprint 1 (Week 1) |
| 2 | flashrank | No — LanceDB fallback | Sprint 1 (Week 1) |
| 3 | gliner | No — GPT-4o fallback | Sprint 2 (Week 3) |
| 4 | docling | No — openpyxl fallback | Sprint 2 (Week 3) |

Development proceeds with or without waiver approval. Each package has a documented fallback using already-approved software.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-04 MDT
