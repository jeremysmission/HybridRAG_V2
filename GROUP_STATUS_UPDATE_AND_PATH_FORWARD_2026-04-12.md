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
- adapting the design to what was actually available at each stage

That means some of the elapsed time has gone into getting the project into a state where the engineering work could be done correctly. In particular, establishing the working database was slowed by more than a month of stop-and-go downloading under proxy/network constraints, and productivity was also affected by two-machine admin-access instability plus the need to solve GPU-vs-CPU preprocessing compatibility on corpus-scale jobs.

### 3. Intentional cost discipline

I am deliberately not taking the most cloud-heavy path. A more vendor-heavy or cloud-heavy design could be much more expensive up front and monthly. Instead, I am building a tiered Python pipeline that uses cheaper deterministic processing first and reserves the more expensive AI work for the smaller subset that really needs it.

That is why the architecture split and quality gates matter: they are what make the low-recurring-cost model realistic.

A recent positive change is that the company has only very recently released an internal AI toolkit with temporary access to OSS-20B and OSS-120B through AWS. That gives me a practical way to use stronger AI only on the remaining heavy preprocessing tasks, while still preserving the overall low-cost tiered design instead of moving to a broad cloud-heavy workflow. It also adds a new engineering burden: learning the AWS infrastructure side quickly enough to use the toolkit correctly without creating hidden cost or configuration problems. Because this path runs through government AWS rather than standard commercial AWS, it carries its own extra restrictions and integration friction.

## What Has Been Completed

Completed work includes:

- architecture reset into `CorpusForge` and `HybridRAG_V2`
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

- **Tier 1**: fast deterministic extraction across the full corpus
- **Tier 2**: model-based entity extraction on a narrower subset
- **Tier 3**: the most expensive hard-tail reasoning/relationship path

This design exists to:

- control cost
- preserve speed
- improve reliability
- avoid running the heaviest AI path over everything

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
