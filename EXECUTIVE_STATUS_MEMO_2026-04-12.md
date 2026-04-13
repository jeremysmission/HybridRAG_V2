# Executive Status Memo 2026-04-12

## Subject

Status Update: AI Prototype Reset, Risk Reduction, and Path Forward

## Summary

I need to reset expectations from my earlier V1 status. The original version was closer to a retrieval demo than to a trustworthy production-capable system. It could find relevant documents, but it could not aggregate reliably enough for the kind of answers we need to demonstrate. Rather than force a brittle demo, I shifted to a cleaner architecture, kept the parts that were working, and rebuilt the rest into a more disciplined two-application pipeline.

## What Changed

The system is now split into:

- `CorpusForge` for upstream ingest, normalization, export, and integrity checks
- `HybridRAG_V2` for import, retrieval, entity extraction, evaluation, and answer generation

This was necessary because the underlying source data spans many years and was not originally created for AI use. It contains inconsistent naming conventions, mixed document styles, and identifiers that look similar even when they mean very different things. That created a risk that the system would confuse real business information with technical and security codes.

## What I Found

The main issue I uncovered was in the first-pass extraction layer. It was sometimes classifying security-control and technical codes as if they were business entities such as purchase orders and part numbers. That means the system could appear polished while still producing misleading answers. A full rerun without fixing that problem would have wasted time and created another dirty dataset.

## What I Completed

Over the last stretch, I focused on turning the prototype into something measurable and trustworthy:

- reset the architecture into two cleaner applications
- hardened workstation install and import paths
- added export integrity and metadata-contract checks
- built a grounded 400-query evaluation corpus
- fixed the evaluation harness so the baseline is believable
- hardened Tier 1 extraction rules against known false positives
- added an automated pre-rerun quality gate
- documented a staged promotion process so future data additions can be screened before reaching production

This also included a meaningful amount of enabling work around approvals and environment readiness. I did not start with every AI use case, software path, and hardware path already cleared and available. Part of the effort has been getting the project into a state where the technical work could be done responsibly, including a long stop-and-go period caused by proxy/network friction while downloading and establishing the working database, repeated IT/admin-access interruptions across two machines, and software compatibility work needed to keep preprocessing on the GPU path instead of much slower CPU-only paths. That environment is now finally coming together.

## Cost And Delivery Context

This work is also being done under a deliberate cost-control strategy.

A more typical vendor-heavy or cloud-heavy path for this kind of effort could easily involve:

- approximately `$15K-$20K` in design/setup effort
- then recurring cloud costs around `$800/month`

I am instead building a tiered Python-based pipeline that minimizes expensive AI passes over the full 700GB corpus. The intent is to push most of the broad preprocessing into lower-cost deterministic stages, reserve the heavier AI work for the reduced subset where it is actually needed, and drive the long-term query-cost model toward something much smaller. That is part of why the architecture split and quality gates matter: if the pipeline is not trustworthy, reruns waste both schedule and the cost savings this design is meant to deliver.

A recent positive development is that the company has only very recently released an internal AI toolkit that includes temporary access to OSS-20B and OSS-120B models through AWS. I am planning to use that selectively for the remaining heavy preprocessing tasks where it creates real leverage, while still avoiding an open-ended cloud-heavy cost model. That also requires me to learn the AWS infrastructure side on the fly so the new capability can be used correctly and cost-consciously. Because this is government AWS rather than standard commercial AWS, it adds an additional layer of restrictions and setup complexity.

## Current Status

The system is in a much stronger state than V1, but the remaining gating item is a clean Tier 1 rerun using the new quality controls. The current path forward is now concrete:

1. run the automated Tier 1 quality gate
2. run a controlled shadow extraction on a smaller sample
3. if it passes, run one clean full Tier 1 rerun
4. use the newly available company OSS toolkit selectively for the remaining heavy preprocessing tasks
5. rerun the evaluation baseline on the cleaned store
6. use that clean baseline to finish retrieval and routing improvements

## Estimated Timeline

My current estimate is approximately **2 more weeks** to reach a trustworthy demo candidate on the rebuilt path.

That estimate is based on the current gated sequence:

1. automated Tier 1 quality gate
2. controlled shadow extraction
3. one clean full Tier 1 rerun
4. rerun of the evaluation baseline
5. targeted tightening of the highest-value remaining issues

This is a milestone estimate, not a claim that every remaining unknown is gone. It is the estimate for a trustworthy demo candidate on the current architecture, not for complete production maturity.

## Why The Time Was Necessary

The time was not spent polishing a demo. It was spent preventing a bad demo and avoiding repeated wasted reruns. The key lesson is that I was closer to a visible prototype than to a trustworthy system. I chose to correct that now rather than build on top of unreliable data.

## Bottom Line

This is no longer an open-ended debugging effort. The architecture reset is done, the main data-quality issue has been identified, and the next steps are measurable and controlled. The project is now on a safer path toward a trustworthy demo and a production-ready design.

## Email-Ready Version

Subject: Status Update on AI Prototype and Path Forward

I need to reset expectations from my earlier V1 status. I found that the original version was closer to a retrieval demo than to a trustworthy production-capable system. It could find relevant documents, but it could not aggregate reliably enough for the kind of answers we need to demonstrate.

Rather than force a brittle demo, I split the system into two cleaner applications: CorpusForge for upstream ingest/export/integrity, and HybridRAG_V2 for import, retrieval, extraction, evaluation, and answer generation. This was necessary because the source material spans many years of legacy data that was never designed for AI use. It contains inconsistent naming conventions, mixed document styles, and identifiers that look alike even when they mean very different things.

The main issue I uncovered was that the first-pass extraction layer was sometimes classifying security-control and technical codes as if they were business entities such as purchase orders and part numbers. That would have made the system look polished while still producing misleading answers. I stopped the blind rerun path, hardened the extraction logic, added automated quality gates, and built a grounded evaluation set so progress can be measured honestly.

At this point, the architecture reset is complete and the next steps are clear: run the automated Tier 1 gate, run a controlled shadow extraction, perform one clean full Tier 1 rerun if that passes, selectively use the newly available company OSS toolkit for the remaining heavy preprocessing tasks, and then rerun the evaluation baseline on the cleaned store. My current estimate is about two weeks to get to a trustworthy demo candidate on this rebuilt path, assuming the clean rerun behaves as expected. The extra time has gone into making the system dependable instead of just making it look close, while also keeping the long-term operating-cost model much lower than a more cloud-heavy approach.
