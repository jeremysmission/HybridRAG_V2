# Agent Research Standing Orders

**Applies to:** all agents working on HybridRAG V2
**Authority:** Jeremy Randall (project owner)
**Date established:** 2026-04-11

---

## Core principle

Default assumption is that your training data is stale. Before implementing anything non-trivial, web-search to confirm current best practice. **Bias strongly toward recency.**

A technique from 6 months ago is probably outdated. A technique from 2 years ago almost certainly is. Library APIs change quickly (we lost 7 days today to a silent LanceDB 0.30 API break). Research benchmarks are updated continuously. Your mental model from training should be treated as a starting point, not a source of truth.

## Expectations

1. **Meet or exceed industry standard best practices.** When you have a design choice, check what's published recently and pick the current state of the art rather than a pattern you remember.

2. **Cite sources in your handoff notes** using one-liners the coordinator and QA can trace:
   - `Used RAGAS v0.3 schema per docs.ragas.io (last updated 2026-MM)`
   - `Switched from X to Y per [paper URL] discussion in section 3.2`
   - `LanceDB hybrid API confirmed via lancedb.com/docs/search/hybrid (2026-04)`

3. **Search for specific error messages before debugging** any unfamiliar exception or warning. The fix has usually been reported publicly within days of the breakage.

4. **Verify library API contracts against current docs** before committing to a design. Don't trust your training-time knowledge of `lancedb`, `gliner`, `sentence-transformers`, `torch`, `pyarrow`, `fastapi`, etc.

5. **Bias toward recency for evaluations and benchmarks.** If you are defining a scoring method, benchmark set, or eval rubric, verify it against current community practice rather than older internal habits.

6. **Default to a quick web check before non-trivial implementation.** The normal budget is about 10 minutes per research question, not an open-ended literature review.

## In-scope research areas

- Retrieval-augmented generation evaluation (RAGAS, MTEB, BEIR, etc.)
- LLM inference serving (vLLM, TGI, SageMaker, Bedrock)
- Vector store APIs (LanceDB, Qdrant, Milvus — but V2 is on LanceDB)
- Named entity recognition and information extraction techniques
- Query classification and router design
- Python library bugs and workarounds for anything in `requirements.txt`
- AWS GovCloud specifics for SageMaker and Bedrock endpoints
- Current state of open-weight LLMs (phi-4 variants, Llama, gpt-oss, Qwen, etc.)

### Role-specific emphasis

- **Evaluation / benchmarking work:** check current RAGAS docs, current MTEB leaderboard patterns, current BEIR-style retrieval evaluation patterns, and recent RAG evaluation papers before locking a rubric or query set.
- **GUI / testing / architecture work:** check current `lancedb`, `pyarrow`, `torch`, `gliner`, `sentence-transformers`, and any Tkinter-adjacent bug reports or release notes when the issue looks version-sensitive.
- **AWS / GovCloud work:** check current Bedrock, SageMaker, and OSS endpoint documentation because GovCloud behavior and auth details drift.
- **Router tuning / extraction work:** check recent papers and implementation guidance on query classification, NER fine-tuning, and tiered extraction strategies before changing scoring or model-selection logic.

### Example search prompts

- `ragas evaluation 2026 production rag`
- `lancedb 0.30 fts hybrid search api`
- `gliner batch inference gpu 2026`
- `aws bedrock govcloud oss endpoint openai sdk compatible`
- `query router classification benchmark 2026`
- `retrieval augmented generation evaluation metrics 2026`
- any exact API or error message seen during implementation

## Out of scope

- Personal browsing or general tutorial content
- Anything that leaks corpus-specific, program-specific, or employer-specific details in the search query
- Multi-hour research deep dives — keep it to ~10 minutes per question, cite the sources, move on
- Re-researching something that is clearly in your training data and unlikely to have changed (standard library, basic Python patterns)
- Searching for secrets, identifiers, or anything that would expose sensitive corpus contents outside approved systems

## Process discipline

- Research first, implement second
- Cite sources in handoff notes
- If research contradicts your prior assumption, STATE that explicitly so the coordinator and future maintainers understand the decision trail
- If a 2026 paper supersedes the approach in the existing V2 code, flag it as a future task — don't silently re-architect without coordinator approval

## Network access

Firewall is intentionally relaxed during active development sessions to allow research. This is a temporary operator-authorized state, not a standing open door. Do not assume network access is available outside active sessions.

**Current session note (2026-04-11 through 2026-04-12):** user explicitly authorized broad web research to speed up implementation, evaluation, GUI testing, architecture work, and AWS/GovCloud verification. Use that access, but keep queries generic and do not leak corpus-specific or employer-specific details.

## Why this rule exists

V2 hit multiple silent library API breakages during April 2026:
- LanceDB `create_fts_index()` multi-column API removed in 0.30+ — broke silently for 7 days
- LanceDB `hybrid_search` builder chain changed — middleware wrapper fell back to vector-only silently
- `pylance` vs `lancedb` package confusion caused a streaming path to silently load everything into memory

Every one of these was caught by web research AFTER the bug was reproduced. If the initial implementations had checked current docs, the bugs would have been caught at code time, not days later during production runs.

The cost of a 10-minute verification search is trivial compared to the cost of a silent correctness bug in production.

---

Signed: Jeremy Randall (project owner) | 2026-04-11 MDT
