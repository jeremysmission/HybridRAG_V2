# Program AI Status Reset And Path Forward 2026-04-13

## Purpose

This is the single all-in-one status update for the current program AI effort.

It is intended to work as:

- a manager-level justification update
- a team-wide project update
- a technical status summary
- a business-case and cost-discipline explanation

## Terms Up Front

To make the rest of this update easier to follow, I want to define the main terms first.

- **HybridRAG**
  - short for **Hybrid Retrieval-Augmented Generation**
  - in this project, that means combining semantic/vector retrieval with text/keyword retrieval instead of relying on only one search method
- **V1**
  - the original HybridRAG implementation
  - this was the first version of the system and the path I had previously described as getting close to a demo
- **V2**
  - the rebuilt current system, `HybridRAG_V2`
  - this is the current retrieval/extraction/evaluation path
- **CorpusForge**
  - the upstream application that prepares, normalizes, deduplicates, and exports the corpus before V2 imports and uses it

## Executive Summary

I need to reset expectations from the earlier V1 status.

V1 proved that the program's data could be indexed and retrieved with AI techniques, but it did **not** prove that the system could support trustworthy business-facing answers. Once I pushed V1 harder against the real enterprise program drive and real aggregation-style questions, I found that it was closer to a retrieval demo than to a trustworthy system.

Rather than force a brittle demo, I kept the parts that were actually working, split the architecture into cleaner upstream and downstream applications, and rebuilt the path around quality gates, measurable evaluation, and staged promotion.

The project is now on a much more disciplined path. The remaining major gating item is not “basic AI plumbing.” It is completing the clean Tier 1 structured-data path and then measuring the rebuilt system on the cleaned store.

## How The Project Evolved

The project did not originally begin as two separate applications.

It started as a single HybridRAG effort, which I now refer to as `V1`. In that original form, ingest, preprocessing, retrieval, extraction, and answering were still too tightly coupled. That was enough to make early proof-of-concept progress, but it made it too easy for the system to look closer to done than it really was.

Once I pushed V1 harder against the real enterprise program drive, it became clear that I needed a cleaner separation of responsibilities. That is why the project evolved into:

- `CorpusForge`
  - the upstream corpus-preparation side
  - responsible for ingest, normalization, deduplication, chunking/export, and integrity checks
- `HybridRAG_V2`
  - the downstream retrieval-and-answering side
  - responsible for import, retrieval, extraction, evaluation, and answer generation

So the move from a single HybridRAG code path into `CorpusForge` plus `HybridRAG_V2` was not cosmetic refactoring. It was the architectural response to what I learned from V1.

## What Failed In V1

The major turning point came when I used V1 on the real enterprise program drive for the kind of answers that matter to the program, not just document retrieval.

That is where I found the hard limitation:

- V1 could retrieve relevant documents and chunks
- but it could not aggregate reliably enough to support trustworthy business-facing answers

This was not a small tuning issue. It was a structural issue.

On the actual enterprise program data, many identifiers look similar even when they mean very different things. Purchase orders, part numbers, technical report IDs, security-control identifiers, cyber-governance codes, and security/vulnerability identifiers all coexist in the same legacy drive. V1 could find related documents, but when I pushed it toward counts, rollups, and structured answers, the first-pass extraction layer was still confusing some of those categories.

That meant the system could produce answers that looked plausible while still being semantically wrong.

The biggest examples were:

- purchase-order-style fields being polluted by security-control and report-code patterns
- part-number-style fields being polluted by STIG / DISA / MITRE / security standard-style identifiers
- aggregation-style answers looking more mature on the surface than they really were underneath

That is the key reason I stopped treating V1 as “almost done.”

## What Was Found

The biggest technical issue uncovered was in Tier 1 entity extraction. It was capable of populating business-facing fields such as purchase orders and part numbers with technical and security identifiers. That means the system could appear operational while still generating misleading structured answers.

Examples of what was going wrong:

- purchase-order fields polluted by control-family codes
- part-number fields polluted by STIG / DISA / MITRE-style identifiers
- a full rerun without quality gates would have produced another dirty store

The main lesson was:

- the old path was closer to a visible prototype than to a trustworthy system

It is also important to understand that this kind of AI preprocessing is not analogous to deploying a normal legacy software package. A large corpus has to be converted into AI-usable form through chunking, embedding, enrichment, extraction, indexing, auditing, and revalidation. Those are compute-intensive one-time conversions, and at this scale they can consume days or weeks of build time before the final system can even be judged fairly.

## What Has Been Completed

Completed work includes:

- architecture reset into `CorpusForge` and `HybridRAG_V2`
- CorpusForge deduplication/canonicalization work to reduce duplicate parse, chunk, embed, extract, and storage overhead
- installer and workstation reliability improvements
- import/index reliability fixes
- Forge export integrity checks
- clearer Forge-to-V2 metadata contract
- grounded 400-query evaluation corpus
- believable production-eval harness
- Tier 1 regex hardening
- automated pre-rerun quality gate
- staged promotion concept for future data additions
- clearer technical and non-technical documentation

## What “Tiers” Means

The system uses extraction tiers:

- **Tier 1**
  - fast deterministic extraction across the full corpus
  - technically this is the broad rule/regex candidate-generation pass over the indexed corpus
  - it is best at structured values with stable shapes such as dates, contacts, purchase-order-like values, and part-number-like values
  - it saves time and money by preventing later model-based tiers from spending compute on easy high-volume cases
- **Tier 2**
  - model-based entity extraction on a narrower subset
  - technically this is the smarter NER-style pass, currently aligned with GLiNER-style extraction, for entities that are too messy for deterministic patterns alone
  - it is where people, organizations, sites/locations, and harder real-world entity classes are handled more intelligently
  - it saves time and money by avoiding use of the heaviest reasoning path on cases that a narrower entity model can already solve
- **Tier 3**
  - the most expensive hard-tail reasoning/relationship path
  - technically this is the selective higher-cost path for the ambiguous or relationship-heavy subset that still remains after Tier 1 and Tier 2
  - it is where deeper extraction, harder cross-field interpretation, and relationship-heavy reasoning belong
  - it saves time and money by being reserved only for the smallest most difficult slice instead of becoming the default for the entire corpus

The important point is that each tier is designed to remove work from the next one. That layered reduction is a major reason the system is still financially and operationally realistic on a corpus of this size.

## Value Added By The Tiered Strategy

The tiered strategy is not only a technical preference. It creates real time and cost savings.

Without a tiered approach, the easiest path would be to run stronger model-based extraction and enrichment broadly across the corpus. On a corpus of this size, that would mean:

- more total model calls
- longer end-to-end build time
- higher API or cloud cost
- more dependence on remote infrastructure for work that can be handled locally

The current strategy avoids that by:

- doing deterministic and rule-based work first
- keeping embeddings local on GPU where they are fast and effectively free once the workstation is available
- narrowing the expensive AI path to the smaller subset where it actually adds value
- designing the future production path so smaller nightly or scheduled updates can be handled mostly offline and incrementally

That means the tiered strategy saves:

- **time**
  - easy high-volume work does not wait behind the slowest AI step
  - future nightly or scheduled updates can be handled mostly incrementally instead of reprocessing the whole corpus through the heaviest path
- **money**
  - the program does not have to pay premium-model cost on every chunk
  - the long-term production model is not forced into a high recurring cloud burn
- **maintenance burden**
  - the steady-state path is designed to be local-first and staged, not permanently dependent on an expensive remote AI service

This is a significant part of the value of the redesign. The architecture reset was not only about making the answers more trustworthy; it was also about making the system more sustainable to build and maintain.

## Additional Value From CorpusForge Deduplication

Another important improvement is the deduplication work in `CorpusForge`.

That work matters because duplicate or near-duplicate files create waste at multiple stages:

- duplicate parsing
- duplicate chunking
- duplicate embeddings
- duplicate extraction
- larger exports
- larger indexes
- noisier retrieval results

By reducing duplicated content earlier in the pipeline, the system avoids paying that cost over and over again. That saves both processing time and storage/index overhead, and it also improves answer quality by reducing duplicate evidence and repeated noise in downstream retrieval.

## Why The Work Took Time

There are three main reasons the work took longer than the original optimistic path suggested.

### 1. Hidden technical debt in the data

This is the program’s first AI effort on top of roughly 15 years of legacy data. That data was not created for AI use. It contains:

- inconsistent naming conventions
- mixed document styles
- identifiers that look alike even when they mean different things
- security and technical codes embedded alongside business data

### 2. Environment and approval overhead

I did not start with every required path already available. Part of the effort has been:

- identifying and submitting AI use cases for approval
- working through software and dependency approval paths
- getting workstation and hardware paths lined up
- dealing with unstable admin access across two machines and repeated IT resets
- working through proxy/network friction while downloading and establishing the working database
- resolving software compatibility problems so preprocessing could use CUDA/GPU instead of falling back to CPU-only execution
- working around the fact that the desktop workstation is still effectively on-site only rather than remotely available
- adapting the design to what was actually available at each stage

That means some of the elapsed time has gone into getting the project into a state where the engineering work could be done correctly. In particular, establishing the working database was slowed by more than a month of stop-and-go downloading under proxy/network constraints, and productivity was also affected by two-machine admin-access instability plus the need to solve GPU-vs-CPU preprocessing compatibility on corpus-scale jobs. The desktop workstation also still remains largely on-site only, so the workstation laptop has been the main way to keep progress moving during nights and weekends away from that machine.

### 3. Intentional cost discipline

I am deliberately not taking the most cloud-heavy path. A more vendor-heavy or cloud-heavy design could be much more expensive up front and monthly. Instead, I am building a tiered Python pipeline that uses cheaper deterministic processing first and reserves the more expensive AI work for the smaller subset that really needs it.

That is why the architecture split and quality gates matter: they are what make the low-recurring-cost model realistic.

## Why Current Time On AWS Is Justified

A recent positive change is that the company has only very recently released an internal AI toolkit with temporary access to OSS-20B and OSS-120B through government AWS.

That gives me a practical way to use stronger AI only on the remaining heavy one-time preprocessing tasks, while still preserving the overall low-cost tiered design instead of moving to a broad cloud-heavy workflow.

That access path was not plug-and-play. It required:

- application and approval
- work with an AI Staff Engineer while issues on their side were debugged
- learning a government AWS path on the fly instead of standard commercial AWS
- lining up government AWS restrictions, Azure-style formatting expectations, the enterprise AI endpoint layer, and OpenAI-compatible Jupyter workflows

This is the direct justification for the current time being spent on AWS. It is not a side project away from the main effort. It is part of the main effort because it creates the best available path for the remaining one-time heavy extraction and enrichment work while the company-provided models are temporarily available at little or no additional model cost.

There is also a timing advantage to using that path now rather than later. While the company toolkit access is temporarily free, it lets me process the hardest remaining enrichment and extraction subset at essentially zero model cost. If I deferred that work until after the free window or tried to do the same work through a paid general-purpose endpoint, the build would either:

- take longer on local/offline resources
- or cost materially more in API usage

So part of the value here is being resourceful and using the temporary company capability while it is available, rather than missing that window and paying for the same heavy one-time work later.

## Business Case And Long-Term Payoff

This project is also being built under a deliberate cost-control strategy.

A more typical outside or cloud-heavy path for this kind of effort could involve meaningful up-front and recurring cost. Public benchmark scenarios already documented for a `700 GB`, `15-year`, mixed-format, `sensitive data`-sensitive RAG effort suggest:

- a lean specialist / boutique path:
  - about `$53K-$116K+` in the first year
  - about `$1.2K-$4K+` per month after build
- a government-style integrator on AWS:
  - about `$68K-$137K` in the first year
  - about `$2.75K-$5.3K` per month after build
- a Red Hat / OpenShift AI platform-first path:
  - about `$114K-$200K+` in the first year
  - about `$4.9K-$8.9K` per month after build

Those benchmark ranges are documented in:

- [RAG_OUTSOURCING_ESTIMATES_CUI_700GB_2026-04-12.md](./RAG_OUTSOURCING_ESTIMATES_CUI_700GB_2026-04-12.md)

The point is not that the program should outsource this work. The point is that the in-house approach is creating long-term value:

- lower outside-services cost
- lower recurring cloud dependence
- lower long-term maintenance burden if the staged local-first model works as intended

So part of the payoff for the time being invested now is that it aims to leave the program with a more affordable steady-state operating model than a vendor-heavy or cloud-heavy alternative.

## Why This Matters To Different Team Roles

This effort is not only about an AI model. It affects multiple functional lanes in different ways.

- **Program management**
  - the main value here is moving from a prototype that looked promising to a system that is measurable, gated, and more supportable
  - the architecture split, quality gates, and evaluation baseline reduce the risk of overclaiming readiness
  - the tiered design is also part of a long-term cost-control strategy, not just a technical preference

- **Logistics / supply / material analysts**
  - this work directly affects whether purchase-order-like data, part numbers, BOM-style evidence, shipping records, and procurement references can be trusted
  - one of the main reasons for the reset was that these business-facing entity types were being polluted by unrelated technical/security identifiers
  - the cleanup and gating work is what makes future procurement and material questions more trustworthy

- **Cyber security / IA**
  - a major part of the problem was that security identifiers such as STIG / DISA / MITRE / security standard-style codes were colliding with business fields
  - the current path explicitly protects against treating cyber/security identifiers as if they were logistics or program entities
  - this is also important for trust, because it preserves a cleaner boundary between cybersecurity artifacts and business data

- **Field engineers / site install teams**
  - the real corpus includes site-specific install folders, packing lists, inventories, surveys, acceptance artifacts, and travel/field records
  - retrieval was already proving useful for finding those documents, but the structured-answer path needed to become more trustworthy before site-level counts and rollups could be treated seriously
  - the current work is aimed at making that path usable without misleading the people who depend on it

- **Network administrators / infrastructure support**
  - the project has depended heavily on getting the environment stable enough to run corpus-scale preprocessing and indexing reliably
  - import/index reliability, workstation operability, proxy-aware installs, GPU/CUDA compatibility, and government AWS integration are all part of the real engineering scope
  - this is one reason the project has taken more than “just model tuning” time

- **Engineers / technical reviewers**
  - the main correction was architectural: separate upstream corpus preparation from downstream retrieval/extraction/evaluation
  - the system is now moving toward a stage -> audit -> promote model instead of direct authoritative writes
  - that is the right direction for future maintainability and production hardening

- **Leadership / stakeholders**
  - the most important message is that the work has shifted from “make something demo-like” to “make something trustworthy enough to stand behind”
  - the extra time has gone into reducing false confidence, lowering long-term cost risk, and creating a more sustainable path forward

## Current Status

What is true now:

- the architecture reset is done
- retrieval is real and usable
- the main remaining gating item is a clean Tier 1 rerun on top of the new quality controls

The current path forward is now concrete:

1. run the automated Tier 1 quality gate
2. run a controlled shadow Tier 1 sample
3. if clean, run one full Tier 1 rerun
4. selectively use the company OSS toolkit for the remaining heavy preprocessing tasks
5. rerun the 400-query baseline on the cleaned store
6. finish targeted retrieval and routing improvements

That is the shortest credible path to a trustworthy demo candidate and a production-shaped design.

## SMART Goals From This Point

To align the next phase with a Specific, Measurable, Achievable, Relevant, and Time-Bound format, the near-term goals are:

### Goal 1 — Freeze The Clean Tier 1 Baseline

- **Specific**
  - finish the clean Tier 1 path and freeze the cleaned store as the new authoritative structured baseline
- **Measurable**
  - completed clean Tier 1 rerun
  - post-rerun audit artifact
  - rerun 400-query baseline on the cleaned store
- **Relevant**
  - this is the main gating dependency for trustworthy structured answers
- **Time-bound**
  - target: **April 15, 2026**

### Goal 2 — Prove The AWS Heavy-Lift Path On The Right Subset

- **Specific**
  - use the company AI Toolkit path on the selected one-time heavy extraction/enrichment subset where remote model assistance creates real leverage
- **Measurable**
  - working government-AWS processing path
  - documented subset choice
  - documented time/cost comparison versus local-only or paid-endpoint alternatives
- **Relevant**
  - this is the best available path for accelerating the hardest remaining one-time preprocessing work
- **Time-bound**
  - target: **April 18, 2026**

### Goal 3 — Reach A Trustworthy Demo Candidate On The Rebuilt Architecture

- **Specific**
  - use the cleaned structured store and updated evaluation results to finish the highest-value retrieval/routing improvements needed for a trustworthy demo candidate
- **Measurable**
  - updated measured baseline
  - documented retrieval/routing improvements
  - operator-ready runbook on the rebuilt path
- **Relevant**
  - this is the milestone that matters for program visibility and confidence
- **Time-bound**
  - target: **April 27, 2026**

## Estimated Timeline

Current estimate:

- about **2 more weeks** to a trustworthy demo candidate on the rebuilt path

This estimate assumes:

- the Tier 1 gate passes
- the shadow extraction does not reveal a new major collision class
- the clean full rerun behaves as expected

## Bottom Line

The project has moved from “get something demo-like working” to “build a trustworthy and affordable AI pipeline on a difficult legacy corpus.”

That reset cost time, but it also dramatically reduced the risk of continuing down a path that looked good while still producing unreliable answers.

The current direction is justified because it is now:

- measurable
- staged
- more trustworthy
- more sustainable from a cost perspective

## Longer-Term Payoff Beyond This Project

One additional point is important from a program perspective: this work is not only building a solution for the current corpus. It is also paving the road for future AI efforts.

Once this architecture is established, the program will already have:

- a proven ingest/preparation path in `CorpusForge`
- a downstream retrieval/extraction/evaluation path in `HybridRAG_V2`
- staged promotion and quality-gating concepts
- reusable workstation and install patterns
- clearer AI endpoint integration experience
- experience connecting local processing, enterprise endpoints, and government AWS tooling in one workflow

That means future AI projects should not have to re-learn all of the same lessons from scratch. The current effort is creating reusable pipeline, tooling, and integration knowledge that should make follow-on AI efforts faster, cheaper, and less risky than this first one.
