# Tiered Extraction Theory Of Operation 2026-04-12

## Purpose

This document explains what "tiers" means in the current system, why the tiered design was chosen, and what each tier is responsible for.

Important clarification:

- when I say **tiers** here, I mean **extraction tiers**
- I do **not** mean test tiers, QA tiers, or deployment environments
- import into LanceDB happens **before** the extraction tiers and is not itself a tier

## Short Version

The tiered design exists because the corpus is too large and too messy to process every document with the heaviest AI method.

So the system is designed to:

1. do the cheapest and broadest work first
2. reserve more expensive AI work for the smaller subset where it is actually needed
3. keep recurring cost and rerun cost under control
4. improve trust by separating easy, high-volume extraction from harder, ambiguous cases

## Why I Chose Tiers

I chose a tiered approach for three reasons:

### 1. Cost

Running heavy AI extraction against the full 700GB corpus would be expensive up front and expensive to maintain. A tiered approach lets the system use:

- deterministic local processing for the broad pass
- narrower model-based extraction only where it adds clear value
- the heaviest AI path only for the hardest remaining cases

That is how the system stays on a path toward low recurring query cost instead of becoming a high-cloud-burn design.

### 2. Speed

Not every extraction problem deserves the same amount of compute.

- many document facts can be found with deterministic patterns very quickly
- some entity types need a model, but only on a filtered subset
- only the hardest relationship or reasoning cases need the most expensive path

That keeps the system operational at corpus scale.

### 3. Reliability

A tiered system is easier to debug and govern.

Instead of one monolithic AI step doing everything, each layer has a clear responsibility:

- broad candidate generation
- richer entity recognition
- hardest-tail reasoning

That makes it easier to measure, test, and quarantine failures.

## The Tier Definitions

## Tier 1

**What it is:**

- fast deterministic extraction
- regex and rule-based candidate generation
- runs over the full corpus

**What it targets well:**

- part numbers
- purchase-order-like values
- dates
- emails
- phones
- serials
- clearly structured identifiers

**What it is good at:**

- scale
- speed
- low cost
- repeatability

**What it is bad at:**

- ambiguity
- messy context
- human names and organizations in noisy text
- complex relationships

**Important design note:**

Tier 1 should be treated as a **candidate generator**, not the final truth layer. That is one of the most important lessons learned from this project.

## Tier 2

**What it is:**

- model-based entity extraction using GLiNER
- runs on a filtered subset, not the full corpus path in the same naive way
- GPU-backed when available

**What it targets well:**

- people
- organizations
- sites/locations
- failure modes
- entity types that regexes handle poorly

**What it adds:**

- better recall on messy real-world language
- cleaner handling of names and organization/location mentions
- coverage for entity types that do not have stable deterministic shapes

**Why it is not Tier 1:**

- slower
- more resource-intensive
- less appropriate for a full-corpus broad pass

Tier 2 exists because some entity types are not practically recoverable from regex alone without unacceptable error.

## Tier 3

**What it is:**

- the expensive hard-tail path
- reserved for flagged complex cases
- intended for relationship-heavy or reasoning-heavy extraction

**What it targets:**

- difficult relationship extraction
- complex cross-field or cross-sentence interpretation
- cases where deterministic patterns and lighter NER are not enough

**Why it is last:**

- highest cost
- slowest path
- easiest place to waste money if used too early or too broadly

Tier 3 should only touch the subset that genuinely needs it.

## Order Of Operations

The intended order is:

1. Forge prepares the export
2. V2 imports into LanceDB
3. Tier 1 runs broad deterministic extraction
4. Tier 2 runs richer entity extraction on the narrower subset
5. Tier 3 handles the hardest remaining cases

Not every document or question needs every tier.

## Non-Technical Explanation

Plain-English version:

The system works in layers so it does not waste expensive AI effort on easy problems. The first layer is a fast scan that catches the obvious, structured things. The second layer is a smarter model that handles the kinds of names and entities that are harder to recognize. The third layer is reserved for the hardest relationship and reasoning cases. This lets the system scale to a very large corpus without turning every document into an expensive AI job.

## Technical Explanation

Engineer-facing version:

The tiered design is a cost- and reliability-driven decomposition of the extraction problem. Tier 1 is a high-throughput deterministic candidate-generation pass over the full imported store. Tier 2 is a narrower GPU-backed NER pass for entity classes with weak regex separability. Tier 3 is the hard-tail reasoning/relationship layer and should remain a flagged subset path, not a corpus-wide default. The point is to keep broad preprocessing cheap, isolate ambiguity to later stages, and avoid letting the most expensive model path define the operating cost of the system.

## Why This Matters For Production

The tiered design is not only about performance. It is also about future maintenance.

By production, the system should:

- process new data in staged layers
- gate lower tiers before promoting results
- only invoke heavier tiers when justified
- keep recurring costs low enough to be sustainable

That is how the system avoids becoming both:

- too expensive to run
- too brittle to trust

## One-Sentence Version

If I had to explain tiers in one sentence:

"The system uses a layered extraction strategy so that cheap, fast, high-volume logic handles the easy cases first, stronger AI models handle the narrower ambiguous cases second, and the most expensive reasoning step is reserved only for the hardest tail."

