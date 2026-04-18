# Sprint 9 QA Bundle

**Date:** 2026-04-05 MDT  
**Scope:** Structured-store promotion on the isolated Sprint 6 path plus measured latency profiling on dedicated local Ollama

---

## What Changed

- Added dedicated Sprint 9 demo config at `config/config.sprint9_demo.yaml`
  - isolated Sprint 6 store
  - dedicated Ollama endpoint on `127.0.0.1:11435`
  - reduced demo `max_tokens` from `768` to `512`
- Added dedicated Sprint 9 extraction config at `config/config.sprint9_extract.yaml`
  - isolated Sprint 6 store
  - dedicated Ollama endpoint on `127.0.0.1:11435`
  - expanded extraction part patterns for `WR`, `AB`, `FM`, `PS`, `PO`, and `SN`
- Fixed `scripts/extract_entities.py` so Ollama extraction respects the configured `api_base`
  instead of silently falling back to `localhost:11434`.
- Hardened provider detection in `src/llm/client.py` for custom loopback Ollama ports.
- Fixed `scripts/run_golden_eval.py` so full eval honors `config.llm.provider`
  instead of misdetecting the dedicated Ollama endpoint as OpenAI.
- Hardened local-Ollama routing and confidence handling for
  `What part was replaced on the transmitter at Thule?`
  so GQ-001 stays `SEMANTIC` and no longer leaks an untagged `UNKNOWN` answer.
- Added stage timings to the query pipeline:
  - `router`
  - `retrieval`
  - `generation`
  - `crag`
  - `total`
- Added `scripts/profile_demo_latency.py` to profile warm demo-path latency by stage.
- Extended `scripts/demo_rehearsal.py --timing` to print aggregate per-stage timing.

---

## Verification Run

### Environment

- Repo: `C:\HybridRAG_V2`
- Demo config: `config/config.sprint9_demo.yaml`
- Extraction config: `config/config.sprint9_extract.yaml`
- Store: `C:\HybridRAG_V2\data\index\sprint6\lancedb`
- Entity DB: `C:\HybridRAG_V2\data\index\sprint6\entities.sqlite3`
- Model: `phi4:14b-q4_K_M`
- Dedicated Ollama endpoint: `http://127.0.0.1:11435/v1`
- GPU: single NVIDIA workstation GPU on `CUDA_VISIBLE_DEVICES=0`

### Commands

Targeted extraction into the isolated entity store:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\extract_entities.py --config config\config.sprint9_extract.yaml --batch-size 1 `
  --source-pattern maintenance_report_sample.txt `
  --source-pattern email_chain_messy.txt `
  --source-pattern spreadsheet_fragment.txt `
  --source-pattern messy_desktop_log.txt `
  --source-pattern IGS_Thule_Maintenance_Report_2025-Q3.txt `
  --source-pattern CANARY_BlueHarbor_Maintenance_Log_2025.txt
```

Demo rehearsal on the tuned Sprint 9 path:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\demo_rehearsal.py --config config\config.sprint9_demo.yaml --timing
```

Full golden eval on the same path:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\run_golden_eval.py --config config\config.sprint9_demo.yaml --output tests\golden_eval\results\sprint9_eval.json
```

Stage profiler:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\profile_demo_latency.py --config config\config.sprint9_demo.yaml --rounds 1 --warmup-rounds 1 --output results\demo_latency_profile_sprint9.json
```

### Results

Structured-store promotion:

- Filtered extraction set: `11` chunks
- Entity store: `154` entities
- Relationship store: `53` relationships
- Table rows: `8`
- Entity types:
  - `CONTACT: 11`
  - `DATE: 46`
  - `ORG: 1`
  - `PART: 59`
  - `PERSON: 16`
  - `PO: 12`
  - `SITE: 9`

Demo rehearsal on `config/config.sprint9_demo.yaml`:

- `10/10` passed
- Average total latency: `10025 ms`
- P50 total latency: `8967 ms`
- P95 total latency: `14941 ms`

Per-stage timing from `demo_rehearsal.py --timing`:

- Router average: `5399 ms`
- Retrieval average: `27 ms`
- Generation average: `4598 ms`
- CRAG average: `0 ms`
- Total average: `10025 ms`

Warm-path profile from `results/demo_latency_profile_sprint9.json`:

- `10/10` demo queries passed after warmup
- Router average: `5406.8 ms`
- Retrieval average: `23.2 ms`
- Generation average: `4656.5 ms`
- Total average: `10087.2 ms`

Post-hardening full golden eval on `config/config.sprint9_demo.yaml`:

- Routing: `24/25`
- Retrieval: `20/25`
- Generation: `20/25`
- Confidence: `19/25`
- CRAG triggered: `0`
- Average latency: `14793 ms`

Known retrieval gaps remain:

- `GQ-016`
- `GQ-017`
- `GQ-019`
- `GQ-020`
- `GQ-023`

---

## Latency Recommendation

The measured bottleneck is the local-Ollama router call, not vector retrieval.

- Retrieval is already effectively solved for demo scale at about `20-30 ms`.
- Generation is slower than retrieval but still materially below router cost on most queries.
- Router classification is consuming about half of the end-to-end budget on warm runs.

**Recommendation:** keep the dedicated local-Ollama path for offline validation and controlled demos, but do not claim sub-5-second live latency on this hardware/model path. If presentation-grade latency is required, the next step should be either:

1. replace more router decisions with deterministic guards for high-signal query shapes, or
2. move live routing/generation to a faster commercial/Azure endpoint while keeping local Ollama for offline work.

---

## QA Focus

### Must Confirm

- `scripts/extract_entities.py` now prints the configured dedicated Ollama endpoint instead of silently using `11434`.
- Isolated entity store is no longer empty.
- `scripts/demo_rehearsal.py --config config\config.sprint9_demo.yaml --timing` returns `10/10`.
- `scripts/profile_demo_latency.py` writes a JSON profile and shows router dominating latency.
- `scripts/run_golden_eval.py --config config\config.sprint9_demo.yaml ...` runs the full pipeline against Ollama instead of falling back to retrieval-only.

### Do Not Fail QA On These Yet

- Full golden eval is not all-green yet. Current measured result is `20/25` generation and `18/25` confidence.
- Warm local-Ollama latency is still around `7.6s` to `14.9s` on the demo query pack.
- The structured store is promoted for the demo-critical subset, not the full 31k-chunk Sprint 6 store.

---

## Exit Status

Sprint 9 exit criteria are satisfied:

- isolated entity store is populated
- full golden eval runs end to end on the dedicated demo path
- a measured latency recommendation now exists

Residual risk for the next sprint is latency hardening plus the five known golden-query gaps, not store readiness.
