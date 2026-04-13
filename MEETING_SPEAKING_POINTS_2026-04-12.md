# Meeting Speaking Points 2026-04-12

## One-Line Status

- I had to reset the AI architecture because V1 retrieval was stronger than its aggregation trust.

## What Changed

- V1 was not discarded blindly; I kept what worked and split the system into:
  - `CorpusForge` for ingest/export/integrity
  - `HybridRAG_V2` for import/retrieval/extraction/eval/answers

## Why It Took Time

- This is our first AI project on top of roughly 15 years of legacy data.
- The data was never designed for AI use.
- Naming, security labels, identifiers, and document structure are inconsistent.
- IT/admin access across two machines was unstable and required resets.
- Proxy/network friction made establishing the working database a long stop-and-go process.
- Preprocessing compatibility had to be solved so corpus-scale work could run on CUDA/GPU instead of CPU-only paths.
- The system was at risk of confusing real business identifiers with technical/security codes.
- I stopped the blind rerun path so I would not waste another full day producing a dirty store.

## What I Finished

- architecture reset into Forge + V2
- installer/workstation reliability improvements
- import and index reliability improvements
- export integrity and metadata-contract checks
- grounded 400-query evaluation corpus
- believable evaluation harness
- Tier 1 regex hardening
- automated pre-rerun quality gate
- staged promotion plan for future data additions

## What The Main Technical Problem Was

- Tier 1 was polluting business fields like purchase orders and part numbers with security-control and cyber-governance identifiers.
- That means the system could look polished while still producing misleading answers.

## What “Tiers” Means

- Tier 1: fast deterministic extraction over the full corpus
- Tier 2: model-based entity extraction on a narrower subset
- Tier 3: the most expensive hard-tail reasoning/relationship path

## Why I Chose Tiers

- to keep cost down
- to keep speed workable on a very large corpus
- to reserve expensive AI for the subset that really needs it
- to make the pipeline easier to debug and trust

## Cost Story

- A more cloud-heavy or vendor-heavy path could be much more expensive up front and monthly.
- I am building a tiered Python pipeline to reduce expensive AI passes and keep long-term operating cost low.
- The extra engineering up front is what makes the lower recurring-cost model possible.
- We now also have a newly released company AI toolkit with temporary OSS-20B / OSS-120B access through AWS.
- I plan to use that selectively for the remaining heavy preprocessing tasks, without abandoning the low-cost tiered design.
- That also means learning the AWS infrastructure side on the fly so I can use it correctly without opening up hidden cloud-cost issues.
- It is government AWS, not standard commercial AWS, so it comes with extra restrictions and setup friction.
- Even getting access required application and working through an AI Staff Engineer while provider-side issues were debugged.

## Current Status

- Retrieval is real and usable.
- The architecture reset is done.
- The remaining gating item is a clean Tier 1 rerun on top of the new quality controls.

## Next Steps

1. run automated Tier 1 gate
2. run shadow Tier 1 sample
3. if clean, run one full Tier 1 rerun
4. use the company OSS toolkit selectively for remaining heavy preprocessing
5. rerun the 400-query baseline on the cleaned store
6. finish targeted retrieval/router tightening

## Schedule

- Current estimate: about 2 more weeks to a trustworthy demo candidate on the rebuilt path

## Closing Line

- I am no longer trying to make it look close. I am making it trustworthy enough to stand behind.
