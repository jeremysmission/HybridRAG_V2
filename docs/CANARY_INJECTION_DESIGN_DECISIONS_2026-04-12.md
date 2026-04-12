# Canary Injection Design Decisions

**Author:** Task #18 analysis reviewer  
**Repo:** `C:\HybridRAG_V2`  
**Task:** #18  
**Purpose:** Record the main alternatives rejected while designing the canary methodology so future implementers do not quietly reintroduce them

---

## Why This File Exists

The main methodology doc is the forward plan. This companion note records the alternatives that were considered and rejected, along with the reason each one was rejected.

That matters here because several design choices in the canary plan are not cosmetic. They define the trust boundary for demo-day aggregation claims.

---

## Decision 1 — Reject `CAN-*` As The Primary Synthetic Namespace

### Rejected option

Use the sample brief's suggested prefixes:

- `CAN-PO-*`
- `CAN-RG213-*`
- `CAN-*` more broadly

### Why it was rejected

The live read-only entity store already contains real entities matching `CAN-%`, including real-looking `PART` values such as `CAN-2005`, `CAN-2004`, `CAN-1210`, `CAN-1209`, and `CAN-1208`.

That means `CAN-*` is not collision-resistant in this corpus.

### Chosen alternative

Use a validation namespace built around `VAL*` and `VALCAN*`, including:

- `VALPO-*`
- `VALPART-*`
- `VALSITE-*`
- `_VALCAN_2026`
- `valcanary_*` filenames

### Why the chosen option is better

It was checked against the live read-only store and is currently collision-free. It also reads clearly as validation data rather than real operational data.

---

## Decision 2 — Reject Hidden Blend-In Canaries For The Live Demo

### Rejected option

Inject synthetic records so they blend visually into the corpus and do not disclose them on stage unless asked.

### Why it was rejected

The audience for this demo is procurement-sensitive and likely to care about trust, controls, and transparency. A hidden blend-in strategy risks looking deceptive if discovered, even if the underlying method is technically sound.

The external research reviewed for Task #18 also leaned toward explicit transparency and auditability for public-sector and enterprise audiences.

### Chosen alternative

Use transparent disclosure:

- state that two demo questions are validation controls,
- explain that the validation pack contains synthetic records with pre-known answers,
- then transition to three narrow real-data proof questions.

### Why the chosen option is better

It aligns with the overnight demo research, fits the public-sector trust model, and keeps the credibility boundary explicit: synthetic controls prove the aggregation path, while narrow real counts prove limited real-data utility.

---

## Decision 3 — Reject “Canaries Prove Whole-Corpus Totals” Without A Frozen Real Baseline

### Rejected option

Use canary injection alone as justification for claims such as:

- total purchase orders in the corpus,
- total unique part numbers across all sites,
- total failures in the entire demo corpus.

### Why it was rejected

The current live V2 entity store still has known pollution in the `PO` and `PART` types. Adding a deterministic canary pack does not make the underlying real baseline trustworthy.

Without a frozen and independently verified baseline, the arithmetic looks clean while the underlying real count may still be wrong.

### Chosen alternative

Use one of two honest patterns:

1. canary-only aggregation controls, or
2. `frozen_real_baseline + deterministic_canary_delta`

### Why the chosen option is better

It prevents the canary mechanism from becoming a false confidence amplifier. The method stays honest even if regex cleanup or entity normalization slips.

---

## Decision 4 — Reject Skip Lists And Deferred-Format Logic As The Primary Canary Toggle

### Rejected option

Use skip lists, defer rules, or implicit policy logic as the main mechanism for including or excluding canaries from a run.

### Why it was rejected

Those controls are harder for operators to reason about quickly during a rehearsal. They also raise the risk of partial inclusion, configuration drift, or a mismatch between what the operator thinks is in the run and what actually gets imported.

### Chosen alternative

Use a dedicated subtree rooted at:

```text
E:\CorpusTransfr\verified\IGS\_VALCAN_2026\
```

Then:

- include that subtree for demo runs,
- omit it for production runs,
- optionally add `--exclude-source-glob "*_VALCAN_2026*"` and `--exclude-source-glob "*valcanary*"` as a secondary safety net.

### Why the chosen option is better

Folder-scope inclusion and exclusion is operator-visible, easy to audit, and fits the current import path without requiring a new policy layer.

---

## Decision 5 — Reject Scattering Canaries Through Real Folders

### Rejected option

Distribute canary files across existing real program-management, logistics, field, and cyber folders so retrieval sees them in a more “natural” mix.

### Why it was rejected

That improves realism at the cost of operational clarity and cleanup safety. It also increases the risk that canaries leak into future non-demo workflows or become hard to exclude later.

### Chosen alternative

Keep canaries in one isolated subtree with persona-specific internal bundles.

### Why the chosen option is better

It preserves realism inside the canary pack while keeping provenance, exclusion, and auditability simple.

---

## Decision 6 — Reject Pure Answer-String Validation

### Rejected option

Treat the model's final answer string as the only validation target.

### Why it was rejected

That hides whether the count actually landed in the stores, whether the right records were retrieved, and whether the answer is accidentally correct for the wrong reason.

### Chosen alternative

Require dual proof:

- query-pipeline validation through a known-answer script,
- independent store-side verification through SQL and LanceDB checks.

### Why the chosen option is better

It separates user-visible correctness from storage correctness and makes failures easier to localize.

---

## Decision 7 — Reject Randomized Or Ad-Hoc Canary Authoring

### Rejected option

Hand-author a one-off validation pack or generate it with nondeterministic timestamps, randomized identifiers, or variable document phrasing.

### Why it was rejected

That introduces drift in chunking, embeddings, entity counts, and answer keys. It makes rehearsal-to-rehearsal comparisons noisy and weakens auditability.

### Chosen alternative

Specify a deterministic generator that emits the same 40 documents, the same fact model, the same filenames, and stable content on every run.

### Why the chosen option is better

It makes the canary pack reproducible and suitable for repeated pre-demo validation.

---

## Bottom Line

The chosen design is intentionally conservative:

- collision-resistant namespace,
- isolated subtree,
- transparent disclosure,
- deterministic generation,
- dual verification,
- no fake “whole-corpus truth” claims without a frozen baseline.

That conservatism is the point. V1 died on aggregation credibility; Task #18 should not solve that with a clever-looking but fragile demo trick.
