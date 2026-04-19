# V2 Demo Readiness Gap Analysis — 2026-04-12

**Author:** reviewer  
**Repo:** `C:\HybridRAG_V2`  
**Scope:** Read-only analysis of current V2 demo readiness for the May 2, 2026 demo  
**Bottom line:** **Overall rating = RED for the full V2 story.**  
**Narrower truth:** V2 is **YELLOW for a tightly-scoped retrieval-first demo**, but it is **not yet honest to present the full “aggregation is solved” story** without additional cleanup and rehearsal.

---

## Executive Summary

V2 is no longer in the same category as V1 on raw retrieval. The 10.4M-chunk LanceDB store is real, FTS and IVF_PQ are both working, hybrid retrieval is working end to end, and the current production eval shows **20/25 top-1** and **25/25 top-5 family-level retrieval coverage**. That is enough to demo a serious retrieval system right now.

The problem is that the May 2 demo is not only about retrieval. The claimed V2 differentiators are structured routing, entity-backed answers, and cross-document aggregation. Those are exactly the areas where the evidence is weakest:

1. **Aggregation credibility is RED.** Current Tier 1 entity data is still badly polluted in the two entity classes most likely to drive procurement and parts-count answers: `PART` and `PO`. The latest crash-recovery snapshot states `PART` is roughly **90% polluted** by security standard/SP 800-53 baseline codes and `PO` is roughly **98% polluted** by security control IDs.
2. **Router accuracy is RED.** The first production eval landed **12/25 routing correct (48%)**. That is not a rounding error. It means V2 often gets the right document family despite the router, not because of the router.
3. **Demo operations are still fragile.** Several operator/demo docs are stale enough to cause self-inflicted failure. Some still expect `17,707` chunks and `40,981` entities. The current corpus is `10,435,593` chunks. If someone grabs the wrong checklist on demo day, the system can look broken even when the code is fine.

### Top 3 Gaps

| Rank | Gap | Why it matters | Current severity |
|---|---|---|---|
| 1 | Aggregation honesty | V1 died on aggregation. V2 cannot afford “plausible but polluted” counts. | **RED** |
| 2 | Router behavior | Bad routing increases latency, complicates explanations, and makes the system look less intentional than it is. | **RED** |
| 3 | Demo/operator packaging | Stale scripts, stale counts, and stale runbooks are a stage-risk multiplier. | **YELLOW trending RED** |

### What V2 Can Credibly Demo Right Now

- Fast hybrid retrieval over a **real 10.4M-chunk corpus**
- Exact-token and hybrid wins on logistics, engineering, and cybersecurity identifiers
- Persona-aligned document retrieval for program management, logistics, field engineering, and cybersecurity
- Spreadsheet/tabular retrieval on known-good families
- Honest “retrieval-first” positioning with cited sources

### What V2 Should Not Claim Right Now

- That corpus-wide aggregation counts are trustworthy across parts and purchase-order style entities
- That the router is production-grade across all five query types
- That operator packaging is “fully demo-ready” without a refreshed single-source checklist
- That May 2 can safely include a broad exploratory audience-choice segment without guardrails

### Key Inputs Reviewed

- [RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md](./RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md)
- [PRODUCTION_EVAL_RESULTS_2026-04-11.md](./PRODUCTION_EVAL_RESULTS_2026-04-11.md)
- [PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md](./PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md)
- [COORDINATOR_STATE_2026-04-11.md](./COORDINATOR_STATE_2026-04-11.md)
- [DEMO_TALKING_POINT_NIGHTLY_SUSTAINABILITY_2026-04-11.md](./DEMO_TALKING_POINT_NIGHTLY_SUSTAINABILITY_2026-04-11.md)
- [LAPTOP_10M_INVESTIGATION_2026-04-11.md](./LAPTOP_10M_INVESTIGATION_2026-04-11.md)
- [PHONE_REGEX_FIX_2026-04-11.md](./PHONE_REGEX_FIX_2026-04-11.md)
- [CRASH_RECOVERY_2026-04-12.md](./CRASH_RECOVERY_2026-04-12.md)
- [DEMO_SCRIPT_2026-04-05.md](./DEMO_SCRIPT_2026-04-05.md)
- [DEMO_DAY_CHECKLIST_2026-04-07.md](./DEMO_DAY_CHECKLIST_2026-04-07.md)
- [ENVIRONMENT_ASSUMPTIONS_2026-04-08.md](./ENVIRONMENT_ASSUMPTIONS_2026-04-08.md)
- [GOLDEN_EVAL_TRACEABILITY_2026-04-08.md](./GOLDEN_EVAL_TRACEABILITY_2026-04-08.md)
- [SPRINT_SYNC.md](./SPRINT_SYNC.md)
- `src/query/query_router.py`
- `src/query/pipeline.py`
- `src/query/entity_retriever.py`

---

## Rating Table

| Dimension | Rating | Short read |
|---|---|---|
| 1. Retrieval quality | **YELLOW** | Strong and demoable, but not clean enough to call bulletproof |
| 2. Entity extraction honesty | **RED** | CONTACT improved; PART and PO are still severely polluted |
| 3. Aggregation credibility | **RED** | Unsafe for confident stage claims today |
| 4. Router classification accuracy | **RED** | 48% routing match is not demo-grade |
| 5. Coverage of 5 personas | **YELLOW** | Four personas have usable material; cross-role aggregation is still soft |
| 6. Infrastructure stability | **YELLOW** | Works now, but recent silent failures were real |
| 7. Install reproducibility | **YELLOW** | Better than last week, not fully de-risked |
| 8. Demo-day narrative | **YELLOW** | Credible if narrowed; overclaims still present in older docs |
| 9. Scalability story | **YELLOW** | 10.4M retrieval story is real; 10.4M structured story is not clean yet |
| 10. Unknown stage-failure risk | **RED** | Too many recent “silent” classes to dismiss |

---

## 1. Retrieval Quality — YELLOW

### Assessment

Retrieval is now the strongest part of V2. The current hybrid path is real, not aspirational:

- The primary store is **10,435,593 chunks**.
- FTS is built and working.
- IVF_PQ is built and working.
- The app-path probe showed the same ranked results as the raw LanceDB hybrid path for **25/25** benchmark queries.
- The production eval showed **20/25 top-1 PASS** and **25/25 PASS+PARTIAL in top-5**.

That is enough to demo confidently on rehearsed query families. It is not enough to call retrieval “solved” for all live-stage inputs because:

- The exact-match logistics probe still missed several identifier-heavy PO cases.
- The production eval P95 is still ugly once the router and full app path are included.
- The strongest wins are family-level retrieval, not always exact-answer completeness.

### Evidence

- [RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md](./RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md): hybrid exact-match hit rate improved from **5/12 vector-only** to **8/12 hybrid**, with hybrid **P50 13.7ms / P95 30.3ms** on raw search and app-path **P50 23.2ms / P95 55.6ms**.
- [PRODUCTION_EVAL_RESULTS_2026-04-11.md](./PRODUCTION_EVAL_RESULTS_2026-04-11.md): **PASS 20/25**, **PASS+PARTIAL 25/25**, **MISS 0/25**.
- [COORDINATOR_STATE_2026-04-11.md](./COORDINATOR_STATE_2026-04-11.md): app-path hybrid probe already recorded as **25/25 identical** to raw path.
- `src/query/pipeline.py`: structured paths still run vector search for additional context, which helps retrieval survive imperfect routing.

### Why not GREEN

- Four exact-token misses still exist in the identifier probe.
- Production eval latency is dominated by routing and still spikes into the tens of seconds at P95.
- The current win rate is strong for a rehearsed demo, not for an unconstrained live audience free-for-all.

### Demo implication

Lead with retrieval-backed queries where the expected document family is already proven. Do not open with a fragile structured-count query just because it looks more magical.

---

## 2. Entity Extraction Honesty — RED

### Assessment

This is the clearest integrity problem in the system right now.

The good news:

- CONTACT extraction improved materially.
- The phone regex round 2 fix reduced the earlier CONTACT explosion from **16.1M** to roughly **2.54M actual** on the current workstation store.

The bad news:

- `PART` is currently described as **~90% polluted** by security standard/SP 800-53 baseline codes.
- `PO` is currently described as **~98% polluted** by security control IDs.
- `PERSON` remains thin at **4,788** because Tier 2 GLiNER promotion is not done on the clean store yet.
- Relationships remain tiny relative to corpus size.

This means the entity store is not currently trustworthy as a stage authority for the very entity types that matter most to logistics and aggregation.

### Evidence

- [PHONE_REGEX_FIX_2026-04-11.md](./PHONE_REGEX_FIX_2026-04-11.md): CONTACT false positives were materially reduced; the measured sample reduction was **84.5%**.
- [PRODUCTION_EVAL_RESULTS_2026-04-11.md](./PRODUCTION_EVAL_RESULTS_2026-04-11.md): current store stats show CONTACT **2,540,033**, PART **2,521,235**, PO **150,602**, PERSON **4,788**, relationships still effectively absent from meaningful production answers.
- [PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md](./PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md): explicit caveats say `PO`, `PART`, `SITE`, and `PERSON` anchors are contaminated in ways that break honest ground truthing.
- [CRASH_RECOVERY_2026-04-12.md](./CRASH_RECOVERY_2026-04-12.md): current primary workstation state states `PART` is ~90% polluted and `PO` is ~98% polluted.
- [COORDINATOR_STATE_2026-04-11.md](./COORDINATOR_STATE_2026-04-11.md): only **59 relationships** were present in the earlier state snapshot, reinforcing how immature the structured layer still is.

### Demo implication

Do not treat current entity counts as proof. If the May 2 demo includes entity-backed answers, constrain them to the query families already shown to retrieve the right documents, and frame them as source-grounded retrieval plus partial structure, not as validated enterprise master data.

---

## 3. Aggregation Credibility — RED

### Assessment

This is the single most important readiness call in this memo.

V2 can retrieve documents related to aggregation-style questions. That is not the same thing as being able to give trustworthy aggregate answers.

Right now, the system has three aggregation problems:

1. **Entity pollution:** counts over `PART` and `PO` are unsafe because the extracted entities themselves are polluted.
2. **Relationship poverty:** the relationship layer is still too thin to support confident multi-hop summary answers.
3. **Eval ambiguity:** several aggregation questions PASS at the family-retrieval level while still being explicitly tagged as **Tier 3 LLM gap** or structurally incomplete.

That is exactly the class of failure that kills trust: answers that sound coherent and cite relevant documents, but are not numerically or structurally dependable.

### Evidence

- [PRODUCTION_EVAL_RESULTS_2026-04-11.md](./PRODUCTION_EVAL_RESULTS_2026-04-11.md): aggregation/cross-role persona scored **3 PASS / 2 PARTIAL**, but those passes are still retrieval-family passes, not audited count truth.
- The same doc explicitly tags `PQ-021`, `PQ-022`, `PQ-024`, and `PQ-025` as **TIER3_LLM_GAP**.
- [CRASH_RECOVERY_2026-04-12.md](./CRASH_RECOVERY_2026-04-12.md): the coordinator’s own note says the “aggregation problem” is the biggest risk and that current aggregation queries return polluted counts.
- `src/query/entity_retriever.py`: aggregation is driven by `entity_store.aggregate_entity(...)` and a few special-case helpers. If the store is polluted, the aggregation answer is polluted.

### Rating rationale

This dimension is RED even though some aggregation-style eval items PASS, because the user’s actual decision question is not “can V2 retrieve an aggregation-related document family?” It is “can V2 be trusted not to repeat V1’s failure mode on stage?” The honest answer today is no.

### Demo implication

- Do not lead with aggregation.
- Do not promise corpus-wide counts unless they are canary-backed or post-cleanup revalidated.
- If an aggregation-style query is shown, it must be framed as “document-surfacing across a distributed corpus” unless the count itself has been independently verified.

---

## 4. Router Classification Accuracy — RED

### Assessment

The router is currently the weakest core reasoning component in the live path.

The production eval reported **12/25 routing correct (48%)**. The bad news is worse than the number alone suggests:

- Many semantic or tabular questions get restricted as `COMPLEX`.
- Some queries still PASS because downstream retrieval is resilient.
- The deterministic guard override in `query_router.py` currently applies only when `self.llm.provider == "ollama"`.

That last point matters. It means the code already contains hand-built knowledge about predictable query shapes, but that safety net is not generally applied across providers.

### Evidence

- [PRODUCTION_EVAL_RESULTS_2026-04-11.md](./PRODUCTION_EVAL_RESULTS_2026-04-11.md): **Routing correct 12/25**.
- The same doc shows multiple misses where expected `TABULAR`, `AGGREGATE`, or `SEMANTIC` got routed to `COMPLEX`.
- `src/query/query_router.py`: `_apply_routing_guards()` returns early if `self.llm.provider != "ollama"`.
- `src/query/pipeline.py`: structured queries are cushioned by vector fallback, which is why routing can be bad while retrieval still looks decent.

### Why this is stage-risky

- Bad routing inflates latency.
- Bad routing makes explanations harder because the operator may have to explain away “why did it say COMPLEX for a spreadsheet question?”
- Bad routing increases the chance of a weird answer format even when retrieval finds the right family.

### Demo implication

Stick to queries that already passed end to end, and keep the operator narration retrieval-centric rather than router-centric. The demo cannot rely on the router being a crowd-pleasing explainer yet.

---

## 5. Coverage of the Five Personas — YELLOW

### Assessment

Coverage exists, but it is not equally strong.

| Persona | Current read |
|---|---|
| Program Manager | **YELLOW** — useful material exists, but some PM queries are still partial or route oddly |
| Logistics Lead | **GREEN/YELLOW** — strongest current demo lane |
| Field Engineer | **GREEN/YELLOW** — strong narrative source families |
| Network Admin / Cybersecurity | **YELLOW** — good retrieval, but one partial and some routing drift |
| Aggregation / Cross-role | **RED/YELLOW** — family retrieval exists, but trustable structured conclusions are not ready |

### Evidence

- [PRODUCTION_EVAL_RESULTS_2026-04-11.md](./PRODUCTION_EVAL_RESULTS_2026-04-11.md):  
  Program Manager = **3 PASS / 2 PARTIAL**  
  Logistics = **5 PASS / 0 PARTIAL**  
  Field Engineer = **5 PASS / 0 PARTIAL**  
  Network Admin / Cybersecurity = **4 PASS / 1 PARTIAL**  
  Aggregation / Cross-role = **3 PASS / 2 PARTIAL**
- [GOLDEN_EVAL_TRACEABILITY_2026-04-08.md](./GOLDEN_EVAL_TRACEABILITY_2026-04-08.md): all five personas are mapped to real production families.

### Demo implication

If the user wants the safest current story, the demo should overweight:

- Logistics
- Field engineering
- Cybersecurity

Program management can still appear, but on rehearsed queries only. Cross-role aggregation should be framed as “in-progress structured capability” unless the data cleanup lands before the demo.

---

## 6. Infrastructure Stability — YELLOW

### Assessment

V2 is functional. It is not yet boring.

Recent history contains multiple silent-failure classes:

- FTS was silently broken for **7 days** before the LanceDB single-column API fix.
- Hybrid search was effectively vector-only until the LanceDB 0.30+ builder-chain fix.
- The laptop hit an exact **10,000,000 chunk** truncation state that required a dedicated investigation.
- The early streaming extraction path had a silent fallback to full-memory loading before the iterator path was hardened.

The positive side:

- These issues were actually found.
- The major ones now have fixes and/or instrumentation.
- The current state on the primary workstation shows both FTS and IVF_PQ working.

### Evidence

- [COORDINATOR_STATE_2026-04-11.md](./COORDINATOR_STATE_2026-04-11.md): commit history explicitly calls out the FTS and hybrid fixes.
- [CRASH_RECOVERY_2026-04-12.md](./CRASH_RECOVERY_2026-04-12.md): confirms both indexes are working and retrieval is verified end to end.
- [LAPTOP_10M_INVESTIGATION_2026-04-11.md](./LAPTOP_10M_INVESTIGATION_2026-04-11.md): no confirmed code-side 10M cap, but enough uncertainty existed to justify ingest-completeness verification.
- [CRITICAL_PYLANCE_INSTALL_REQUIRED_2026-04-11.md](./CRITICAL_PYLANCE_INSTALL_REQUIRED_2026-04-11.md): documents the streaming false alarm and the move to a cleaner built-in LanceDB batch path.

### Rating rationale

This is not RED because the system does work now. It is not GREEN because several recent breakages were silent until production-like probing exposed them.

### Demo implication

No live demo should depend on “we’ll probably notice if something drifted.” Pre-demo health checks must be mandatory.

---

## 7. Install Reproducibility — YELLOW

### Assessment

This has improved materially, but it is not fully proven on fresh iron.

The good news:

- Workstation install docs now stress repo-local config, repo-local venvs, proxy-aware pip setup, and explicit CUDA verification.
- `verify_install.py` exists and is wired into the installer.

The remaining risk:

- Some older environment/demo docs are stale.
- The sprint board still contains contradictory or outdated victory language.
- A full “fresh workstation, current corpus, current demo flow” proof is not clearly closed in the mainline evidence pack.

### Evidence

- [WORKSTATION_STACK_INSTALL_2026-04-06.md](./WORKSTATION_STACK_INSTALL_2026-04-06.md): repo-relative configs and installer expectations are now explicit.
- [CRITICAL_PYLANCE_INSTALL_REQUIRED_2026-04-11.md](./CRITICAL_PYLANCE_INSTALL_REQUIRED_2026-04-11.md): the corrected version shows `verify_install.py` is now the dependency truth source.
- [OPERATOR_SURFACE_QA_2026-04-08.md](./OPERATOR_SURFACE_QA_2026-04-08.md): launch-path mismatches and misleading stop behavior were still present in earlier operator QA.
- [ENVIRONMENT_ASSUMPTIONS_2026-04-08.md](./ENVIRONMENT_ASSUMPTIONS_2026-04-08.md) and [DEMO_DAY_CHECKLIST_2026-04-07.md](./DEMO_DAY_CHECKLIST_2026-04-07.md): still reference the obsolete `17,707` / `40,981` world.

### Demo implication

For demo day, one machine must be designated authoritative and verified against the current corpus and current runbook. “Any workstation should work” is not yet a safe assumption.

---

## 8. Demo-Day Narrative — YELLOW

### Assessment

The “why V2” story is much better than the current packaging around it.

The credible parts of the story:

- Real 10.4M-chunk corpus
- Real hybrid retrieval
- Real offline-friendly architecture
- Real workstation-scale economics
- Real separation from vendor-heavy control planes

The weak parts:

- Some older demo docs still assume a much smaller corpus or earlier build states.
- Some existing language still implies aggregation confidence that the data does not justify.
- There is not yet one canonical demo packet that reflects the latest measured reality.

### Evidence

- [DEMO_TALKING_POINT_NIGHTLY_SUSTAINABILITY_2026-04-11.md](./DEMO_TALKING_POINT_NIGHTLY_SUSTAINABILITY_2026-04-11.md): strong narrative for overnight sustainability and local economics.
- [DEMO_SCRIPT_2026-04-05.md](./DEMO_SCRIPT_2026-04-05.md): useful structure, but stale corpus sizes and some risky demo choices remain.
- [DEMO_DAY_CHECKLIST_2026-04-07.md](./DEMO_DAY_CHECKLIST_2026-04-07.md): still tied to obsolete store sizes.
- [SPRINT_SYNC.md](./SPRINT_SYNC.md): still contains “DONE (25/25)” and “Demo rehearsal 10/10” language that no longer describes the stricter current production-eval reality.

### Demo implication

The story is defensible if the team intentionally narrows it to what V2 can prove now. It becomes fragile when older aspirational claims leak into the live script.

---

## 9. Scalability Story — YELLOW

### Assessment

The scalability story is real for ingestion and retrieval. It is not yet equally real for clean structured promotion.

What is solid:

- Importing **10.4M chunks** into LanceDB is documented.
- Query latency on the raw hybrid path is good.
- Storage size and build times are known.

What is not yet equally solid:

- Clean structured extraction over the same scale is still in motion.
- Tier 2 GLiNER promotion is not fully landed on a clean entity store.
- The laptop truncation investigation proves the team still needs ingest-integrity checks instead of trusting completion by feel.

### Evidence

- [IMPORT_BENCHMARK_10M_2026-04-11.md](./IMPORT_BENCHMARK_10M_2026-04-11.md): import budget is roughly **2.5-3 hours** on the tested path, faster from local NVMe.
- [RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md](./RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md): 10.4M retrieval path is fast enough for live demo use.
- [LAPTOP_10M_INVESTIGATION_2026-04-11.md](./LAPTOP_10M_INVESTIGATION_2026-04-11.md): ingest completeness needed explicit verification logic.
- [CRASH_RECOVERY_2026-04-12.md](./CRASH_RECOVERY_2026-04-12.md): Tier 2 GLiNER is still an overnight process and not a completed clean-production story yet.

### Demo implication

It is fair to say “V2 can search a 10.4M-chunk corpus on a workstation.” It is not yet fair to say “V2 has fully clean structured knowledge promotion over that corpus.”

---

## 10. Unknown Failure Modes We Do Not Yet Understand Well Enough — RED

### Assessment

This dimension is RED because the failure classes most likely to surprise the team are exactly the classes already seen in the past week:

- silent API drift
- silent fallback behavior
- stale doc/operator mismatch
- retrieval success masking structured-data weakness

The most dangerous failure on stage is not a loud crash. It is a plausible answer that the operator trusts because retrieval looks healthy.

### Evidence

- [COORDINATOR_STATE_2026-04-11.md](./COORDINATOR_STATE_2026-04-11.md): multiple recent fixes landed only after deeper probing.
- [CRASH_RECOVERY_2026-04-12.md](./CRASH_RECOVERY_2026-04-12.md): explicitly says aggregation is the biggest risk and that demo fallback may need to avoid corpus-wide aggregate claims.
- [OPERATOR_SURFACE_QA_2026-04-08.md](./OPERATOR_SURFACE_QA_2026-04-08.md): operator control and launch-path confusion were real, not hypothetical.

### Demo implication

The demo needs a constrained, rehearsed operating envelope. “Let’s see what the audience asks” is still a risk multiplier, not a flex.

---

## Must Fix Before Demo

| Priority | Fix | Suggested owner | Estimated effort | Why it is must-fix |
|---|---|---|---|---|
| 1 | Clean `PART` / `PO` regex pollution and rerun Tier 1 on the primary workstation | reviewer + coordinator | 0.5-1 day | Without this, aggregation remains untrustworthy |
| 2 | Re-run production eval on the cleaned entity store and explicitly separate retrieval PASS from truthful aggregate-answer PASS | reviewer | 0.5 day | Needed to avoid repeating V1’s failure mode |
| 3 | Tune router behavior for the actual provider path in use, not just local Ollama guards | reviewer | 0.5 day | Current 48% routing match is too weak for a high-stakes live demo |
| 4 | Replace stale demo/operator docs with one canonical May 2 packet | Coordinator + reviewer | 2-4 hours | Current stale docs are a self-own waiting to happen |
| 5 | Designate and verify one authoritative demo machine with pre-demo health checks | Coordinator + operator | 2-4 hours | Prevents “wrong box / wrong store / wrong counts” incidents |

---

## Nice To Fix Before Demo

| Fix | Suggested owner | Estimated effort | Why it helps |
|---|---|---|---|
| Finish Tier 2 GLiNER on the clean store and measure PERSON/ORG/SITE lift | Coordinator + reviewer | 0.5-1 day | Improves entity lookup credibility |
| Add a small canary-backed aggregate pack with independently checked answers | reviewer | 0.5 day | Lets the team show one or two structured wins safely |
| Refresh demo narrative with current 10.4M numbers and current latency numbers | Coordinator + reviewer | 2-3 hours | Stops stale storytelling drift |
| Rehearse explicit recovery scripts for wrong-answer and no-result cases | Coordinator + non-author tester | 1-2 hours | Reduces stage panic |
| Verify fresh install on the workstation desktop against current mainline and current store expectations | Coordinator | 2-4 hours | De-risks failover machine use |

---

## Acceptable Known Limitations

These are limitations the team can disclose honestly without undermining the demo:

- V2’s strongest proof today is retrieval quality over a large corpus, not universally solved aggregation.
- Some entity-backed answers still depend on ongoing structured promotion work.
- Audience free-form questions should be bounded to known personas and source families.
- Offline/GovCloud compatibility is an architectural strength, but the exact remote deployment story is still a separate workstream.
- Nightly sustainability estimates are currently an engineering forecast, not yet a long-horizon production operations report.

---

## Risk Register

| Rank | Risk | Probability | Impact | Why it matters | Mitigation |
|---|---|---|---|---|---|
| 1 | Polluted aggregate answer looks plausible on stage | High | Critical | Repeats V1 trust failure | Remove unsafe aggregate queries until cleanup lands |
| 2 | Router sends a simple query down a weird path | High | High | Adds latency and confusing narration | Use only rehearsed PASS queries; tune provider-path guards |
| 3 | Operator follows a stale checklist with obsolete counts | High | High | Makes the healthy system look broken | Publish one canonical May 2 packet and retire older ones |
| 4 | Silent index/config drift between rehearsal and demo | Medium | High | Retrieval quality silently regresses | Mandatory pre-demo health check: chunk count, indices, sample queries |
| 5 | Tier 2/relationship work is still incomplete, weakening “who/what/why” answers | Medium | High | Structured story feels shallower than promised | Narrow demo to document-grounded retrieval and selected entity lookups |
| 6 | Demo machine mismatch or stale local store | Medium | High | Wrong corpus or wrong counts on stage | Freeze one authoritative machine and one validated backup |
| 7 | Audience asks an out-of-scope exploratory question early | Medium | Medium | Can derail trust before core proof lands | Reserve audience-choice for the end or decline it entirely |
| 8 | Latency spike from LLM/router path | Medium | Medium | Dead air erodes confidence | Lead with low-latency canaries, keep narration retrieval-first |

---

## Recommended Demo Script Sketch

This is a **script sketch**, not a new query pack. Every item below already exists in current V2 artifacts.

| Order | Query ID | Why it is relatively safe now | What it proves |
|---|---|---|---|
| 1 | `PQ-002` | Current PM semantic PASS on production data; ties directly to schedule/status stakeholder value | V2 can answer program-management questions over current reporting artifacts |
| 2 | `PQ-006` | Current logistics TABULAR PASS; grounded in open-purchase spreadsheet families rather than polluted aggregate counts | V2 can retrieve and use spreadsheet-style procurement data, not just prose |
| 3 | `PQ-009` | Current logistics semantic PASS; strong operational/logistics story without risky global counts | V2 can track maintenance-adjacent operational readiness questions |
| 4 | `PQ-013` | Current field-engineering semantic PASS; strong narrative source family | V2 can surface engineering incident history and return-to-service context |
| 5 | `PQ-016` | Current cyber semantic PASS on real security artifacts | V2 can retrieve cybersecurity evidence from the same corpus, not just logistics docs |
| 6 | `PQ-019` | Current cyber TABULAR PASS and useful for compliance/program crossover | V2 can bridge structured compliance artifacts and explanatory retrieval |
| 7 | One rehearsed refusal / out-of-scope query from the existing demo packet | Safe only if picked from an already scripted refusal case | V2 knows when not to guess |

### Queries To Avoid Until Cleanup Lands

- `PQ-011` if the audience will interpret the answer as trustworthy part-failure counting
- `PQ-021` through `PQ-025` if the narration would imply authoritative cross-program aggregation
- Any ad hoc PO/part count question not already canary-verified

---

## What V2 Can Honestly Say On May 2

If the team narrows the script appropriately, V2 can credibly say:

- “This system retrieves from a real 10.4M-chunk corpus, not a toy sample.”
- “Hybrid retrieval and full-text search are working on production-scale data.”
- “We can answer rehearsed program, logistics, field, and cybersecurity questions with sources.”
- “We are deliberately not overselling aggregate counts until the structured cleanup is finished.”

That last sentence is not weakness. It is exactly the kind of honesty that V1 lacked.

---

## Final Recommendation

**Do not treat May 2 as a broad capability showcase yet. Treat it as a controlled proof of large-corpus retrieval plus selected structured wins.**

If the entity cleanup and router tuning land in time, the rating can move from **RED overall** to **YELLOW overall**. If they do not land, the team should still demo V2, but only on a retrieval-first script that explicitly avoids unverified aggregation claims.

That is the honest state tonight.

Signed: reviewer
