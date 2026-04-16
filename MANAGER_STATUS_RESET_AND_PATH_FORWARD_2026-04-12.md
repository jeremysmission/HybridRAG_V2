# Manager Status Reset And Path Forward 2026-04-12

## Why I Am Sending A Reset

To make this update easier to follow, I want to define the main terms first.

- **HybridRAG**
  - short for **Hybrid Retrieval-Augmented Generation**
  - in this project, that means combining semantic/vector retrieval with text/keyword retrieval instead of relying on only one search method
- **V1**
  - the original HybridRAG implementation
  - this was the first version of the system and the path I previously described as getting close to a demo
- **V2**
  - the rebuilt current system, `HybridRAG_V2`
  - this is the new architecture I refer to below when I describe the reset and the current path forward
- **CorpusForge**
  - the new upstream application that prepares, normalizes, and exports the corpus before V2 imports and uses it

## How The Project Evolved

The project did not originally begin as two separate applications.

It started as a single HybridRAG effort, which I now refer to as `V1`. In that original form, ingest, preprocessing, retrieval, extraction, and answering were still too tightly coupled. That was enough to make early proof-of-concept progress, but it also made it too easy for the system to look closer to done than it really was.

Once I pushed V1 harder against the real enterprise program drive, it became clear that I needed a cleaner separation of responsibilities. That is why the project evolved into:

- `CorpusForge`
  - the upstream corpus-preparation side
  - responsible for ingest, normalization, chunking/export, and integrity checks
- `HybridRAG_V2`
  - the downstream retrieval-and-answering side
  - responsible for import, retrieval, extraction, evaluation, and answer generation

So the move from one HybridRAG code path into `CorpusForge` plus `HybridRAG_V2` was not cosmetic refactoring. It was the architectural response to what I learned from V1.

My last major update was still based on the original V1 path and the assumption that I was closing in on a usable demo. Since then, I found that the project was closer to a retrieval demo than to a trustworthy AI system. That is why I need to reset the status, explain what changed, and explain why the work has taken longer than I originally expected.

The short version is:

- V1 proved that the program's data could be searched and retrieved with AI techniques
- V1 did **not** prove that the system could answer business-facing questions reliably
- once I tested it more seriously against the real enterprise program drive and real aggregation-style questions, I found issues that would have made a demo look better than the underlying system really was
- rather than force a brittle demo, I split the work into a cleaner architecture and rebuilt the path around quality gates and measurable progress

## Where I Started

The original goal was to build an AI system that could work over roughly 15 years of mixed-format legacy program data, answer questions over that corpus, and do it without creating a large recurring cloud bill.

I originally pursued that through a single-system V1 path. That version did accomplish something important:

- it proved that the corpus could be indexed
- it proved that relevant documents could be retrieved
- it proved that a homegrown Python approach could do more than a toy proof of concept

At that stage, it looked like I was getting close to a demo.

## What I Ran Into Before The Core AI Problems

Before the main AI design issues were even fully visible, a significant amount of setup friction slowed progress:

- I had to identify and submit multiple AI use cases and software paths for approval
- I had to work through hardware and workstation readiness constraints
- I had to deal with unstable admin access across two machines, including getting bumped off one machine and needing IT resets
- I had to spend more than a month dealing with stop-and-go proxy/network issues just to get the working database and dependencies established
- I had to solve software compatibility issues so heavy preprocessing would stay on CUDA/GPU instead of falling back to much slower CPU-only execution
- I only very recently got access to the company's new AI toolkit path, which runs through government AWS and came with its own approval, setup, and integration learning curve

In other words, I did not start this effort with a clean, fully approved, fully provisioned AI environment. Part of the elapsed time went into getting the project into a state where the technical work could happen correctly at all.

## What Failed In V1

The major turning point came when I pushed V1 harder against the real enterprise program drive and tried to use it for the kind of answers that matter to the program, not just document retrieval.

That is where I found the hard limitation:

- V1 could retrieve relevant documents and chunks
- but it could not aggregate reliably enough to support trustworthy business-facing answers

This was not a small tuning issue. It was a structural issue.

On the actual enterprise program data, many identifiers look similar even when they mean very different things. Purchase orders, part numbers, technical report IDs, security-control identifiers, and cyber-governance codes all coexist in the same legacy drive. V1 was capable of finding related documents, but when I pushed it toward counting, rollups, and structured answers, the first-pass extraction layer was still confusing some of those categories.

That meant the system could produce answers that looked plausible while still being semantically wrong.

The biggest examples were:

- purchase-order style fields being polluted by security-control and report-code patterns
- part-number style fields being polluted by STIG / DISA / MITRE / security standard-style identifiers
- aggregation-style answers looking more mature on the surface than they really were underneath

That is the key reason I stopped treating V1 as "almost done."

## Why I Reset The Architecture

Once I found those issues, I made the decision to stop trying to force the one-system V1 path and instead split the system into two cleaner applications with clearer responsibilities.

The current architecture is:

- `CorpusForge`
  - upstream ingest
  - normalization
  - chunk/vector export
  - integrity checks
- `HybridRAG_V2`
  - import into the searchable store
  - retrieval
  - entity extraction
  - evaluation
  - answer generation

This was not a restart from zero. I kept what was actually working and repurposed it into a cleaner design. The point of the split was to separate upstream data preparation from downstream retrieval and reasoning so I could isolate failures and stop hiding weak assumptions inside one large path.

## What I Have Been Doing Since The Reset

Since the pivot away from V1, the work has been focused on turning the project from a fragile prototype path into a measurable, production-shaped pipeline.

Completed work includes:

- splitting the system into `CorpusForge` and `HybridRAG_V2`
- hardening installer and workstation setup so the system is actually operable
- fixing import/index reliability issues
- adding export integrity and metadata-contract checks between the two applications
- building a grounded 400-query evaluation corpus so progress can be measured honestly
- fixing the production-evaluation harness so the baseline is believable
- hardening Tier 1 extraction logic against known false-positive classes
- building automated quality gates so future data additions can be screened before contaminating production
- documenting a staged promotion process instead of a blind rerun process

The important change here is that I am no longer relying on "it seems to work." I now have an evaluation set, quality gates, and a cleaner architecture that let me measure what is actually trustworthy.

## How The Design Evolved

The design has also evolved in a deliberate cost-controlled direction.

Instead of taking the more expensive default path of pushing everything through a cloud-heavy AI workflow, I have been building a tiered system in homegrown Python.

What I mean by a tiered approach is:

- broad deterministic preprocessing and filtering happen first
- the corpus is reduced before the heaviest AI steps are used
- later stages only use stronger AI where it adds real value
- future data should be staged, checked, and promoted only if it passes quality gates

This matters for two reasons:

1. it reduces the chance of polluting the system with bad extracted data
2. it reduces both startup cost and long-term maintenance cost

That cost discipline is important because outsourcing or cloud-first approaches for a sensitive data-sensitive RAG effort of this size can become expensive quickly. I am trying to build something that is more affordable to sustain over time, not just something flashy in the short term.

## What I Mean By "Tiers"

One thing that is easy to miss in these updates is what I mean when I say the system is now "tiered."

In practical terms, the tiers are layers of extraction work with different cost, speed, and precision characteristics.

I chose that design because the corpus is too large and too messy to run the heaviest AI method across everything by default.

The current tiers mean:

- **Import**
  - this is the step before the tiers
  - the prepared chunk/vector export is loaded into the searchable store so the system has a normalized indexed baseline to work from
- **Tier 1**
  - fast broad-pass extraction
  - this is the deterministic high-volume layer that scans the full corpus for structured candidate values such as dates, contacts, purchase-order-like values, and part-number-like values
  - it is optimized for throughput and scale, not for final truth
- **Tier 2**
  - model-based entity extraction on the narrower subset where deterministic patterns are not enough
  - this is where people, organizations, locations, and messier entity classes are handled more intelligently
- **Tier 3**
  - reserved for the hardest relationship-heavy or ambiguity-heavy cases
  - this is the most expensive layer and should only touch the smaller tail that truly needs deeper reasoning or relationship extraction

The reason for using tiers is both technical and financial:

- the easier work should be handled by cheaper local logic first
- only the narrower ambiguous portion should use the more expensive AI path
- this gives me a realistic path to lower recurring cost and lower maintenance burden after the initial build

So when I say "tiered," I do not mean unnecessary complexity for its own sake. I mean a controlled layered approach that keeps the expensive AI work focused only where it adds the most value.

## What The Tiered Strategy Saves

The tiered strategy is also one of the main reasons this project is still financially realistic.

Without a tiered design, the default path would be to run heavier AI extraction and enrichment broadly across the corpus. On a corpus of this size, that would increase both:

- processing time
- external model cost

By using a tiered approach instead, I am deliberately:

- doing the broad deterministic and rule-based work locally
- keeping embeddings local on GPU where they are fast and effectively free once the workstation is in place
- reducing the amount of data that needs stronger model-based extraction
- reserving the heaviest AI path for the smaller subset where it creates the most value

That saves money in two ways:

1. it lowers the number of expensive model calls during the initial build
2. it keeps the steady-state production model from becoming dependent on a high monthly cloud burn

It also saves time in two ways:

1. it avoids spending heavy-model runtime on easy low-ambiguity cases
2. it lets the long-term maintenance path stay incremental, so future nightly or scheduled updates can be handled mostly offline rather than reprocessing the whole corpus with the most expensive path

In practical terms, this is the difference between:

- a broad cloud-heavy extraction design that is expensive to build and expensive to keep running
- and a staged local-first design that uses stronger remote AI only where it is worth the cost

That is a major part of the value I have been adding through the architecture redesign. I am not only trying to make the system work; I am trying to make it work in a way that the program can afford to maintain.

## What Changed Recently On The AI Infrastructure Side

A recent positive development is that the company only very recently released an internal AI toolkit that includes temporary access to OSS-20B and OSS-120B models through government AWS.

That is helpful, but it has not been plug-and-play. To even get to that point, I had to:

- apply for access
- work through an AI Staff Engineer while they debugged issues on their side
- learn a government AWS path on the fly instead of standard commercial AWS
- line up government AWS restrictions, Azure-style formatting expectations, the enterprise company AI endpoint layer, and OpenAI-compatible Jupyter workflows

The good news is that this path is finally becoming usable. My intent is not to abandon the tiered low-cost design, but to use this temporarily free company-provided AI selectively for the remaining heavy preprocessing tasks where it provides the most leverage.

## Why Spending Time On AWS Now Is Justified

The main reason this AWS work is worth doing now is that it applies to the expensive one-time build phase, not to the long-term steady-state operating model.

There is a big difference between:

- the initial conversion of the legacy corpus into AI-usable form
- and the ongoing incremental maintenance path after the system is established

The initial build includes the heaviest preprocessing tasks:

- large-scale chunking and normalization
- embeddings and enrichment
- model-assisted extraction on the hardest subset
- one-time conversion of old legacy content into a cleaner AI-ready architecture

That front-loaded work is where stronger remote AI capability helps the most, because it can shorten the one-time heavy lift on the hardest portion of the corpus.

The important point is that I am **not** designing the system to depend on that heavy remote AI path forever.

The intended long-term model is:

- do the one-time heavy build work now using the best temporarily available company capability where it truly helps
- keep the broad pass local and deterministic
- let nights-and-weekends or scheduled production windows handle smaller incremental updates offline
- reserve remote model usage for exceptional cases instead of making it the permanent default

That is why the AWS learning and setup time is justified. It is helping accelerate the hardest remaining one-time preprocessing and enrichment tasks without locking the program into a permanently high cloud bill. In other words, I am using temporary external leverage for the initial heavy lift while still designing the steady-state production model around lower-cost local and incremental processing.

There is also a timing advantage to using that path now rather than later. While the company toolkit access is temporarily free, it lets me process the hardest remaining enrichment and extraction subset at essentially zero model cost. If I deferred that work until after the free window or tried to do the same work through a paid general-purpose endpoint, the build would either take longer on local/offline resources or cost materially more in API usage. So part of the value here is being resourceful and using the temporary company capability while it is available, rather than missing that window and paying for the same heavy one-time work later.

That is the direct justification for the current time being spent on AWS. It is not a side project away from the main effort. It is part of the main effort because it creates the best available path for the remaining one-time heavy extraction and enrichment work while the company-provided models are temporarily available at little or no additional model cost.

## Current Status

The project is in a much better place now than it was under V1, but the current bottleneck is not basic retrieval anymore. The current bottleneck is structured-data trust.

What is true right now:

- the architecture reset is complete
- the core repos and pipeline boundaries are in much better shape
- retrieval is real and usable
- the evaluation corpus is in place
- the main gating item is a clean Tier 1 rerun on top of the new quality controls

That means I am no longer trying to guess my way to a demo. I now have a more disciplined path:

1. run the automated Tier 1 quality gate
2. run a controlled shadow extraction on a smaller sample
3. if that passes, run one clean full Tier 1 rerun
4. rerun the 400-query baseline on the cleaned store
5. then tighten the remaining retrieval and routing issues from evidence

## Why This Matters Across The Team

This work is not only relevant to the AI lane.

- For **program management**, it creates a more measurable and supportable path instead of a prototype that only looked close.
- For **logistics and material analysis**, it directly improves trust in purchase-order-like data, part numbers, inventories, packing lists, and procurement evidence.
- For **cyber security**, it prevents STIG / DISA / MITRE / security standard-style identifiers from being mistaken for business entities, which preserves a cleaner trust boundary.
- For **field engineers**, it strengthens retrieval and future structured use of site-install records, inventories, acceptance artifacts, and field documentation.
- For **network and infrastructure roles**, it explains why workstation reliability, proxy-aware installs, GPU/CUDA compatibility, and government AWS integration were real parts of the engineering work, not side distractions.

Part of the reason for documenting the reset this way is so each functional area can see how the current work supports their use case rather than feeling like this is only an abstract AI exercise.

## Why This Took Longer Than I Expected

The simplest honest explanation is this:

- I was closer to a demo than I was to a trustworthy system

Once I found that V1 could retrieve but not aggregate reliably enough, and once I found that the real enterprise program drive still contained enough identifier collisions to poison structured answers, the responsible move was to stop and harden the system instead of presenting something that would be hard to trust.

It is also important to understand that this kind of AI preprocessing work is not like installing a normal legacy software program. To make a large legacy corpus usable inside an AI system, it has to be chunked, embedded, enriched, indexed, extracted, audited, and revalidated. On a corpus of this size, those are compute-intensive one-time builds and conversions that can take days or weeks even before the final question-answering layer is ready.

## Timeline And What I Need Next

The safest way to describe the schedule is by milestone.

My current estimate is:

- roughly **2 more weeks** to get to a trustworthy demo candidate on the rebuilt path

That estimate assumes:

- the automated Tier 1 gate continues to pass
- the clean rerun behaves as expected
- the post-rerun baseline improves without exposing a completely new blocker

What that estimate covers:

- Tier 1 gate
- shadow extraction
- one intentional clean full Tier 1 rerun
- rerun of the 400-query baseline
- targeted tightening of the remaining highest-value retrieval/routing issues

What it does not mean:

- that every future automation task is finished
- that the system is already at full production maturity
- that every possible question type will be solved immediately after that demo candidate milestone

## Plain-English Summary

If I had to explain this in the simplest possible way:

This has turned into the normal growing pains of a first AI project built on top of many years of legacy data. The old data was never designed for AI use, so it contains inconsistent naming, mixed document styles, and codes that look alike even when they mean very different things. I found that the earlier version could find documents, but it could not yet support trustworthy counting and structured answers on the real enterprise program drive. Rather than force a fragile demo, I split the system into cleaner parts, added quality gates, and rebuilt the path so future data can be screened before it reaches production. The extra time has gone into making the system dependable rather than just impressive on the surface.

## Very Short Manager Version

If a shorter version is needed:

"I found that the original path was closer to a retrieval demo than to a trustworthy production-style AI system. On the real enterprise program drive, it could retrieve documents but could not aggregate reliably enough for business-facing answers because some business fields were still being polluted by technical and security identifiers. I reset the architecture into two cleaner applications, built quality gates and a grounded evaluation set, and I am now at the point where I can do one controlled clean rerun instead of wasting more time on blind reruns. My current estimate is about two weeks to get to a trustworthy demo candidate on the rebuilt path."
