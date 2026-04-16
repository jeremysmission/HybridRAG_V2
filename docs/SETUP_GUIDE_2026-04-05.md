# HybridRAG V2 — Setup Guide

**Workstation note:** for the current work laptop / work desktop lane, use [WORKSTATION_STACK_INSTALL_2026-04-06.md](WORKSTATION_STACK_INSTALL_2026-04-06.md) and `INSTALL_WORKSTATION.bat`. This guide is the generic/manual path.

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Tested on:** Windows 11, Python 3.12.x, CUDA 12.8, NVIDIA workstation desktop GPUs
**Updated:** 2026-04-08 — Python version, Ollama note, troubleshooting

---

## Prerequisites (install these first)

1. **Python 3.12.x** — [python.org](https://python.org) — Add to PATH during install. Python 3.14 is NOT supported.
2. **Git** — [git-scm.com](https://git-scm.com)
3. **Ollama** — [ollama.com/download](https://ollama.com/download) — for local stress testing with phi4 (NOT required for production queries)
4. **Tesseract OCR** — [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) — for scanned PDF OCR in CorpusForge (not used by V2 directly)
5. **NVIDIA CUDA Toolkit 12.8** — [developer.nvidia.com](https://developer.nvidia.com/cuda-downloads) — for GPU embedding

---

## Step 1: Clone and Create Virtual Environment

**Python version:** 3.12 required. Python 3.14 is NOT supported (dependency compatibility issues). If your system default is 3.14, use `py -3.12` explicitly.

```bash
git clone <repo-url> C:\HybridRAG_V2
cd C:\HybridRAG_V2

# Create venv (ALWAYS repo-local, never system-wide)
# Use explicit version if system default is too new:
py -3.12 -m venv .venv
# Or if python 3.12 is your default:
python -m venv .venv

# Activate
.venv\Scripts\activate        # Windows CMD
# or: source .venv/bin/activate  # Git Bash / WSL

# Verify version (must be 3.12.x)
python --version
```

## Step 2: Install PyTorch with CUDA (BEFORE other packages)

**Critical:** Install torch from the PyTorch CUDA index first. If you install from PyPI, you get CPU-only torch and GPU embedding won't work.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

Verify CUDA:
```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

## Step 3: Install Python Dependencies

```bash
pip install -r requirements.txt
```

**If behind corporate proxy:**
```bash
pip install pip-system-certs
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

## Step 4: Pull Embedding Model

```bash
ollama pull nomic-embed-text
```

Verify:
```bash
ollama list | grep nomic
```

## Step 5: (Optional) Pull phi4 for Stress Tests

This is free local LLM for running stress/architecture tests without API costs.
**Not used in production or QA — test infrastructure only.**

```bash
ollama pull phi4:14b-q4_K_M
```

## Step 6: Set API Credentials

**Home/Development (Commercial OpenAI):**
```bash
# Windows CMD:
set OPENAI_API_KEY=sk-...

# Git Bash / PowerShell:
export OPENAI_API_KEY=sk-...
```

**Work/Production (Azure OpenAI):**
```bash
set AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
set AZURE_OPENAI_API_KEY=your-key-here
```

**Never put API keys in config files, code, or .env files committed to git.**

Verify:
```bash
python scripts/boot.py
```

## Step 7: Import Data (from CorpusForge)

CorpusForge exports pre-chunked, pre-embedded packages to `data/source/`.

```bash
python scripts/import_embedengine.py
```

Or for first-time testing with the test corpus:
```bash
python scripts/test_retrieval.py
```

## Step 8: Extract Entities (Sprint 2+)

After data is imported, run entity extraction to populate the structured stores:

```bash
python scripts/extract_entities.py
```

This processes all LanceDB chunks through GPT-4o (costs API tokens).
For a dry-run (see what would be extracted without inserting):
```bash
python scripts/extract_entities.py --dry-run --limit 5
```

## Step 9: Start the Server

```bash
python -m src.api.server
```

Server runs at http://127.0.0.1:8000 — Swagger docs at http://127.0.0.1:8000/docs

## Step 10: Verify

```bash
# Health check
curl http://127.0.0.1:8000/health

# Test query (requires API key + imported data)
curl -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" -d "{\"query\": \"Who is the POC for Thule?\"}"
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Activate venv | `.venv\Scripts\activate` |
| Run server | `python -m src.api.server` |
| Run tests | `pytest tests/` |
| Boot check | `python scripts/boot.py` |
| Import data | `python scripts/import_embedengine.py` |
| Extract entities | `python scripts/extract_entities.py` |
| Stress test (free) | `set HYBRIDRAG_API_PROVIDER=ollama && pytest tests/` |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `torch.cuda.is_available() = False` | Reinstall torch from CUDA index (Step 2) |
| `ModuleNotFoundError: lancedb` | `pip install lancedb==0.30.2` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | `pip install pip-system-certs` |
| `CUDA out of memory` | Set `CUDA_VISIBLE_DEVICES=0` to use GPU 0 only |
| `LLM not configured` | Set OPENAI_API_KEY or AZURE_OPENAI_* env vars |

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
