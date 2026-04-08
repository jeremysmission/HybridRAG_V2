# Environment Assumptions for Demo Day

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-08 MDT

---

## Required Before Demo

### 1. Python

- **Version:** 3.11.x or 3.12.x (NOT 3.14 -- dependency compat issues)
- **Venv:** `.venv` at repo root, activated before all commands
- **Verify:** `.venv\Scripts\python.exe --version`

### 2. GPU / CUDA

- **CUDA Toolkit:** 12.8 installed system-wide
- **torch:** 2.7.1+cu128 from PyTorch CUDA index (NOT PyPI CPU-only)
- **GPU:** NVIDIA RTX 3090 (24GB VRAM) or equivalent
- **Single-GPU mode:** `set CUDA_VISIBLE_DEVICES=0`
- **Verify:** `.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"`

### 3. API Keys (set as environment variables)

| Variable | Required For | Default If Missing |
|----------|-------------|-------------------|
| `OPENAI_API_KEY` | GPT-4o generation (home/dev) | LLM unavailable -- retrieval-only mode |
| `AZURE_OPENAI_ENDPOINT` | Azure GPT-4o (work) | Falls back to OPENAI_API_KEY |
| `AZURE_OPENAI_API_KEY` | Azure GPT-4o (work) | Falls back to OPENAI_API_KEY |

**Demo without API key:** Retrieval works (25/25 golden eval). Generation/LLM answers require a key. Rule-based fallback router handles routing.

### 4. Ollama (optional for demo, required for extraction)

- **Models needed:** `phi4:14b-q4_K_M` (bulk extraction), `nomic-embed-text` (already in venv)
- **Service:** Must be running if extraction scripts are used
- **Port:** Default 11434
- **Verify:** `ollama list`
- **NOT needed for demo queries** -- demo uses CUDA embedding via sentence-transformers, not Ollama

### 5. Data Files

| File | Path | Expected State |
|------|------|---------------|
| LanceDB store | `data/index/lancedb/` | 17,707 chunks, IVF_PQ index |
| Entity store | `data/index/entities.sqlite3` | 40,981 entities, 9,497 relationships |
| Config | `config/config.yaml` | Default beast preset |
| Golden queries | `tests/golden_eval/golden_queries.json` | 25 queries |

### 6. Network

- **Home/dev:** Direct internet for OpenAI API
- **Work:** Proxy required -- set `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY=127.0.0.1,localhost`
- **pip installs at work:** Use `.venv\pip.ini` with proxy config and `pip-system-certs`

### 7. Disk Space

- **Minimum:** 10 GB free on C:
- **Current usage:** LanceDB ~79 MB, Entity DB ~53 MB, venv ~3 GB
- **Monitor:** C: is 98% full (55 GB free as of 2026-04-08)

---

## Paths That Must Exist

```
C:\HybridRAG_V2\
  .venv\                         -- Python virtual environment
  config\config.yaml             -- Main config
  data\index\lancedb\            -- Vector store (17,707 chunks)
  data\index\entities.sqlite3    -- Entity store (40,981 entities)
  tests\golden_eval\golden_queries.json  -- Golden eval queries
  scripts\run_golden_eval.py     -- Golden eval runner
  scripts\health_check.py        -- Health check
  src\api\server.py              -- FastAPI server
  src\gui\app.py                 -- Tkinter GUI
```

---

## Environment Variable Cheatsheet

```bash
# Home / Beast workstation
set OPENAI_API_KEY=sk-...
set CUDA_VISIBLE_DEVICES=0

# Work machines (add proxy)
set HTTP_PROXY=http://centralproxy.northgrum.com:80
set HTTPS_PROXY=http://centralproxy.northgrum.com:80
set NO_PROXY=127.0.0.1,localhost
set AZURE_OPENAI_ENDPOINT=https://...
set AZURE_OPENAI_API_KEY=...
```

---

## What Happens Without Each Component

| Missing | Impact | Workaround |
|---------|--------|-----------|
| OPENAI_API_KEY | No LLM generation, rule-based router | Retrieval still works 25/25 |
| CUDA/GPU | Falls back to ONNX CPU embedding (45x slower) | Set `device: cpu` in embedder |
| Ollama | No phi4 extraction | Use GPT-4o extraction or skip |
| Entity DB | No ENTITY/AGGREGATE/TABULAR queries | Vector-only retrieval (20/25) |
| LanceDB | No queries at all | Must import first |
| Internet | No API calls | Local Ollama only |

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
