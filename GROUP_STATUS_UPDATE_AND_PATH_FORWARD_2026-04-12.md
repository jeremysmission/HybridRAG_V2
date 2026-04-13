# Group Status Update And Path Forward 2026-04-12

## Purpose

This is a fuller written update for the team that explains:

- what changed since the earlier V1 path
- what was found
- what has been completed
- why the work has taken time
- how the architecture evolved
- what the next steps are
- why continued work on the current path is justified

## Summary

To make the rest of this update easier to follow, I want to define the main terms up front.

- **HybridRAG**
  - short for **Hybrid Retrieval-Augmented Generation**
  - in this project, that means combining semantic/vector retrieval with text/keyword retrieval instead of relying on only one search method
- **V1**
  - the original HybridRAG implementation
  - this was the first version of the system and the path I previously reported as being close to a demo
- **V2**
  - the rebuilt current system, `HybridRAG_V2`
  - this is the new architecture I refer to below when I describe the reset and the current path forward
- **CorpusForge**
  - the new upstream application that prepares, normalizes, and exports the corpus before V2 imports and uses it

## How The Project Evolved

The project did not begin as two separate applications.

It started as a single HybridRAG effort, which I now refer to as `V1`. In that original form, ingest, preprocessing, retrieval, extraction, and answering were still too tightly coupled. That was workable for early proof-of-concept progress, but it made it too hard to tell which part of the system was actually trustworthy and which part was only appearing to work.

Once I pushed V1 harder against the real IGS drive, it became clear that I needed a cleaner separation of responsibilities. That is why the project evolved into:

- `CorpusForge`
  - the upstream corpus-preparation side
  - responsible for ingest, normalization, chunking/export, and integrity checks
- `HybridRAG_V2`
  - the downstream retrieval-and-answering side
  - responsible for import, retrieval, extraction, evaluation, and answer generation

So the split into `CorpusForge` plus `HybridRAG_V2` was not a branding change. It was the architectural response to what I learned from V1.

I need to reset expectations from the earlier V1 status. The original version proved that retrieval on the corpus was possible, but it did not prove that the system could support trustworthy structured answers. In particular, V1 could find relevant evidence but could not aggregate reliably enough for the kind of answers we ultimately want to stand behind.

Rather than continue forcing a brittle one-app design, I kept the pieces that were working and rebuilt the system into a cleaner two-application architecture:

- `CorpusForge`
  - ingest
  - normalization
  - export packaging
  - integrity checks
- `HybridRAG_V2`
  - import into LanceDB
  - retrieval
  - entity extraction
  - evaluation
  - answer generation

This was not cosmetic refactoring. It was a necessary architecture reset.

## What Was Found

The biggest technical issue uncovered was in Tier 1 entity extraction. It was capable of populating business-facing fields such as purchase orders and part numbers with security-control and technical identifiers. That means the system could appear operational while still generating misleading structured answers.

Examples of what was going wrong:

- purchase-order fields polluted by control-family codes
- part-number fields polluted by STIG / DISA / MITRE-style identifiers
- a full rerun without quality gates would have produced another dirty store

The main lesson was:

- the old path was closer to a visible prototype than to a trustworthy system

It is also worth clarifying that this kind of AI preprocessing is not analogous to deploying a normal legacy software package. A large corpus has to be converted into AI-usable form through chunking, embedding, enrichment, and extraction. Those are compute-intensive one-time conversions, and at this scale they can consume days or weeks of build time before the final system can even be judged fairly.

## Why The Work Took Time

There are three reasons the work took longer than the original optimistic path suggested.

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

A recent positive change is that the company has only very recently released an internal AI toolkit with temporary access to OSS-20B and OSS-120B through AWS. That gives me a practical way to use stronger AI only on the remaining heavy preprocessing tasks, while still preserving the overall low-cost tiered design instead of moving to a broad cloud-heavy workflow. It also adds a new engineering burden: learning the AWS infrastructure side quickly enough to use the toolkit correctly without creating hidden cost or configuration problems. Because this path runs through government AWS rather than standard commercial AWS, it carries its own extra restrictions and integration friction.

That access path also required application and back-and-forth with an AI Staff Engineer because there were issues on their side that had to be debugged before the environment became usable. Even after access, the working path required additional integration learning because the practical workflow depended on government AWS infrastructure plus Azure-style formatting expectations, the company's enterprise endpoint AI layer, and OpenAI-compatible patterns inside Jupyter-based development.

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

This design exists to:

- control cost
- preserve speed
- improve reliability
- avoid running the heaviest AI path over everything

The important point is that each tier is designed to remove work from the next one. That layered reduction is a major reason the system is still financially and operationally realistic on a corpus of this size.

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
  - a major part of the problem was that security identifiers such as STIG / DISA / MITRE / NIST-style codes were colliding with business fields
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

## Why Continued Work Is Justified

The current work is not open-ended churn. It is converging around a clear gated path:

1. run automated Tier 1 quality gate
2. run controlled shadow Tier 1 sample
3. if clean, run one full Tier 1 rerun
4. selectively use the company OSS toolkit for the remaining heavy preprocessing tasks
5. rerun the 400-query baseline on the cleaned store
6. finish targeted retrieval and routing improvements

That is the shortest credible path to a trustworthy demo candidate and a production-shaped design.

## Current Status

What is true now:

- the architecture reset is done
- retrieval is real and usable
- the main remaining gating item is a clean Tier 1 rerun on top of the new quality controls

## Estimated Timeline

Current estimate:

- about **2 more weeks** to a trustworthy demo candidate on the rebuilt path

This estimate assumes:

- the Tier 1 gate passes
- the shadow extraction does not reveal a new major collision class
- the clean full rerun behaves as expected

## Bottom Line

The project has moved from “get something demo-like working” to “build a trustworthy and affordable AI pipeline on a difficult legacy corpus.” That reset cost time, but it also dramatically reduced the risk of continuing down a path that looked good while still producing unreliable answers.

The current direction is justified because it is now:

- measurable
- staged
- more trustworthy
- more sustainable from a cost perspective
