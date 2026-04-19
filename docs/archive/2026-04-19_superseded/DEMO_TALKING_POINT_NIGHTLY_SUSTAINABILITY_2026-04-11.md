# Demo Talking Point: Nightly Update Sustainability

**Date:** 2026-04-11
**Author:** Jeremy Randall (CoPilot+)
**Audience:** Civilian enterprises, program managers, logistics leads

---

## The Claim

Once the initial corpus build is complete, **ongoing daily updates can be processed entirely by free offline AI running on a single workstation overnight** — no cloud dependency, no per-query cost, no data leaving the network.

## The Evidence

### Real corpus activity analysis

We analyzed original file modification timestamps across the full 430,540-file production corpus (preserved via atomic transfer with metadata retention):

| Period | Unique Files/Day (avg) | GB/Day (avg) |
|--------|----------------------|-------------|
| 2024 average | ~29 files/day | ~0.12 GB/day |
| 2025 average | ~18 files/day | ~0.07 GB/day |
| 2026 YTD | ~22 files/day | ~0.10 GB/day |

Peak months (bulk deliveries) reach 50-100 files/day. These are rare — 2-3 times per year.

### Nightly processing time for a typical day (~25 files)

| Stage | Method | Time | Cost |
|-------|--------|------|------|
| Delta detection + dedup | Hash-based incremental | ~1 min | $0 |
| Parse + chunk + embed | 27-format parser + GPU embedding | ~2 min | $0 |
| Entity extraction (Tier 1) | Regex pattern matching | <1 sec | $0 |
| Entity extraction (Tier 2) | GLiNER NER model on GPU | ~15 sec | $0 |
| Entity extraction (Tier 3) | phi4:14b local LLM | ~1.8 hours | $0 |
| V2 import + index update | LanceDB incremental insert | ~1 min | $0 |
| **Total** | | **~2 hours** | **$0** |

### What this means for operations

- A standard workstation with a single GPU can sustain nightly updates indefinitely
- No cloud API calls, no token costs, no data egress
- The system is self-contained — suitable for restricted or offline networks
- Bulk delivery months (rare, 2-3x/year) can optionally use the organization's existing AI endpoints for faster processing, then return to offline mode

## How the initial build works differently

The initial 430K-file corpus build is a one-time heavy lift:

| Stage | Time | Method |
|-------|------|--------|
| Dedup (430K → 216K files) | ~2 hours | Hash-based, offline |
| Parse + chunk + embed | ~21 hours | GPU-accelerated, offline |
| Tier 1+2 extraction | ~3 hours | Regex + GLiNER, offline |
| Tier 3 hard tail (~120K chunks) | ~13 hours | Organization AI endpoint, $0 |
| **Total initial build** | **~2 days** | **Mostly offline, $0** |

After that, the nightly delta pipeline keeps the system current at zero ongoing cost.

## Key differentiator

Most enterprise RAG systems require continuous cloud API access for document processing. This system processes documents locally using a tiered extraction strategy where:

- **94% of entities** are extracted by instant regex pattern matching ($0)
- **5% more** are extracted by a lightweight NER model on GPU ($0)
- **Only ~1%** requires LLM reasoning, handled by a free local model overnight

The result: a fully operational document intelligence system that costs nothing to maintain after initial deployment.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-11 MDT
