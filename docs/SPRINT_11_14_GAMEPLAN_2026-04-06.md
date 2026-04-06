# Sprint 11-14 Game Plan

**Date:** 2026-04-06 MDT  
**Prepared during:** Sprint 10 closeout and QA handoff  
**Purpose:** Next four-sprint plan after the isolated Sprint 9/10 path reached a full `25/25/25/25` golden pass.

---

## Current-State Summary

- The isolated Sprint 9 demo path is now golden-green:
  - routing `25/25`
  - retrieval `25/25`
  - generation `25/25`
  - confidence `25/25`
- Deterministic table recovery is now available for row-shaped spreadsheet fragments.
- Full-pipeline eval scoring now reflects the actual routed retrieval context.
- The main remaining weakness is latency, not correctness.

---

## Current Research Notes

### Ollama

- OpenAI-compatible clients should point at a `/v1/` base URL.
  - Source: https://docs.ollama.com/api/openai-compatibility
- Default local API base is `http://localhost:11434/api`, and custom local base URLs remain a first-class pattern.
  - Source: https://docs.ollama.com/api/introduction
- `keep_alive` can keep models hot in memory or unload them immediately; this is the obvious next lever for warm-path latency.
  - Source: https://docs.ollama.com/faq

### LanceDB

- For `IVF_PQ`, LanceDB recommends keeping auto-tuned `nprobes` by default and only increasing it when recall is insufficient.
  - Source: https://docs.lancedb.com/indexing/vector-index
- `refine_factor` reranks extra candidates in memory and is the main recall/latency tradeoff knob during search.
  - Source: https://docs.lancedb.com/indexing/vector-index
- LanceDB OSS supports manual GPU indexing for `IVF_PQ` using the Python SDK.
  - Source: https://docs.lancedb.com/indexing/gpu-indexing

### OpenAI Eval / Agent Safety Guidance

- Use structured outputs between stages to constrain model behavior and data flow.
- Run trace graders and evals at the stage level, not just end to end.
- Harden tool use and prompt-injection boundaries explicitly.
  - Source: https://developers.openai.com/api/docs/guides/agent-builder-safety

---

## Sprint 11: Latency Hardening

### Goal

Reduce warm-path latency without regressing the newly green golden results.

### Work Items

1. Add Ollama model prewarm / keep-alive controls for the dedicated demo endpoint.
2. Separate cold-start latency from steady-state latency in the profiler output.
3. Benchmark router-only and generation-only latency independently.
4. Tune LanceDB search parameters only if recall remains stable:
   - `nprobes`
   - `refine_factor`
5. Add a latency gate report for:
   - cold P50 / P95
   - warm P50 / P95
   - per-stage averages

### Exit Criteria

- Warm demo-path average latency is materially lower than the current ~15s full-eval mean.
- Golden correctness remains at `25/25/25/25`.

---

## Sprint 12: Broader Structured Promotion

### Goal

Promote deterministic and LLM-backed structured extraction beyond the current demo slice.

### Work Items

1. Run a larger isolated structured promotion on a controlled corpus slice.
2. Add source-level reset/idempotency commands for:
   - entities
   - relationships
   - extracted tables
3. Expand deterministic extractors for:
   - spreadsheet fragments
   - repeated report tables
   - contact blocks
4. Validate structured-store counts and duplicate behavior after reruns.

### Exit Criteria

- Structured promotion covers a materially larger source slice than Sprint 10.
- Rerunning promotion on the same slice is clean and documented.

---

## Sprint 13: Eval And Trace Hardening

### Goal

Make the QA harness more diagnostic and less dependent on manual triage.

### Work Items

1. Add stage-level graders for:
   - router
   - retrieval context
   - generation
   - confidence
2. Save retrieval context snapshots per query in golden runs.
3. Add diff-friendly output for regressions between runs.
4. Add prompt-injection and tool-safety regression probes to the QA bundle.

### Exit Criteria

- Golden eval failures identify the failing stage directly.
- QA can compare two runs without manual JSON inspection.

---

## Sprint 14: Deployment Path And Operator Runbook

### Goal

Convert the isolated demo path into a repeatable operator workflow.

### Work Items

1. Refresh wheel bundles after the Sprint 11-13 changes.
2. Document dedicated Ollama startup, warmup, and smoke-check flows.
3. Add one-button or one-command pre-demo validation.
4. Decide whether the isolated demo path remains local-Ollama-only or needs a dual-path deployment recommendation.

### Exit Criteria

- A non-author can start the demo stack, warm it, and smoke-test it from the runbook alone.
- Deployment recommendation is documented with tradeoffs.

---

## Guiding Principle

Do not reopen correctness churn while latency and operator workflow remain the real bottlenecks.

The system is now functionally green. The next four sprints should focus on:

- faster steady-state operation
- broader structured coverage
- better QA diagnostics
- repeatable operator startup and demo readiness
