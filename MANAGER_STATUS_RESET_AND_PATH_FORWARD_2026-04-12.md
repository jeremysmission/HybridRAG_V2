# Manager Status Reset And Path Forward 2026-04-12

## Why This Update Is Different

My last status update was still based on the original V1 path and the assumption that I was closing in on a usable demo. Since then, I found a hard limitation in V1: it could retrieve documents, but it could not aggregate reliably enough to support the type of answers I need to demonstrate. Rather than force a brittle demo, I stopped treating V1 as the main path, kept the pieces that were actually working, and rebuilt the system into a cleaner two-application design.

## Architecture Reset

The current system is now split into:

- `CorpusForge`
  - upstream ingest
  - normalization
  - export packaging
  - integrity checks
- `HybridRAG_V2`
  - import into the searchable store
  - retrieval
  - entity extraction
  - evaluation
  - answer generation

This was not cosmetic refactoring. It was necessary to separate upstream data preparation from downstream retrieval and reasoning so I could identify which parts were actually trustworthy.

## What I Found

The biggest issue I uncovered was in the first-pass entity extraction layer. It was populating business-facing fields like purchase orders and part numbers with security-control and cyber-governance identifiers. That means the system could look operational while still producing misleading structured answers. This is the main reason I stopped the blind rerun path and shifted from “demo soon” to “make the pipeline trustworthy first.”

Examples of what was going wrong:

- purchase order fields were being polluted by control-family codes
- part-number fields were being polluted by STIG / DISA / MITRE-style identifiers
- a full rerun without quality gates would have consumed time and produced another dirty store

## What I Have Accomplished Since The Pivot

Over the last stretch, I have been converting the system from a fragile prototype path into a measurable, production-shaped pipeline.

Completed work includes:

- split the architecture into `CorpusForge` and `HybridRAG_V2`
- hardened workstation/install paths so the system is actually operable
- fixed import/index reliability problems
- added export integrity and metadata-contract checks between the two applications
- built a grounded 400-query evaluation corpus so progress can be measured honestly
- fixed the production-eval harness so the baseline is now believable instead of misleading
- hardened Tier 1 regex logic against known false-positive classes
- built an automated pre-rerun quality gate so future data additions can be screened before contaminating production
- documented the forward process for staged promotion instead of blind rerun

## Current Status

The project is now in a much better state than it was under V1, but the current bottleneck is not installer work or basic retrieval plumbing. The bottleneck is structured-data trust.

What is true right now:

- retrieval is real and usable
- the rebuilt architecture is in place
- the evaluation corpus is in place
- the main remaining gating item is a clean Tier 1 rerun on top of the new quality controls

## Why It Took Longer Than Expected

I underestimated how many hidden reliability issues were still sitting underneath a “working” demo path.

The main lesson is:

- I was closer to a demo than I was to a trustworthy system

Once I found that V1 could not aggregate reliably and that Tier 1 extraction was still capable of poisoning business-facing entities, the responsible move was to stop promising progress based on appearance and rebuild the path so it can be measured and trusted.

## Budget And Resource Constraint Context

An important part of this effort is that I am building this under tight cost constraints instead of using the more expensive default path.

The more conventional approach would be to contract out large parts of the design and cloud execution path, which would likely run on the order of:

- roughly `$15K-$20K` for the design and setup work alone
- then ongoing cloud costs in the range of roughly `$800/month`

Instead, I have been building a homegrown Python pipeline that uses a tiered approach to reduce how much expensive AI preprocessing is needed on the full 700GB corpus.

The design goal is:

- do the broad filtering and deterministic preprocessing locally
- reduce the expensive AI-heavy work to a much smaller fraction of the data
- use the temporarily available company-provided AWS AI services only where they add real value
- push the long-term query cost toward something closer to tens of dollars per month instead of hundreds or thousands

That cost discipline is part of why the architecture and gating work matters so much. If the pipeline is dirty, every rerun wastes not only time but also the cost savings the tiered design is supposed to create.

## What Happens Next

The next steps are now concrete and measurable:

1. Run the automated Tier 1 regex quality gate.
2. Run a controlled shadow extraction on a smaller chunk sample.
3. If it passes, run one clean full Tier 1 rerun.
4. Rerun the 400-query production baseline on the cleaned store.
5. Use that clean baseline to tighten remaining retrieval and routing problems.

This is the shortest credible path to a trustworthy demo and a trustworthy production direction.

## Estimated Timeline

The safest way to describe schedule is by milestone, not by implying that every remaining unknown is gone.

My current estimate is:

- roughly **2 more weeks** to get to a trustworthy demo candidate on the rebuilt path

That estimate assumes:

- the automated Tier 1 gate passes
- the shadow Tier 1 run does not reveal a new major collision class
- the clean Tier 1 rerun completes as expected
- the post-rerun baseline improves without exposing a completely new blocker

What that 2-week estimate covers:

- Tier 1 gate
- shadow extraction
- one clean full Tier 1 rerun
- rerun of the 400-query baseline
- final tightening on the highest-value remaining retrieval/routing issues
- preparation of a more trustworthy demo candidate

What it does **not** mean:

- full production hardening of every path
- "answer any question" maturity with no further iteration
- completion of all future automation and promotion work

If asked for the shortest honest answer:

"About two weeks to get to a trustworthy demo candidate on the rebuilt architecture, assuming the clean rerun behaves the way the new quality gates suggest it should."

## Non-Technical Summary

Plain-English version:

I found that the earlier system could retrieve documents but could not support reliable structured answers. I rebuilt the pipeline into two cleaner applications, hardened the install/import/export path, built a real evaluation set, and added automated quality gates so future data updates can be checked before they pollute production. I am now at the stage where I can do one controlled shadow run and one intentional clean rerun, instead of repeatedly losing time to dirty reruns.

## Manager Framing For A Non-Technical Audience

If the audience is non-technical, the easiest honest framing is:

- this is the program's first AI project
- the source material comes from many years of legacy data
- the data was not originally created for an AI system
- naming, security labels, identifiers, and document conventions are inconsistent across that history
- that means the hard part is not only "building an AI model"
- the hard part is teaching the system which patterns are real business information and which patterns only look similar

Plain-English version using that framing:

"This has turned into the normal growing pains of a first AI project built on top of about 15 years of legacy data. The old data was never designed for an AI system, so it contains inconsistent naming conventions, mixed document styles, and codes that look alike even when they mean very different things. The system was starting to confuse real business identifiers with security-control and technical codes, which would have made the answers look polished but not trustworthy. Instead of forcing a demo on top of that, I split the system into cleaner parts, added quality checks, and built a safer process so future data can be screened before it reaches production. The extra time is going into making the system dependable rather than just impressive on the surface."

Additional budget framing if useful:

"I am also doing this under a cost-control model. The standard cloud-heavy path for something like this can get expensive quickly. I am deliberately building a tiered pipeline that minimizes expensive AI passes over the full corpus and keeps long-term usage costs low. That means a little more engineering up front, but it is what gives us a realistic path to something operational without turning it into a high-cost recurring service."

## Very Short Manager Version

If a shorter version is needed:

"I found that the original path looked closer to a demo than it really was. Because this is our first AI project and it sits on top of roughly 15 years of inconsistent legacy data, I had to stop and harden the pipeline so the system does not confuse business information with technical/security codes. I split the architecture, built the quality gates, and now I am at the point where I can do one controlled clean rerun instead of wasting more time on unreliable runs. My current estimate is about two weeks to get to a trustworthy demo candidate on the rebuilt path."

## Short Spoken Version

"I had to reset the architecture after finding that the original version could retrieve documents but could not aggregate reliably enough for the kind of answers we need. I split the system into an upstream export app and a downstream retrieval/evaluation app, fixed several hidden reliability issues, built a grounded 400-query evaluation corpus, and added automated quality gates to prevent bad data from contaminating production. The next milestone is one controlled shadow extraction, then one clean Tier 1 rerun, then a fresh measured baseline on the rebuilt system."
