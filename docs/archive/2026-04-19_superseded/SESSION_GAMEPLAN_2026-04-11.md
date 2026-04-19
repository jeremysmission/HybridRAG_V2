# Session Game Plan — 2026-04-11

> WARNING: Historical recovery note. Useful context, but not the current source of truth for readiness, recovery sequence, or demo posture.
> Start instead with `docs/SOURCE_OF_TRUTH_MAP_2026-04-12.md` and `docs/REBOOT_HANDOVER_2026-04-13.md`.

**Purpose:** Crash-safe recovery doc. If the session or machine dies, this is the quickest way to resume.

---

## Hardware Available

| Machine | GPU | Role | Status |
|---------|-----|------|--------|
| primary workstation (here) | NVIDIA workstation desktop GPUs (24GB each), 64GB RAM | Dev/lab — validate architecture, tune, extract | ACTIVE |
| Workstation Desktop | RTX A4000 (20GB), 64GB RAM | Clean production runs, 24-48h unattended, AWS access | AVAILABLE (10 min drive) |
| Workstation Laptop | RTX 3000 Pro, 64GB RAM | V2 query testing, code review, AWS access | BESIDE USER |
| AWS SageMaker | OSS-20B + OSS-120B (GovCloud) | Tier 3 heavy extraction, 150K TPM / 5M TPH | NEEDS WIRING |

### primary workstation GPU Assignment

- **GPU 0:** High overhead from desktop processes (browser, VPN, Ollama, etc). Measured 1.64x slower than GPU 1 on identical embed workloads. Use for lighter/non-latency-critical work.
- **GPU 1:** Clean, low baseline VRAM. Use for all fast/heavy GPU work (embedding, GLiNER, extraction).
- Evidence: `{USER_HOME}\overnight_gpu\lane1\` and `{USER_HOME}\overnight_gpu\lane2\` benchmark reports.

### Agent Capacity

- 4 agents available for divide-and-conquer parallel work
- Use numeric lane naming only (Lane 1, Lane 2, Lane 3, Lane 4)
- Each agent signs every post with agent name
- GPU-backed lanes go to GPU 1 unless specifically isolated

### Backup Repos on primary workstation

- `C:\HybridRAG3_Educational` — V1 legacy, prior art for GUI/admin/scheduling patterns
- `C:\CorpusForge` — primary Forge repo
- `C:\HybridRAG_V2` — primary V2 repo

## Assets on E: Drive

| Path | What | Size |
|------|------|------|
| `E:\CorpusTransfr\verified\IGS\` | Full raw 700GB source (430,540 files, includes dupes) | 710GB |
| `E:\CorpusIndexEmbeddingsOnly\export_20260411_0720\` | Overnight index: 10,435,593 chunks + vectors, no enrichment/extraction | 30GB |
| Free space | | 191GB |

## Contamination Rule

- primary workstation = lab only. No primary workstation artifacts go to work machines as-is.
- Only push code/config/docs to remote. Work machines reproduce clean runs from their own source.

## Task Status (check task list for live state)

### P0 — Import & Extract (primary workstation)

1. **Import 10.4M into V2 LanceDB** — IN PROGRESS
   - Command: `.venv/Scripts/python.exe scripts/import_embedengine.py --source "E:/CorpusIndexEmbeddingsOnly/export_20260411_0720" --create-index`
   - Expected: ~25-40 min total (import + index build)
   - Recovery: backup at `data/index/lancedb_pre_10M_20260411`, just rename back if needed

2. **Tier 1 regex extraction** — BLOCKED on #1
   - Command: `.venv/Scripts/python.exe scripts/tiered_extract.py --tier 1`
   - Expected: ~30 seconds

3. **Tier 2 GLiNER on GPU 1** — BLOCKED on #2
   - Command: `CUDA_VISIBLE_DEVICES=1 .venv/Scripts/python.exe scripts/tiered_extract.py --tier 2`
   - Expected: ~1-2 hours background

### P1 — Retrieval Quality (primary workstation foreground)

4. **Refresh golden eval queries** — BLOCKED on #1
5. **Test retrieval quality with real queries** — BLOCKED on #1, #4
6. **Validate regex patterns against output** — BLOCKED on #2

### P2 — Production Push

7. **Push validated code/config** — BLOCKED on #6
8. **Prepare workstation desktop run** — BLOCKED on #7

## If Recovery Needed

1. Open this file
2. Check task list status
3. If import was interrupted: `data/index/lancedb_pre_10M_20260411` is the safe rollback
4. Open: `C:\HybridRAG_V2\docs\SOURCE_OF_TRUTH_MAP_2026-04-12.md`
5. Resume from the first incomplete task after checking `C:\HybridRAG_V2\docs\REBOOT_HANDOVER_2026-04-13.md`

## Key Reference Files

- Import guide: `C:\HybridRAG_V2\docs\HOW_TO_IMPORT_FORGE_EXPORT_TO_V2_LANCEDB.md`
- Tiered extraction strategy: `C:\HybridRAG_V2\docs\REGEX_PREEXTRACTION_ASSESSMENT_2026-04-08.md`
- Tiered plan: `C:\HybridRAG_V2\docs\OPERATION_FREELOAD_TIERING_AND_REASSEMBLY_2026-04-06.md`
- Field mining playbook: `C:\CorpusForge\docs\FIELD_MINING_PLAYBOOK_2026-04-09.md`
- Corpus metadata captures: `{USER_HOME}\corpus_metadata_capture_2026-04-10\`
- Pipeline throughput guide: `C:\HybridRAG_V2\docs\PIPELINE_STAGES_AND_THROUGHPUT_2026-04-05.md`

Signed: CoPilot+ | Coordinator | 2026-04-11 MDT
