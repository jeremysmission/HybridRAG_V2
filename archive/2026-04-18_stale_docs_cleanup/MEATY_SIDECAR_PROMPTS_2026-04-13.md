# Meaty Sidecar Prompts — 2026-04-13

Use this file when you want one more heavy round of research sidecars.

Recommended priority:

1. `PRE_DEMO_RETRIEVAL_ARCHITECTURE_RESEARCH`
2. `OCR_TABLE_STACK_GO_NO_GO`
3. `EXTRACTION_ORACLE_AND_OSS_READINESS`

---

## 1. OCR / Table Stack Go-No-Go

```text
===== BEGIN AGENT PROMPT: OCR_TABLE_STACK_GO_NO_GO =====

You are a read-only research lane.

Canonical repos:
- C:\CorpusForge
- C:\HybridRAG_V2

Goal:
Determine whether a targeted OCR/table-parsing pilot is worth doing before May 2, and if so, which stack should be piloted first.

You MUST use web search.
Prioritize primary sources:
- official repos/docs
- benchmark papers
- official issue trackers/discussions
Use forum/community posts only as anecdotal deployment evidence, clearly labeled.

Read first:
- C:\HybridRAG_V2\COORDINATOR_FIRST_READ_HANDOVER_2026-04-13.md
- C:\HybridRAG_V2\docs\CORPUS_FAMILY_BURDEN_RECON_2026-04-13.md
- C:\HybridRAG_V2\docs\LANE3_OPERATOR_INSTALLER_PREFLIGHT_EVIDENCE_2026-04-13.md
- C:\CorpusForge\docs\FORGE_V2_METADATA_CONTRACT_2026-04-12.md
- current OCR/precheck/parser files in CorpusForge

Research targets:
- Docling
- Marker
- MinerU
- OmniDocBench
- any strong official OCR/table pipeline that is realistically on-prem / workstation-usable

Tasks:
1. Map which corpus families are most likely under-extracted because OCR/table parsing is still weak.
2. Compare current Forge OCR path vs latest external/open stacks.
3. Judge Windows/workstation feasibility, GPU needs, CPU fallback, output formats, licensing, and operational complexity.
4. Decide whether the best pilot is:
   - scanned PDFs
   - DD250s
   - packing lists
   - calibration logs
   - another family
5. Estimate the real downstream cost of adopting any OCR win:
   - re-parse
   - re-chunk
   - re-embed
   - re-export
   - V2 re-import
6. Produce one pre-May-2 recommendation and one post-May-2 recommendation.
7. Explicitly say what is not worth touching yet.

Output wanted:
1. Executive summary
2. Family-by-family OCR/table opportunity matrix
3. Tool comparison matrix
4. Recommended pilot order
5. Go / no-go for pre-May-2 OCR work
6. Biggest hidden OCR/value gap

Success condition:
The coordinator can decide whether to spend time on OCR/table stack changes or defer them confidently.

===== END AGENT PROMPT: OCR_TABLE_STACK_GO_NO_GO =====
```

---

## 2. Pre-Demo Retrieval Architecture Research

```text
===== BEGIN AGENT PROMPT: PRE_DEMO_RETRIEVAL_ARCHITECTURE_RESEARCH =====

You are a read-only research lane.

Canonical repo:
- C:\HybridRAG_V2

Goal:
Use current repo evidence plus latest retrieval/GraphRAG/reranking research to decide the best honest pre-demo retrieval architecture moves.

You MUST use web search.
Prioritize primary sources:
- papers
- official repos
- official benchmark/eval work
Do not rely on vague blogspam.
Use secondary commentary only if clearly labeled and only to support, not anchor, a claim.

Read first:
- C:\HybridRAG_V2\COORDINATOR_FIRST_READ_HANDOVER_2026-04-13.md
- C:\HybridRAG_V2\docs\FORGE_TO_V2_TYPED_METADATA_MIGRATION_PLAN_2026-04-13.md
- C:\HybridRAG_V2\docs\AGGREGATION_UNLOCK_AUDIT_2026-04-13.md
- C:\HybridRAG_V2\docs\PRODUCTION_WORKSTATION_PROMOTION_AUDIT_2026-04-13.md
- C:\HybridRAG_V2\docs\LANE1_QA_REPORT_2026-04-13.md
- C:\HybridRAG_V2\docs\PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md
- C:\HybridRAG_V2\docs\PRODUCTION_EVAL_DELTA_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md
- C:\HybridRAG_V2\docs\PRODUCTION_EVAL_RESULTS_POST_CDRL_PATH_PATCH_400_2026-04-13.md
- C:\HybridRAG_V2\docs\production_eval_results_lane1_retrieval_router_400_2026-04-13.json
- C:\HybridRAG_V2\docs\production_eval_results_post_cdrl_path_patch_400_2026-04-13.json
- relevant files under C:\HybridRAG_V2\src\query\
- relevant files under C:\HybridRAG_V2\src\store\

Evidence rules:
- Treat repo evidence as ground truth for what the system currently does.
- Treat web research as guidance for what is worth changing next, not proof that the repo already implements it.
- If repo artifacts conflict with each other, call out the conflict explicitly and state which artifact you trust more and why.
- Every non-repo factual claim from web research must include source name, publication/update date, and URL.

Tasks:
1. Evaluate the repo’s current thesis: “most aggregation pain is normalization/metadata/row-substrate before graph.”
2. Research latest evidence on:
   - RAG vs GraphRAG
   - efficient graph retrieval
   - metadata filtering
   - hybrid reranking
   - candidate grouping / path-aware retrieval
3. Turn that into a concrete pre-demo architecture ladder:
   - what should land before May 2
   - what should explicitly wait
4. Focus especially on:
   - latency reduction
   - cyber regression avoidance
   - typed metadata consumption
   - path-aware candidate control
   - rerank budget discipline
5. Give 5-10 ranked experiments/design moves with expected impact, latency effect, implementation scope, and risk.
6. Explicitly say what would be overkill or fake sophistication right now.

Output wanted:
1. Executive summary
2. Repo-grounded current-state assessment
3. Latest-research synthesis with dated citations
4. Pre-demo architecture ladder
5. Ranked top 5-10 moves
6. What to defer until after May 2
7. Biggest mistaken instinct to avoid
8. Source appendix with grouped repo evidence and web evidence

Success condition:
The coordinator gets a research-backed answer to “what retrieval architecture work is actually worth doing next?”

===== END AGENT PROMPT: PRE_DEMO_RETRIEVAL_ARCHITECTURE_RESEARCH =====
```

---

## 3. Extraction Oracle / OSS Readiness

```text
===== BEGIN AGENT PROMPT: EXTRACTION_ORACLE_AND_OSS_READINESS =====

You are a read-only research/design lane.

Canonical repos:
- C:\HybridRAG_V2
- C:\CorpusForge

Goal:
Design the strongest possible development extraction bakeoff using gpt-4o as the oracle, current local extraction as baseline, and future OSS/AWS extraction as the decision target.

You MUST use web search.
Prioritize primary sources:
- official model repos/docs
- official papers
- official benchmarks
You may include forum anecdotes only in a clearly labeled “deployment notes” section.

Read first:
- C:\HybridRAG_V2\COORDINATOR_FIRST_READ_HANDOVER_2026-04-13.md
- C:\HybridRAG_V2\docs\METADATA_MIGRATION_IMPLEMENTATION_2026-04-13.md
- C:\HybridRAG_V2\docs\CORPUS_FAMILY_BURDEN_RECON_2026-04-13.md
- current extraction code in V2
- any GLiNER / skip-signal / installer evidence docs

Tasks:
1. Define the best 50-100 hard-chunk sample for a dev bakeoff.
2. Pick the hardest families/fields:
   - logistics rows
   - procurement
   - CAP / IGSI
   - A027 subtype
   - OCR-damaged chunks
   - other high-value hard cases
3. Research current official capability of:
   - GLiNER
   - GLiREL or relation-extraction analogs
   - structured extraction in document parsers like Marker/Docling/MinerU where relevant
4. Design the bakeoff:
   - schema
   - prompts
   - scoring
   - field-level pass/fail
   - ambiguity handling
5. Tell us what this bakeoff can actually answer about:
   - local extraction quality ceiling
   - likely OSS 20b / 120b viability later on AWS
   - what still truly needs premium extraction
6. Produce an execution plan that is honest about cost, sample size, and expected learning value.

Output wanted:
1. Executive summary
2. Hard-chunk sample design
3. Field/schema evaluation plan
4. Model/tool comparison frame
5. What gpt-4o oracle evaluation should answer
6. What OSS/AWS decision it enables
7. Biggest hidden mistake to avoid in the bakeoff

Success condition:
The coordinator can launch a high-value extraction bakeoff instead of vaguely “trying gpt-4o on some chunks.”

===== END AGENT PROMPT: EXTRACTION_ORACLE_AND_OSS_READINESS =====
```

---

## Why These 3

- OCR/table stack is informed by current official tools and benchmarks:
  - Docling: https://github.com/docling-project/docling
  - Marker: https://github.com/VikParuchuri/marker
  - MinerU: https://github.com/opendatalab/MinerU
  - OmniDocBench: https://github.com/opendatalab/OmniDocBench

- Retrieval architecture should be grounded in official research:
  - RAG vs GraphRAG: https://arxiv.org/abs/2502.11371
  - Efficient KG retrieval for enterprise RAG: https://arxiv.org/abs/2507.03226
  - HYRR reranking: https://aclanthology.org/2024.lrec-main.748/

- Extraction bakeoff should anchor on official GLiNER sources:
  - GLiNER paper: https://aclanthology.org/2024.naacl-long.300/
  - GLiNER repo: https://github.com/urchade/GLiNER
  - GLiREL repo: https://github.com/jackboyla/GLiREL
