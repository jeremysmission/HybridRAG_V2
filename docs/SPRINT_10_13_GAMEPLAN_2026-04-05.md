# Sprint 10-13 Game Plan

**Date:** 2026-04-05 MDT  
**Prepared during:** Sprint 9 closeout  
**Purpose:** Next four-sprint plan after isolated structured-store promotion and latency profiling

---

## Current-State Summary

- The isolated Sprint 6 demo store is now dual-path:
  - vector store populated
  - structured store partially promoted for the demo-critical subset
- Full golden eval now runs end to end on dedicated local Ollama.
- The main remaining bottleneck is router latency on local Ollama, not retrieval.
- Five golden-query gaps remain:
  - `GQ-016`
  - `GQ-017`
  - `GQ-019`
  - `GQ-020`
  - `GQ-023`

---

## Sprint 10: Router Latency Reduction

### Goal

Cut warm demo-path latency by reducing or bypassing the expensive local-Ollama router step for high-signal query shapes.

### Work Items

1. Profile router prompts and responses for token volume.
2. Expand deterministic guards for the most common demo and golden-query patterns.
3. Add a router-only benchmark so routing latency can be measured independently.
4. Re-run the demo query pack and compare:
   - routing correctness
   - total latency
   - router-stage latency

### Exit Criteria

- Router average latency is materially reduced on the demo query pack.
- Routing correctness does not regress on the golden set.

---

## Sprint 11: Retrieval Gap Closure

### Goal

Close the five known Sprint 9 gaps without regressing the existing 20/25 retrieval pass rate.

### Work Items

1. Inspect the failing queries and identify whether each miss is:
   - corpus gap
   - retrieval issue
   - routing issue
   - structured-store gap
2. Promote any missing structured facts needed for:
   - Mike Torres contact email
   - AB-115 site distribution
   - cancelled purchase orders and reasons
   - cross-corpus unique part rollups
3. Add query-specific regression probes for the five failing IDs.

### Exit Criteria

- The five named queries improve or are explicitly explained by corpus limits.
- Retrieval pass rate improves beyond the current `20/25`.

---

## Sprint 12: Full Structured Promotion

### Goal

Move from demo-critical structured extraction to a broader isolated-store promotion with repeatable index and store hygiene.

### Work Items

1. Expand extraction coverage beyond the current 11-chunk subset.
2. Add a controlled promotion checklist for:
   - chunk-source selection
   - extraction run
   - entity/relationship/table counts
   - rerun idempotency
3. Validate that structured queries improve on the larger promoted slice.

### Exit Criteria

- Structured store is promoted on a materially larger source slice.
- Idempotent reruns are documented and verified.

---

## Sprint 13: Demo Endpoint Decision And Deployment Path

### Goal

Make the final call on demo serving architecture and prove the chosen path is launchable and supportable.

### Work Items

1. Compare dedicated local Ollama against a commercial/Azure endpoint for:
   - latency
   - routing stability
   - generation quality
   - operator complexity
2. Refresh wheel bundles for the promoted build.
3. Update operator docs for the selected demo path.
4. Add a smoke-gate command that a non-author can run before a live demo.

### Exit Criteria

- A single demo-serving recommendation is documented.
- The chosen path has a repeatable startup and smoke-check flow.

---

## Guiding Principle

Do not spend more time on prompt cosmetics while router latency remains the dominant cost center. The data now says the next wins are architectural:

- cheaper routing
- broader structured coverage
- explicit endpoint choice for demo use
