# Engineering Status And Architecture Reset 2026-04-12

## Executive Technical Summary

The V1 path was closer to a retrieval demo than to a trustworthy question-answering system. It could retrieve relevant documents, but it could not support reliable structured aggregation because the architecture mixed ingest, indexing, extraction, and answer logic too tightly, and the first-pass entity layer was still producing polluted business-facing entities.

The system has now been split into two applications:

- `CorpusForge`
  - upstream ingest
  - normalization
  - chunk/vector export
  - integrity checks
- `HybridRAG_V2`
  - import into LanceDB
  - FTS/vector retrieval
  - Tier 1/Tier 2 extraction
  - evaluation
  - answer path

This was a necessary architecture reset, not cosmetic refactoring.

## Why V1 Was Abandoned As The Main Path

V1 had three problems:

1. It could retrieve evidence, but could not aggregate reliably enough for business-facing answers.
2. It did not have a sufficiently isolated upstream/downstream contract, so it was hard to tell whether a failure was caused by ingest, extraction, routing, or answer logic.
3. It encouraged false confidence: the system could appear to work while still carrying dirty structured data.

The decision was to keep the parts that were working and rebuild the rest around clearer interfaces.

## Root Cause Of The Current Delay

The most important finding was that Tier 1 entity extraction was polluting business entity types with security/cyber identifiers.

Examples:

- `PO` collisions:
  - control-family codes such as `IR-8`, `IR-4`, `IR-9`
  - report/product tokens such as `FSR-L22`, `ASV-VAFB`, `RTS-DATA`
- `PART` collisions:
  - STIG / DISA / MITRE families such as `AS-5021`, `OS-0004`, `GPOS-0022`, `CCI-0003`, `SV-2045`, `CVE-*`, `CCE-*`
  - cyber/status debris such as `pam_faillock`, `SERVICE_STOP`, `SNMP`, `mode`, `NORMAL`, `failure`

That means a full rerun without better controls would have produced another dirty authoritative store and wasted another day.

## What Has Been Completed

### Architecture and operability

- split the system into `CorpusForge` and `HybridRAG_V2`
- fixed installer/workstation paths
- hardened import/index reliability
- added export integrity checks in Forge
- clarified the Forge-to-V2 metadata contract

### Evaluation

- built a grounded 400-query production corpus
- fixed the production-eval harness so the current baseline is believable rather than misleading

### Tier 1 hardening

- tightened PO and PART boundary handling
- added confusion-set research from the live corpus/store
- added an automated pre-rerun gate
- added an acceptance-gate doc and runbook
- added external research synthesis to validate the process against broader practice

Relevant recent commits:

- `34b64d8` Tighten Tier 1 PO and part boundary guards
- `d0476bb` docs: audit tier1 PO and PART confusion sets
- `f3bafb7` Add Tier 1 regex pre-rerun gate
- `a45e62f` fix(ops): strengthen tier1 regex gate curated cases
- `1620084` docs: formalize tier1 regex acceptance gate
- `e94d704` docs: add Tier 1 regex research synthesis
- `54eadec` docs: add tier1 regex corpus rerun audit

## Current Technical Position

The important shift is:

- regex is no longer being treated as the truth layer
- regex is being treated as a candidate generator
- validators/invalidators and staged promotion determine what becomes authoritative business data

This is the key engineering correction.

It is also worth stating explicitly that the preprocessing path here is a real data-engineering workload, not a simple software-install workload. Converting the legacy corpus into AI-usable form requires chunking, embedding, enrichment, extraction, indexing, and validation passes. At this corpus size, those are compute-intensive one-time builds and conversions that can consume days or weeks before the downstream QA path is even meaningful.

## Current Baseline

On the current store, the 400-query baseline is usable enough for diagnosis but not yet the final truth baseline:

- `148 PASS`
- `107 PARTIAL`
- `145 MISS`
- `259/400` routing correct

This tells us the system is not dead, but it is not production-trustworthy yet.

The dominant remaining issues are:

1. dirty structured layer
2. identifier/path retrieval gaps
3. router weakness
4. weak higher-order structured answer path

## What We Are Doing Instead Of Guess-And-Check

The new pre-rerun process is:

1. code hardening
2. corpus/store confusion audit
3. automated regex gate
4. shadow Tier 1 run on roughly 5,000 to 10,000 chunks
5. approval only if the shadow run passes
6. one clean full Tier 1 rerun
7. rerun the 400-query baseline on the cleaned store

This is the opposite of “rerun and hope.”

## Acceptance Gate For Tier 1

Before any future full Tier 1 rerun:

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py
```

Tier 1 is only approved if:

- curated adversarial fixtures pass
- preserve fixtures pass
- blocked namespaces do not dominate top post-run `PO` / `PART` values
- shadow-run precision is acceptable:
  - `PO >= 97%`
  - `PART >= 95%`

## Long-Term Production Direction

The production model should be:

- stage delta data
- run extraction on staging
- run automated quality gates
- promote only passing deltas

Not:

- ingest directly into the authoritative store
- discover pollution later
- do retroactive cleanup

Structurally, the next likely improvement is to stop overloading entity types:

- split `BUSINESS_PO` from `REPORT_ID`
- eventually add governed non-business buckets such as `SECURITY_CONTROL` / `CYBER_BASELINE`

## Why The Time Was Necessary

The lost time was not caused by cosmetic polish. It came from discovering that:

- the original path hid reliability problems behind seemingly good retrieval
- the data itself contains long-tail collisions that look valid to naive regexes
- a full rerun is expensive enough that doing it without gates is irresponsible

There were also real environment constraints:

- repeated IT/admin-access instability across two machines disrupted continuity and forced resets
- proxy/network friction slowed initial database establishment dramatically
- preprocessing at this corpus scale is materially different on CPU-only versus CUDA/GPU paths, so software compatibility work to keep preprocessing on the GPU path was a real schedule item, not an optimization nicety
- the new government AWS path also came with provider-side access issues and a non-trivial integration curve across Azure-style formatting assumptions, the enterprise AI endpoint layer, and OpenAI-compatible Jupyter workflows

The time has gone into making the pipeline measurable, stageable, and production-shaped.

## Next Technical Steps

1. Run the automated Tier 1 regex gate.
2. Run a 5k–10k chunk shadow Tier 1 job.
3. If the shadow run passes, run one clean full Tier 1 rerun.
4. Rerun the 400-query baseline on the cleaned store.
5. Use the cleaned baseline to prioritize:
   - retrieval fixes for identifier/path-heavy miss families
   - router improvements
   - stronger structured-answer logic

## Short Engineer-To-Engineer Version

“V1 turned out to be a retrieval-first prototype with weak aggregation trust. I split the system into CorpusForge and HybridRAG_V2 so ingest/export integrity is isolated from retrieval/extraction/eval. The main blocker I found was Tier 1 entity pollution: PO and PART were picking up security-control, STIG, and report-ID junk. We stopped the blind rerun path, hardened the extractor, added corpus-derived confusion sets, built a pre-rerun regex gate, and aligned the process with staged promotion instead of direct authoritative writes. Next step is gate -> shadow Tier 1 -> one clean rerun -> rerun the 400-query baseline -> then retrieval/router tuning on the cleaned store.”
