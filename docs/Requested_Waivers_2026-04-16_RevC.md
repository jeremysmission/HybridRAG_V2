# HybridRAG V2 — Requested Software Waivers

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-16 MDT (Rev C)
**Previous:** Rev B 2026-04-04 (4 waivers), Rev C adds RAGAS + rapidfuzz for QA/Eval GUIs
**Reference:** Waiver Reference Sheet (`HybridRAG3_Educational/docs/05_security/waiver_reference_sheet.md`)
**Pre-Approved Cross-Ref:** `ApprovedSoftware_922 Items.docx` (922-item approved list)

---

## Summary

HybridRAG V2 requires **6 software waivers** (4 original + 2 new for evaluation). All packages are:
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
| Why Required | V1 attempted entity extraction using regex/heuristic methods. The result: service_events table with 1,902 rows but zero populated part numbers, zero failure modes, and garbage site names. GLiNER performs zero-shot NER without fine-tuning, handling the 67+ file formats and inconsistent naming conventions in the enterprise program corpus. It handles 80% of entity extraction at zero API cost, with GPT-4o handling the remaining 20% of complex extractions. |
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
| Why Required | The enterprise program corpus contains extensive structured data in spreadsheets and PDFs: parts received/requested/shipped, maintenance service reports, diagnostics results, logistics trackers. V1's pdfplumber achieves ~32% accuracy on complex tables. Docling achieves 97.9% accuracy. This difference determines whether tabular queries ("Status of PO-2024-0891?") work or fail. |
| Security | MIT license. IBM is an established US enterprise with existing FedRAMP authorizations. Granite-Docling-258M model is Apache 2.0. No telemetry. No outbound connections. |
| Fallback if Denied | Use openpyxl (already GREEN) for Excel files + pdfplumber (already GREEN) for PDF tables. Lower accuracy on complex/scanned tables but functional for well-formatted spreadsheets. |

**Justification Template:**
```
docling v2.x is an MIT-licensed Python package published by IBM
Research (USA). It is used by HybridRAG V2 to extract structured
table data from PDFs and spreadsheets with 97.9% accuracy on complex
tables. Uses the Granite-Docling-258M model (Apache 2.0, IBM). Zero
telemetry, zero outbound network activity. Processes documents
entirely in-process. IBM is an established US enterprise with
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

## Waiver Request 5: RAGAS (NEW — Rev C)

| Field | Detail |
|-------|--------|
| Package | ragas |
| Version | 0.4.x (latest stable) |
| License | Apache 2.0 |
| Publisher | Explodinggradients / Open source (arXiv:2309.15217, peer-reviewed) |
| pip install | `pip install ragas` |
| Purpose | Industry-standard evaluation framework for Retrieval-Augmented Generation systems. Measures retrieval quality (context precision, context recall) and generation quality (faithfulness, answer relevancy). Required by QA Workbench and Eval GUI for objective, reproducible quality measurement. |
| Data Flow | In-process library. Reads local query packs and eval results. Non-LLM metrics (context precision, context recall) run entirely locally with zero network access. LLM-based metrics (faithfulness, answer relevancy) are OPTIONAL and would use already-approved Azure OpenAI API. |
| Server Required | No — in-process evaluation library |
| Current Status | Not on waiver sheet (NEW request) |
| Dependencies | pydantic (MIT, already GREEN), numpy (BSD-3, already GREEN), datasets (Apache 2.0, Hugging Face/USA) |
| Why Required | Without RAGAS, quality measurement is manual and subjective. RAGAS provides the same metrics used by industry leaders (Google, Microsoft, Meta) to evaluate RAG systems. Our QA Workbench and Eval GUI display "ragas not installed" without it, blocking the quality certification workflow needed before demo. The Non-LLM metrics require zero API access and run in seconds. |
| Security | Apache 2.0 license. Published as peer-reviewed research (arXiv:2309.15217). Zero telemetry. Non-LLM metrics require zero network access. The framework is the most widely cited RAG evaluation tool in both academic and production use. |
| Fallback if Denied | Manual evaluation using custom Python scripts with precision/recall calculations. Loses industry-standard metric definitions and reproducibility. QA Workbench RAGAS tab shows "not installed" but other tabs still function. |
| Pre-Approved Reference | Anaconda3 (approved) includes pip; ragas is a pip package inside the approved Anaconda environment. Similar to how numpy, scipy, pandas are pip packages inside Anaconda. |

**Justification Template:**
```
ragas v0.4.x is an Apache 2.0-licensed Python package for evaluating
Retrieval-Augmented Generation systems. It is the industry-standard
framework cited by Google, Microsoft, and Meta for RAG quality
measurement. Published as peer-reviewed research (arXiv:2309.15217).
Used by HybridRAG V2's QA Workbench and Eval GUI for objective,
reproducible retrieval quality metrics. Non-LLM metrics run entirely
in-process with zero network access. Zero telemetry. Installs as a
pip package inside the approved Anaconda environment.
```

---

## Waiver Request 6: rapidfuzz (NEW — Rev C)

| Field | Detail |
|-------|--------|
| Package | rapidfuzz |
| Version | Latest stable |
| License | MIT |
| Publisher | Max Bachmann / Open source (Germany, NATO ally) |
| pip install | `pip install rapidfuzz` |
| Purpose | High-performance fuzzy string matching library used by RAGAS for Non-LLM context recall and precision metrics. Computes Levenshtein similarity between retrieved and reference contexts without requiring an LLM judge. |
| Data Flow | In-process library. Pure computation on local strings. Zero network activity. |
| Server Required | No — in-process string matching |
| Current Status | Not on waiver sheet (NEW request) |
| Dependencies | None (C++ extension with pre-built wheels, no additional Python deps) |
| Why Required | Required dependency for RAGAS Non-LLM metrics. Without rapidfuzz, RAGAS falls back to LLM-based evaluation which requires API access and costs. rapidfuzz enables fully offline, deterministic quality measurement. It is the standard fuzzy matching library replacing the older fuzzywuzzy (which had a GPL license issue). |
| Security | MIT license. Germany is a NATO ally. Zero CVEs on NVD. No telemetry. No network calls. Pre-built binary wheels available for Windows. |
| Fallback if Denied | RAGAS LLM-based metrics only (requires Azure OpenAI API access and per-query cost). Lose the ability to run offline, deterministic quality checks. |
| Pre-Approved Reference | Anaconda3 (approved) includes pip; rapidfuzz is a pip package inside the approved Anaconda environment. |

**Justification Template:**
```
rapidfuzz is an MIT-licensed Python package for high-performance
fuzzy string matching. Used by HybridRAG V2's RAGAS evaluation
framework for offline, deterministic retrieval quality metrics
(context precision and recall without LLM). Zero telemetry, zero
network access. Pure in-process string computation. Published by
Max Bachmann (Germany, NATO ally). Installs as a pip package inside
the approved Anaconda environment. rapidfuzz has zero known CVEs.
```

---

## Status Legend

| Color | Meaning |
|-------|---------|
| GREEN | Pre-approved on the 922-item approved software list |
| YELLOW | Waiver application submitted or pending |
| RED | Banned -- NDAA non-compliant (Chinese origin) or explicitly denied |

---

## Software Stack by Application

### HybridRAG V2 -- Core Query/Retrieval System

| Package | License | Origin | App Role | Status |
|---------|---------|--------|----------|--------|
| Python (Anaconda3) | BSD-3 | USA | Runtime | GREEN (approved 3.12.7) |
| PowerShell 7 | MIT | USA (Microsoft) | Install/launch scripts | GREEN (approved 7.6.0) |
| torch (PyTorch) | BSD-3 | USA (Meta) | GPU compute for embeddings | YELLOW (via Anaconda pip) |
| sentence-transformers | Apache 2.0 | Germany (NATO) | Embedding model loader | YELLOW (via Anaconda pip) |
| lancedb | Apache 2.0 | USA (SF, YC) | Vector + FTS database | YELLOW (waiver submitted) |
| flashrank | Apache 2.0 | Open source | Reranker (4MB model, CPU) | YELLOW (waiver submitted) |
| gliner | Apache 2.0 | France (NATO) | Entity extraction (NER) | YELLOW (waiver submitted) |
| docling | MIT | USA (IBM) | Table extraction from PDFs | YELLOW (waiver submitted) |
| pydantic | MIT | Open source | Config validation | GREEN (via Anaconda) |
| numpy / scipy | BSD-3 | USA | Numeric compute | GREEN (via Anaconda) |
| openpyxl | MIT | Open source | Excel file handling | GREEN (via Anaconda) |

### QA Workbench + Eval GUI -- Evaluation System

| Package | License | Origin | App Role | Status |
|---------|---------|--------|----------|--------|
| ragas | Apache 2.0 | Open source (arXiv) | RAG evaluation metrics | YELLOW (apply today) |
| rapidfuzz | MIT | Germany (NATO) | String matching for RAGAS | YELLOW (apply today) |
| scikit-learn | BSD-3 | Open source | Eval statistics | GREEN (via Anaconda) |
| pytest | MIT | Open source | Regression test suite | GREEN (via Anaconda) |

### CorpusForge -- Ingest/Chunking Pipeline

| Package | License | Origin | App Role | Status |
|---------|---------|--------|----------|--------|
| Python (Anaconda3) | BSD-3 | USA | Runtime | GREEN (approved 3.12.7) |
| torch (PyTorch) | BSD-3 | USA (Meta) | GPU embedding at chunk time | YELLOW (via Anaconda pip) |
| sentence-transformers | Apache 2.0 | Germany (NATO) | Embedding model | YELLOW (via Anaconda pip) |
| pdfminer.six | MIT | Open source | PDF text extraction | GREEN (via Anaconda pip) |
| python-docx | MIT | Open source | DOCX parsing | GREEN (via Anaconda pip) |

### Explicitly NOT Used (RED)

| Package | Origin | Why Banned |
|---------|--------|-----------|
| DeepSeek | China | NDAA non-compliant |
| Qwen | China (Alibaba) | NDAA non-compliant |
| Any Chinese-origin LLM | China | NDAA non-compliant |

---

## Waiver Application Priority

| Priority | Package | App | Blocking? | Status |
|---|---|---|---|---|
| 1 | lancedb | V2 Core | Yes -- core storage | YELLOW (submitted) |
| 2 | flashrank | V2 Core | No -- LanceDB fallback | YELLOW (submitted) |
| 3 | gliner | V2 Core | No -- GPT-4o fallback | YELLOW (submitted) |
| 4 | docling | V2 Core | No -- openpyxl fallback | YELLOW (submitted) |
| **5** | **ragas** | **QA/Eval GUIs** | **Yes -- blocks eval** | **YELLOW (apply today)** |
| **6** | **rapidfuzz** | **QA/Eval GUIs** | **Yes -- RAGAS dep** | **YELLOW (apply today)** |

Development proceeds with or without waiver approval. Each package has a documented fallback using already-approved software.

**Key argument for all YELLOW packages:** They install as pip packages inside the pre-approved Anaconda 3.12.7 environment. They are extensions of an approved platform, not standalone software. All are open-source (MIT or Apache 2.0), all from USA or NATO ally countries, all run locally with zero data exfiltration.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-16 MDT (Rev C)

