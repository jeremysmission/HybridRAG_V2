# Sprint 8 QA Bundle

**Date:** 2026-04-05 MDT  
**Scope:** Demo gate and delivery hardening on the isolated Sprint 6 store using dedicated local Ollama

---

## What Changed

- Added dedicated demo config at `config/config.sprint8_demo.yaml`
  - isolated store
  - dedicated Ollama endpoint on `127.0.0.1:11435`
  - demo-only `max_tokens: 768`
- Added dedicated local Ollama manager at `scripts/manage_demo_ollama.py`
  - auto-picks the less-busy GPU
  - isolates demo serving on its own port
  - preloads model and pins it in memory
- Added live demo gate at `scripts/demo_gate.py`
  - store/index readiness
  - skip-file acknowledgment
  - `/health`, `/query`, `/query/stream` checks
- Hardened local-Ollama routing and confidence handling
  - deterministic router guards for demo-critical query shapes
  - targeted semantic retrieval guard for broad "general condition" prompts
  - structured/direct-fact confidence normalization
  - stream endpoint now emits normalized confidence

---

## Verification Run

### Environment

- Repo: `C:\HybridRAG_V2`
- Config: `config/config.sprint8_demo.yaml`
- Model: `phi4:14b-q4_K_M`
- Dedicated Ollama port: `11435`
- Dedicated API port: `8002`
- Store: `C:\HybridRAG_V2\data\index\sprint6\lancedb`

### Commands

Start or confirm dedicated Ollama:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\manage_demo_ollama.py start --gpu auto --port 11435 --model phi4:14b-q4_K_M --context-length 8192
.venv\Scripts\python.exe scripts\manage_demo_ollama.py status --port 11435
```

Run the full demo rehearsal:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\demo_rehearsal.py --config config\config.sprint8_demo.yaml --timing
```

Run the live API gate:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\demo_gate.py --config config\config.sprint8_demo.yaml --start-server --server-timeout 120 --manifest C:\CorpusForge\data\output\sprint6_scale_subset_20260405_1810\export_20260405_1753_dedup\manifest.json --json-output results\demo_gate_report_sprint8.json
```

### Results

Full 10-query rehearsal:

- `10/10` passed
- Average latency: `9958.9 ms`
- P50 latency: `8972 ms`
- Min latency: `7544 ms`
- Max latency: `14861 ms`

Per-query live rehearsal:

- Q1 `PASS` in `7544 ms`
- Q2 `PASS` in `7862 ms`
- Q3 `PASS` in `10923 ms`
- Q4 `PASS` in `8738 ms`
- Q5 `PASS` in `14607 ms`
- Q6 `PASS` in `7617 ms`
- Q7 `PASS` in `10631 ms`
- Q8 `PASS` in `14861 ms`
- Q9 `PASS` in `9206 ms`
- Q10 `PASS` in `7600 ms`

Live API gate:

- Store rows: `31608`
- Vector index: present
- Index ready: `True`
- Indexed rows: `31608`
- Unindexed rows: `0`
- `/health`: `ok`
- `/query` smoke: `PASS`
- `/query/stream` contract: `PASS`
- Gate verdict: `PASS`

Skip-file acknowledgment now locked to:

> For the current proof subset, 324 supported files were staged. 293 parsed successfully and produced 32,043 raw chunks. 31 files failed parsing and remain tracked for follow-up. Full-corpus deferred categories still include CAD, encrypted, and skip-list formats, and those are being tracked rather than silently dropped.

---

## QA Focus

### Must Confirm

- Dedicated Ollama can be started on the less-busy GPU and stays isolated from other workloads.
- `scripts/demo_rehearsal.py --config config\config.sprint8_demo.yaml --timing` returns exit code `0`.
- `scripts/demo_gate.py ... --start-server ...` returns gate verdict `PASS`.
- `/query/stream` still emits `metadata` first and `done` before `[DONE]`.
- Q5 stays complete on facts:
  - `SN-2847`
  - `noise floor`
  - `CH3`
  - `filter module`
  - `corrosion`
- Q8 stays `PARTIAL` and includes both `maintenance` and `repair`.
- Q9 stays `HIGH` confidence even if the model text still begins with `[PARTIAL]`.

### Do Not Fail QA On These Yet

- Warm local-Ollama latency remains above the earlier `5s` story on most queries.
- Entity store remains empty on the isolated Sprint 6 demo store:
  - `entities=0`
  - `relationships=0`
  - `tables=0`

---

## Residual Risk

Sprint 8 is functionally green for demo flow and API contract, but it is not yet performance-green against the earlier sub-5-second aspiration on local Ollama. The dedicated isolated path improved stability and removed the shared-service blocker, but the current warm-path story is roughly `7.5s` to `14.9s` on this hardware/model pairing.

Carry that as the primary Sprint 9 risk.
