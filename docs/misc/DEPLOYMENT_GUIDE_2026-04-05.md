# HybridRAG V2 — Deployment Guide

**Workstation note:** for the current work laptop / work desktop lane, use [WORKSTATION_STACK_INSTALL_2026-04-06.md](WORKSTATION_STACK_INSTALL_2026-04-06.md) and `INSTALL_WORKSTATION.bat`. This guide is the generic/manual path.

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Audience:** Anyone deploying V2 on a fresh machine for the first time

---

## 1. Prerequisites

### Hardware

| Component | Recommended | Minimum |
|-----------|-------------|---------|
| GPU | NVIDIA GPU, 8GB+ VRAM (e.g., RTX 3060+) | CPU-only fallback works but embedding is slower |
| RAM | 32GB | 16GB |
| Disk | 50GB free (stores grow with corpus size) | 20GB for small test corpus |
| OS | Windows 10/11 64-bit | Windows 10 64-bit |

### Software (install all before proceeding)

| Software | Version | Where to Get It |
|----------|---------|-----------------|
| Python | **3.11 or 3.12** (NOT 3.14 — see note below) | [python.org](https://python.org) — check "Add to PATH" during install |
| Git | Latest | [git-scm.com](https://git-scm.com) |
| Ollama | Latest | [ollama.com/download](https://ollama.com/download) — runs embedding models locally |
| Tesseract OCR | Latest | [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) — needed for scanned PDFs |
| NVIDIA CUDA Toolkit | 12.8 | [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads) — skip if CPU-only |

**Python version warning:** Python 3.14 is NOT supported. Several dependencies have compatibility issues with 3.14. If your machine has 3.14 as the default (common on newer builds), you must install 3.12 side-by-side and use `py -3.12` explicitly when creating the virtual environment.

---

## 2. Clone and Create Virtual Environment

```bash
git clone <repo-url> C:\HybridRAG_V2
cd C:\HybridRAG_V2
```

Create the virtual environment. Use the explicit Python version launcher if your system default is 3.14:

```bash
# If your system default Python is 3.14 (check with: python --version)
py -3.12 -m venv .venv

# If your system default Python is already 3.11 or 3.12
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows CMD
.venv\Scripts\activate

# Git Bash or WSL
source .venv/bin/activate

# PowerShell
.venv\Scripts\Activate.ps1
```

Verify the Python version. It must say 3.11.x or 3.12.x:

```bash
python --version
```

---

## 3. Install Dependencies

### Step 3a: Install PyTorch with CUDA FIRST

This must happen before installing anything else. If you install torch from PyPI (the default), you get a CPU-only build and GPU embedding will not work.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

If you do not have an NVIDIA GPU and want CPU-only:

```bash
pip install torch
```

Verify CUDA is available (GPU installs only):

```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU only\"}')"
```

You should see `CUDA: True` and your GPU name (e.g., `NVIDIA NVIDIA workstation GPU`).

### Step 3b: Install remaining dependencies

```bash
pip install -r requirements.txt
```

### Troubleshooting: Corporate proxy or certificate errors

If you see `SSL: CERTIFICATE_VERIFY_FAILED` or connection timeouts behind a corporate network:

```bash
pip install pip-system-certs
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

If the PyTorch CUDA index is blocked by your proxy, download the wheel manually from [download.pytorch.org/whl/cu128](https://download.pytorch.org/whl/cu128) and install with `pip install <filename>.whl`.

---

## 4. Pull Models

### Required: Embedding model

V2 uses Ollama to run the `nomic-embed-text` embedding model locally. This is the only model required for the system to function.

```bash
ollama pull nomic-embed-text
```

Verify:

```bash
ollama list
```

You should see `nomic-embed-text` in the list.

### Optional: phi4 for stress tests

This is a free local LLM used only during development to run architecture and stress tests without consuming API credits. It is NOT used in production, QA, or demos.

```bash
ollama pull phi4:14b-q4_K_M
```

This model is approximately 8GB. It requires at least 10GB VRAM or will fall back to CPU (slow but functional).

---

## 5. Configure

### 5a: Review config.yaml

The configuration file is at `config/config.yaml`. Here is what each section controls:

| Section | What It Does | What You Might Change |
|---------|-------------|----------------------|
| `paths` | File locations for LanceDB, entity database, and data import directory | Change if you want data on a different drive |
| `retrieval` | Controls how many chunks are retrieved and reranked per query | `top_k` (default 10) — more = broader answers, slower |
| `llm` | Model name, token limits, temperature, timeout | Usually leave defaults. Change `timeout_seconds` if on slow network |
| `extraction` | Confidence threshold and part number patterns for entity extraction | `min_confidence` (default 0.7) — lower = more entities but more noise |
| `server` | Host and port for the API server | Change `port` if 8000 is already in use |
| `crag` | Corrective RAG (experimental, disabled by default) | Leave `enabled: false` unless testing CRAG |
| `hardware_preset` | `primary workstation` or `laptop` — adjusts batch sizes | Set to `laptop` on machines with less than 16GB VRAM |

For most deployments, the defaults work without changes.

### 5b: Set API credentials

The system needs an LLM API key to generate answers. Set it as an environment variable — never put keys in config files or code.

**Home / Development (Commercial OpenAI):**

```bash
# Windows CMD
set OPENAI_API_KEY=sk-your-key-here

# Git Bash / PowerShell
export OPENAI_API_KEY=sk-your-key-here
```

**Work / Production (Azure OpenAI):**

```bash
set AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
set AZURE_OPENAI_API_KEY=your-key-here
```

The system auto-detects which provider to use based on which environment variables are set. You do not need to change anything in config.yaml.

**Verify credentials are working:**

```bash
python scripts/boot.py
```

This checks that all stores can be opened, the embedding model responds, and the LLM API is reachable.

---

## 6. Import Data

V2 consumes pre-chunked, pre-embedded data packages produced by the companion EmbedEngine pipeline. These packages land in `data/source/`.

### 6a: Copy EmbedEngine output

Place the EmbedEngine export package (containing `chunks.jsonl`, `vectors.lance`, `entities.jsonl`, and `manifest.json`) into the `data/source/` directory.

### 6b: Run import

```bash
python scripts/import_embedengine.py
```

This loads chunks into LanceDB, runs second-pass entity extraction via GPT-4o (costs API tokens), validates entities through the quality gate, and promotes them to the production stores.

For a small test corpus first:

```bash
python scripts/test_retrieval.py
```

### 6c: Verify import

After import completes, check that data is loaded:

```bash
curl http://127.0.0.1:8000/health
```

The `chunks_loaded` field should be greater than zero.

---

## 7. Extract Entities

After data is imported, run entity extraction to populate the structured entity and relationship stores:

```bash
python scripts/extract_entities.py
```

**What to expect:**
- This processes every chunk through GPT-4o for entity extraction. It costs API tokens.
- For a corpus of ~2,000 chunks, expect 10-20 minutes and approximately $5-10 in API costs.
- For the full 27.6M chunk production corpus, expect several hours.

**Dry-run option** (see what would be extracted without inserting):

```bash
python scripts/extract_entities.py --dry-run --limit 5
```

This shows sample extractions from 5 chunks so you can verify quality before committing to a full run.

---

## 8. Start the API Server

```bash
python -m src.api.server
```

The server starts at `http://127.0.0.1:8000`. Swagger API documentation is available at `http://127.0.0.1:8000/docs`.

Verify with a health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "chunks_loaded": 2935,
  "entities_loaded": 412,
  "relationships_loaded": 187,
  "llm_available": true
}
```

If `llm_available` is `false`, your API key environment variable is not set (see Step 5b).

---

## 9. Start the GUI

With the API server still running (leave that terminal open), open a new terminal:

```bash
.venv\Scripts\activate
python src/gui/launch_gui.py
```

The GUI is a Tkinter desktop application with three tabs:
- **Query** — type questions and get answers
- **Entities** — browse extracted entities and relationships
- **Settings** — view current configuration (read-only)

On first boot, the GUI connects to the API server at `http://127.0.0.1:8000`. If the server is not running, you will see a connection error in the status bar.

---

## 10. Verify Installation

Run through this checklist to confirm everything is working:

```bash
# 1. Health check — should return status "ok" with chunks > 0
curl http://127.0.0.1:8000/health

# 2. Entity stats — should show entity counts by type
curl http://127.0.0.1:8000/entities/stats

# 3. Test query — should return an answer with confidence and sources
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Who is the POC for Thule?\"}"

# 4. Streaming query — should stream tokens via SSE
curl -N -X POST http://127.0.0.1:8000/query/stream \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"What part numbers are associated with Thule?\"}"

# 5. Run automated tests
pytest tests/
```

If all five pass, the installation is complete and operational.

---

## 11. Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `torch.cuda.is_available()` returns `False` | Torch installed from PyPI (CPU-only) | Uninstall torch, reinstall from CUDA index: `pip install torch --index-url https://download.pytorch.org/whl/cu128` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Corporate proxy intercepting HTTPS | `pip install pip-system-certs` then retry |
| `ModuleNotFoundError: lancedb` | Missing dependency | `pip install lancedb==0.30.2` |
| `ConnectionRefusedError` on /health | API server not running | Start the server: `python -m src.api.server` |
| `LLM not configured` error on /query | No API key set | Set `OPENAI_API_KEY` or `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` environment variables |
| `/query` returns 503 "No data loaded" | No data imported yet | Run `python scripts/import_embedengine.py` first |
| `CUDA out of memory` | GPU VRAM exhausted | Set `CUDA_VISIBLE_DEVICES=0` to use a single GPU; reduce batch sizes; or set `hardware_preset: laptop` in config.yaml |
| `ollama list` shows no models | Embedding model not pulled | Run `ollama pull nomic-embed-text` |
| Python version error on venv creation | System default is 3.14 | Use `py -3.12 -m venv .venv` instead of `python -m venv .venv` |
| GUI won't start / blank window | Server not running | Start the API server in a separate terminal first |
| Slow queries (>30 seconds) | CPU-only torch, or large `top_k` | Verify CUDA is available; reduce `top_k` in config.yaml |
| Empty entity/relationship stores | Entity extraction not run | Run `python scripts/extract_entities.py` after importing data |

---

## Quick Reference

| Task | Command |
|------|---------|
| Activate venv | `.venv\Scripts\activate` |
| Start server | `python -m src.api.server` |
| Start GUI | `python src/gui/launch_gui.py` |
| Run tests | `pytest tests/` |
| Boot check | `python scripts/boot.py` |
| Import data | `python scripts/import_embedengine.py` |
| Extract entities | `python scripts/extract_entities.py` |
| Health check | `curl http://127.0.0.1:8000/health` |

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
