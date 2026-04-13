# AI System Evolution And Tiered Cost Strategy 2026-04-12

## Purpose

This document captures the full story of the current AI effort:

- what was originally designed
- what failed
- what was repurposed instead of discarded
- what the key findings were
- how the method evolved
- why the system is now built as a tiered pipeline
- how that tiered design reduces both startup cost and ongoing maintenance cost

## Executive Summary

The original V1 path proved that the program could retrieve relevant information, but it did not prove that the system could answer questions reliably enough to support business-facing use. In particular, V1 could not aggregate with enough trust, and the first-pass extraction layer was still capable of turning technical/security identifiers into misleading business entities.

Rather than continue forcing a fragile one-app design, the system was reset into a cleaner two-application architecture:

- `CorpusForge` for ingest, normalization, export, and integrity
- `HybridRAG_V2` for import, retrieval, extraction, evaluation, and answer generation

This was not a restart from zero. It was an evolution:

- keep what worked
- separate responsibilities
- remove hidden failure modes
- make the whole path measurable

The result is a more production-shaped system and a much clearer long-term cost strategy.

## The Original Design

The original goal was to build a system that could:

- ingest and normalize a very large document corpus
- retrieve relevant evidence from that corpus
- extract structured entities and relationships
- support answer generation and aggregation
- do all of that without requiring a large recurring cloud bill

The initial implementation moved toward that goal, but the architecture mixed too many concerns together. It was difficult to tell whether an issue was caused by ingest, extraction, retrieval, routing, or answer logic.

## What Failed In V1

V1 did achieve some important things:

- it showed that retrieval on the corpus was real
- it proved that the system could surface relevant evidence
- it validated that a lightweight, homegrown Python stack could handle more than a toy use case

But it also exposed hard limits:

1. Retrieval success was stronger than answer trust.
2. Aggregation quality was not strong enough to support confident business-facing responses.
3. Tier 1 extraction was still capable of poisoning business entity types.
4. The one-app design made it too easy to mistake visible progress for trustworthy progress.

The key lesson was:

- V1 was closer to a demo than to a dependable system

## What Was Repurposed Instead Of Thrown Away

The pivot did not discard the useful work. It repurposed it.

Kept and evolved:

- the homegrown Python codebase
- the retrieval-first foundation
- the chunking/indexing concepts
- the corpus-specific lessons already learned
- the operator workflows that were worth preserving
- the evaluation and debugging knowledge accumulated during V1

Rebuilt around them:

- upstream/downstream repo separation
- clearer import/export contract
- better install and workstation reliability
- stronger integrity checks
- formal evaluation corpus and baseline process
- staged quality gating before expensive reruns

## Key Findings

The most important findings so far are:

1. **Dirty structured data is more dangerous than weak retrieval.**
   If the system retrieves the right evidence but the structured layer is polluted, the answer can still be misleading.

2. **`PO` and `PART` were not safe to trust as-is.**
   Technical/security identifiers were colliding with business entity fields.

3. **Regex should not be treated as the truth layer.**
   Regex is best used as a broad candidate generator followed by validators and invalidators.

4. **The expensive mistake is a blind rerun.**
   A full Tier 1 rerun on a dirty rule set can waste a day and still leave the system worse than before.

5. **A system like this needs staged promotion, not direct production writes.**
   New data should be staged, audited, and promoted only after passing quality checks.

## The Evolved Method

The method has evolved from:

- ingest everything
- extract
- inspect problems afterward

to:

- ingest into staging
- run deterministic preprocessing
- use extraction as a candidate-generation step
- validate candidates
- audit the staged results
- promote only passing data to the authoritative store

This is the major methodological shift.

## The Tiered Approach

The tiered approach exists for two reasons:

1. quality control
2. cost control

### Tiered quality logic

The pipeline now assumes that not every problem should be handled by the heaviest AI step.

- deterministic preprocessing handles broad filtering and structure
- Tier 1 handles high-volume candidate extraction
- later tiers handle narrower, more valuable AI-assisted work
- promotion gates decide what can become authoritative

### Tiered cost logic

A fully cloud-heavy design on a 700GB corpus would be expensive up front and expensive to operate.

The current strategy is to:

- use homegrown Python and local deterministic processing wherever possible
- reduce the amount of corpus that needs heavier AI treatment
- reserve expensive model calls for the smaller subset where they add real value
- take advantage of temporarily available company-provided AWS AI services where appropriate
- aim for a much lower long-term query-cost profile than a naive cloud-first design

In practical terms, the target is:

- avoid a startup path that looks like a `$15K-$20K` design exercise plus roughly `$800/month` in steady cloud cost
- instead, engineer a lower recurring cost model that is closer to tens of dollars per month in query traffic rather than hundreds or thousands

That cost target is only realistic if the pipeline is trustworthy. Dirty reruns destroy both schedule and cost savings.

An important recent development is that the company has only just released an internal AI toolkit that includes temporary access to OSS-20B and OSS-120B via AWS. That matters because it creates a narrow, cost-controlled way to use stronger AI on the remaining heavy preprocessing tasks without changing the overall philosophy of the system. The strategy remains the same: broad work stays local and deterministic, while the heavier model path is used sparingly where it creates the most leverage. It also means the project now includes a self-taught AWS infrastructure learning curve so that this new capability can be used responsibly instead of turning into unmanaged cloud complexity. Because this path runs through government AWS rather than standard commercial AWS, there is also a separate layer of restrictions and configuration friction that has to be worked through.

## Why This Took Time

The time was not spent polishing a demo.

It was spent:

- finding hidden reliability issues
- preventing repeated dirty reruns
- separating what actually works from what only looked close
- rebuilding the system into something that can be measured honestly
- creating a process that protects future network-drive additions from contaminating production

This is normal for a first AI project built on top of many years of legacy data. The source material was not designed for AI use, so the system has to learn how to distinguish real business information from technical and security codes that only look similar.

It is also important that this did not happen in a vacuum. Along the way, a significant amount of enabling work was required:

- identifying and submitting AI use cases for approval
- working through software and dependency approval constraints
- getting the necessary workstation and hardware paths lined up
- dealing with unstable admin access across two machines and repeated IT resets
- working through difficult proxy/network conditions while downloading and establishing the working database
- resolving software compatibility issues so heavy preprocessing could stay on CUDA/GPU instead of falling back to CPU-only execution
- adapting the architecture to what was actually available at each stage

So part of the elapsed time was not only model and pipeline design. It was getting the project into a state where the engineering work could be done with the right tools and approvals in place. In practice, the proxy/network constraint alone made the initial database establishment a stop-and-go effort over more than a month, the two-machine admin issue caused repeated continuity breaks, and the GPU-vs-CPU preprocessing compatibility problem had to be solved because corpus-scale preprocessing is dramatically less practical when stuck on CPU only. That environment is finally coming together.

## Current Position

As of 2026-04-12:

- the architecture reset is done
- installer and workstation reliability is substantially improved
- Forge export integrity and metadata-contract work is in place
- the 400-query evaluation corpus is built
- the production-eval harness has been corrected
- Tier 1 regex has been hardened
- an automated pre-rerun gate exists
- the process is now staged and measurable instead of guess-and-check

The remaining gating item is:

- one clean Tier 1 path using the new controls

## Path Forward

The next sequence is:

1. run the automated Tier 1 gate
2. run a shadow Tier 1 extraction on a smaller chunk sample
3. approve the full Tier 1 rerun only if the shadow run passes
4. run one clean full Tier 1 rerun
5. rerun the 400-query baseline on the cleaned store
6. use the cleaned baseline to target retrieval, routing, and structured-answer improvements

## Non-Technical Story

Plain-English version:

The first version showed that AI could find relevant documents, but it did not yet prove that the system could answer questions safely enough for real use. I found that some technical and security codes were being mistaken for business data. Instead of forcing a demo on top of that, I split the system into cleaner parts, kept the pieces that were working, and added quality gates so future data can be checked before it reaches production. The design now uses cheaper broad processing first and saves the heavier AI work for the smaller portion where it is actually needed, which is how I am trying to make the system both reliable and affordable.

## Technical Story

Engineer-facing version:

The project has moved from a retrieval-heavy prototype to a staged ingestion and promotion system. V1 proved retrieval value but failed the aggregation trust test. The corrective move was to split upstream export/integrity responsibilities into `CorpusForge` and downstream retrieval/extraction/eval responsibilities into `HybridRAG_V2`, then harden Tier 1 with corpus-derived confusion sets, validator-style gates, and a shadow-run approval process. The tiered design is intentional: broad deterministic processing and high-volume candidate generation happen locally, while narrower AI-heavy work is reserved for later stages. That reduces both technical risk and recurring cost while keeping the system aligned with a production-style promotion model.

## Bottom Line

This effort has evolved from “get a demo working” into “build a trustworthy and affordable AI pipeline for a very large, messy, legacy corpus.”

That is why the work has taken time.

It is also why the system is now on a much stronger path than it was under V1.
