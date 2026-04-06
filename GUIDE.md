# HybridRAG V2 Guide

## Project Overview

HybridRAG V2 is a tri-store retrieval and answer system for IGS and NEXION maintenance and operations documents. It consumes pre-built chunks from the ingest pipeline and supports semantic, entity, aggregation, and tabular query paths.

## Core Architecture

- **Store 1:** LanceDB for vector search, BM25 hybrid search, and metadata filtering
- **Store 2:** SQLite entities with normalization and quality gates
- **Store 3:** SQLite relationships for multi-hop and structured retrieval
- **Query Router:** classifies the query and selects the right retrieval path
- **Reranker:** FlashRank on CPU
- **Generation Layer:** OpenAI-compatible providers plus local Ollama for development and stress testing

## Development Rules

- **500 lines max per class** where practical
- **No offline generation mode for operational answers**
- **Ollama is test and development infrastructure only**
- **Keep one code path with hardware-specific config, not separate product modes**
- **Pin the OpenAI SDK to v1.x**
- **Do not install `sentence-transformers[onnx]` because it can replace CUDA torch**
- **Keep provider selection environment-driven**

## Provider Notes

- Home and general development can use `OPENAI_API_KEY`
- Work deployments can use `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY`
- Local development and stress tests can use Ollama

Provider detection is based on the configured endpoint and provider settings.

## Daily Workstation Reminders

- Use the repo venv explicitly: `.\.venv\Scripts\python.exe` and `.\.venv\Scripts\pip.exe`
- If package installs fail at work, set session proxy vars first:
  - `$env:HTTP_PROXY = "http://centralproxy.northgrum.com:80"`
  - `$env:HTTPS_PROXY = "http://centralproxy.northgrum.com:80"`
  - `$env:NO_PROXY = "127.0.0.1,localhost"`
- Verify torch in the repo venv with:
  - `.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"`
- If local services are involved, keep `NO_PROXY` set for `127.0.0.1,localhost`

## Dependency Policy

- New packages should stay within the approved license and sourcing constraints already documented for the project
- Review [Requested_Waivers_2026-04-04.md](/C:/HybridRAG_V2/docs/Requested_Waivers_2026-04-04.md) before adding new dependencies
- Avoid the banned vector and model stack already listed in the project policy docs

## Related Docs

- [HOW_IT_WORKS_TECHNICAL_2026-04-05.md](/C:/HybridRAG_V2/docs/HOW_IT_WORKS_TECHNICAL_2026-04-05.md)
- [SETUP_GUIDE_2026-04-05.md](/C:/HybridRAG_V2/docs/SETUP_GUIDE_2026-04-05.md)
- [WORKSTATION_STACK_INSTALL_2026-04-06.md](/C:/HybridRAG_V2/docs/WORKSTATION_STACK_INSTALL_2026-04-06.md)
- [WORKSTATION_DESKTOP_SETTINGS_FOR_TORCH_INSTALL_2026_04_06.md](/C:/HybridRAG_V2/docs/WORKSTATION_DESKTOP_SETTINGS_FOR_TORCH_INSTALL_2026_04_06.md)
