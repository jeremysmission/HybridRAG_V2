# May 2 Canonical Demo Packet — 2026-04-12

**Status:** Authoritative operator packet as of 2026-04-12 late evening MDT. Use this packet for demo prep until a newer dated canonical packet replaces it.
**Scope:** Counts, claims, guardrails, demo shape, and pre-demo checks.
**Rule:** Do not use older checklist/script/environment docs as live operator truth.

## Current Authoritative Counts

### Corpus scale

- Raw source: ~700 GB
- Unique files after dedup: ~215K
- Successfully parsed: ~93K
- LanceDB chunks: **10,435,593**

### Current repo-local store at `C:\HybridRAG_V2\data\index`

- Entity rows in `entities.sqlite3`: **19,959,604**
- Relationships in `relationships.sqlite3`: **59**
- Extracted table rows in `entities.sqlite3`: **0**

### Current entity mix

- ORG: 5,840,183
- DATE: 4,651,727
- PERSON: 2,851,865
- PART: 2,830,083
- CONTACT: 2,540,033
- SITE: 1,095,111
- PO: 150,602

### Read this correctly

- Higher entity-row volume does **not** mean aggregation is clean.
- Broad `PART` and `PO` aggregation is still unsafe until the Tier 2 fix, clean Tier 1 rerun, and production eval on the cleaned store are complete.
- Relationships remain extremely thin at `59`; do not present relationship-backed reasoning as solved.

## What V2 Can Honestly Claim Now

- V2 retrieves over a **real 10.4M-chunk corpus** on local hardware.
- Hybrid retrieval is demoable on a tightly scoped script: latest production-eval evidence supports **20/25 top-1** and **25/25 top-5 family-level retrieval coverage**.
- Rehearsed retrieval-first questions in logistics, field engineering, cybersecurity, and selected PM lanes are the safest current proof.
- The architecture is **local-first and portable**. The core retrieval plane does not require a managed platform subscription.

## What V2 Must Not Claim Yet

- Do **not** claim broad corpus-wide `PO` or `PART` counts are trustworthy.
- Do **not** say aggregation is solved or that V1's failure mode is fully closed.
- Do **not** sell the router as production-grade; latest documented routing accuracy is **12/25 correct (48%)**.
- Do **not** promise "ask anything" or open audience-choice early.
- Do **not** imply relationship-backed reasoning is complete while relationships remain thin.
- Do **not** use "restricted-ready," "GovCloud-ready," or "zero-cost" language unless separately re-verified for the actual demo environment.

## Safest Demo Shape Right Now

### Default live shape as of tonight

1. Open with one business-relevant retrieval win.
2. Run two more rehearsed persona modules from logistics, field, or cyber.
3. Show one deliberate trust-boundary moment: refusal, partial answer, or source-evidence fallback.
4. End with deployment, portability, and cost framing.
5. Keep aggregation out of the live path unless the gates below close.

### Conditional upgrade path before May 2

Use the planned **2 canary-backed validation controls + 3 narrow real-scoped manual counts** only after all of the following are true:

- Tier 2 OOM issue is resolved.
- Clean Tier 1 rerun is complete on the authoritative store.
- Production eval is rerun on the cleaned store.
- VALCAN pack is injected and verified.
- The five-query pack passes rehearsal end to end.

### If those gates do not close

Run a **retrieval-first demo only**. That is the honest fallback.

## Required Pre-Demo Health Checks

- `Installer`: `scripts\verify_install.py` passes on the primary machine and backup machine.
- `Store counts`: chunk count matches the current frozen packet count; entity and relationship counts match the latest dated packet for the machine being used.
- `Indices`: `scripts\health_check.py` runs clean and hybrid retrieval works on two known-good queries.
- `GPU / runtime`: `torch.cuda.is_available()` is true, the intended single GPU is selected, and background jobs are not contending with the demo path.
- `Query pack`: every scripted query passes on the actual demo machine the same day.
- `Canary gate`: if aggregation is included, both canary controls and all three narrow real-scoped checks must pass before rehearsal is signed off.
- `Freeze`: once counts and queries are green, freeze the demo machine and stop ad hoc data or installer changes.

## Stop Conditions

Stop and re-freeze the packet if any of the following happen:

- chunk-count drift
- entity-count drift without an intentional rerun
- failed installer verification
- failed scripted query
- failed canary validation
- last-minute machine swap without a fresh health check

## Source Basis

- `docs/COORDINATOR_STATE_2026-04-11.md`
- `docs/CRASH_RECOVERY_2026-04-12.md`
- `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md`
- `docs/DEMO_DAY_RESEARCH_2026-04-12.md`
- `docs/CANARY_INJECTION_METHODOLOGY_2026-04-12.md`
- Live probe on 2026-04-12 late evening: LanceDB count plus SQLite entity, relationship, and extracted-table counts from `C:\HybridRAG_V2\data\index`
