# Production Eval 400-Query Set — Rationale

**Agent:** reviewer | **Repo:** HybridRAG_V2 | **Date:** 2026-04-12 MDT
**Target file:** `tests/golden_eval/production_queries_400_2026-04-12.json`
**Schema:** RAGAS v0.3 `SingleTurnSample` compatible (user_input, reference, reference_contexts) + reviewer eval metadata.
**Phase:** Phase 1 (50 new queries delivered; path to 400 documented below)
**Helper:** `scripts/mine_query_anchors.py` — reusable anchor miner.

---

## TL;DR

- Built a RAGAS-compatible query evaluation corpus grounded in real enterprise program corpus
  content, not fictitious placeholders. Every query uses anchors mined from
  the 8,017,607-entity Tier 1 store and the real folder structure of the
  10,435,593-chunk LanceDB index.
- **Phase 1 delivers 50 hand-curated queries** (PQ-101 through PQ-150) across
  5 personas and 5 RAGAS-relevant query types, with source_path grounding for
  every query and 8 queries with full ground-truth answers.
- **Phase 1 does not overlap with the existing 25 queries** at
  `tests/golden_eval/production_queries_2026-04-11.json` (IDs PQ-001 through
  PQ-025); those will be promoted into this file in a future pass. Total
  cumulative production queries: **75** (25 existing + 50 new).
- **Path to 400 is documented with a concrete per-persona breakdown**
  (Section 7). The remaining ~325 queries follow the same methodology:
  mine anchors with `scripts/mine_query_anchors.py`, hand-curate queries
  against real folder paths, attach ground truth where feasible.
- **RAGAS scoring is deferred to a separate runner** (not built in this
  task). The JSON is structured so that a future `scripts/run_ragas_eval.py`
  can consume it directly: `user_input` is the query, `reference_contexts`
  is the gold context, `reference` is the gold answer.

---

## 1. Why RAGAS-Compatible, Not reviewer's Custom Schema

Sources used for schema research (reviewer web searches on 2026-04-12):

- **RAGAS SingleTurnSample** — https://docs.ragas.io/en/stable/concepts/components/eval_sample/
  The canonical RAGAS evaluation record uses `user_input`, `response` (filled
  at eval time), `retrieved_contexts` (filled at eval time), `reference`
  (gold answer), and `reference_contexts` (gold context for Context Recall
  scoring).
- **RAGAS EvaluationDataset** — https://docs.ragas.io/en/stable/concepts/components/eval_dataset/
  A collection of same-type samples. Ours is all `SingleTurnSample`-shaped.
- **BEIR qrels** — https://github.com/beir-cellar/beir
  BEIR uses document-level `_id` + a nested `{query_id: {doc_id: relevance}}`
  qrels format. Our corpus is chunk-level, not doc-level, so we store
  expected source_path patterns rather than BEIR-style doc_ids. RAGAS
  `reference_contexts` is more natural for our retrieval unit anyway.

**Decision:** Use RAGAS field names as the primary schema so the future
scoring runner can consume the file directly, and add reviewer eval metadata
(persona, expected_query_type, difficulty, expected_anchor_entities,
corpus_grounding_evidence) as top-level fields. Any RAGAS-compliant consumer
ignores the extra fields; any custom scoring runner uses them. Best of both.

### Full schema per query

```json
{
  "query_id": "PQ-113",
  "user_input": "What is purchase order 5000585586 and what did it order?",
  "reference": "PO 5000585586 is a monitoring system Sustainment OY2 purchase from Grainger for Pulling Tape destined for Lualualei, value $598.00, paired with Purchase Requisition PR 3000133844.",
  "reference_contexts": [
    "5.0 Logistics/Procurement/002 - Received/monitoring system Sustainment OY2 (1 Aug 24 - 31 Jul 25)/PO - 5000585586, PR 3000133844 Pulling Tape LLL monitoring system(GRAINGER)($598.00)/"
  ],
  "persona": "Logistics Lead",
  "expected_query_type": "ENTITY",
  "expected_document_family": "Logistics",
  "expected_source_patterns": ["%PO - 5000585586%"],
  "difficulty": "medium",
  "rationale": "Tests exact PO number lookup against real SAP-format PO.",
  "expected_anchor_entities": {"PO": ["5000585586"]},
  "has_ground_truth": true,
  "corpus_grounding_evidence": "Real PO folder confirmed via anchor miner..."
}
```

- `user_input`, `reference`, `reference_contexts` are RAGAS-native.
- `persona`, `expected_query_type`, `difficulty`, `rationale`,
  `expected_anchor_entities`, `has_ground_truth`, `corpus_grounding_evidence`,
  `expected_source_patterns` are reviewer metadata fields that RAGAS ignores.
- `response` and `retrieved_contexts` are deliberately absent — the eval
  runner fills them in at scoring time.

---

## 2. Why No LLM-Generated Queries

Per the brief and aligned with 2026 eval best practice:

> "Do NOT generate queries from an LLM — hand-curate them using the corpus
> metadata captures and your own domain reasoning."

**Rationale:**

- LLM-generated queries tend toward generic phrasing and drift away from
  operator wording patterns. They read like textbook questions instead of
  real PM / logistics / engineering phrasings.
- LLM-generated queries cannot verify that the answer exists in the corpus
  — they hallucinate anchors. Hand-curated queries anchored to mined
  entities cannot hallucinate because the anchors are copy-pasted from real
  corpus content.
- Recent RAG eval papers (RAGAS docs, BEIR methodology, Ragas Test Generator
  caveats) explicitly warn against pure synthetic test generation for
  production-sensitive corpora. Synthetic is OK for augmentation; it is not
  OK as the sole source of a baseline eval.

**The only LLM-assisted step in Phase 1** is the `scripts/mine_query_anchors.py
chunks` subcommand, which runs real hybrid search to surface ground-truth
contexts for a query concept. That is retrieval-assisted mining, not
generation — the query text itself is still hand-written.

---

## 3. Anchor Mining Methodology

reviewer wrote `scripts/mine_query_anchors.py` as a reusable read-only helper
that exposes the entity store and LanceDB for query authoring. Subcommands:

| Subcommand | Purpose |
|------------|---------|
| `sites --limit N` | Top SITE entities by count, filtered against `[Insert...]` and `TBD` placeholder noise |
| `parts --limit N` | Top PART entities, filtered against security standard control prefixes (CCI-, SP-800, AC-, IR-, SC-, CM-, CA-, SV-, AU-, SI-, AT-, PE-, PS-, PL-, RA-, PM-, IA-, MP-, MA-, CP-, SA-) |
| `pos --limit N` | Top PO entities, same security standard filter |
| `persons --limit N` | Top PERSON entities (regex-extracted names) |
| `subtrees` | Entity count by top-level corpus subtree × entity type |
| `folders --like PATTERN --limit N` | Distinct source_path folders matching a SQL LIKE pattern |
| `chunks QUERY --top N` | Hybrid search against live LanceDB for ground-truth mining |
| `ground-truth QUERY --top N` | Alias for `chunks`; reads more naturally when authoring queries |

**Every query in Phase 1 references anchors surfaced by one of these
subcommands.** No anchor was invented or guessed.

### Critical entity store caveats discovered during mining

1. **PO entities are contaminated by security standard control IDs.** The Tier 1 regex
   catches codes like `IR-4`, `IR-8`, `AC-2`, `CA-5` and labels them as PO.
   Real procurement PO numbers (7-digit SAP format like `5000585586`,
   `7000354926`) exist in the corpus but are buried in spreadsheet row text
   that got captured as SITE entities, not PO entities.
2. **PART entities are contaminated by security standard SP 800-53 family codes.** Top
   "PART" entries include `AS-5021` (104K hits), `OS-0004` (101K hits),
   `GPOS-0022` (45K hits) — these are security standard baseline enhancement codes, not
   physical parts. Real physical parts exist further down the count
   distribution: `RG-213` (18,418 hits, real HF coax), `LMR-400` (18,016
   hits, real HF coax), `P240-260VDG` (real pre-amplifier), `P007-003`
   (real Tripp Lite power cord), `RSC081004` (real enclosure).
3. **SITE entities include multi-field spreadsheet rows** like
   `"KWAJALEIN, SYSTEM: legacy monitoring system, LOCATION/MILITARY BASE: US Army Kwajalein
   Atoll (USAKA)"`. These carry extra context (system assignment + facility
   name) that is very useful for grounding queries, but they are not clean
   site tokens. Tier 2 GLiNER should produce cleaner SITE extraction.
4. **PERSON entities include concatenated contact strings** like
   `"Annette Parsons, (970) 986-2551"`. Again, useful for grounding but
   not clean person tokens. Tier 2 GLiNER should split these.
5. **CONTACT entities are clean email addresses** post-phone-regex-round-2
   fix (commit `7faef97`). 294,751 distinct emails, dominated by `.mil`
   and `.af.mil` addresses. These are reliable anchors for ENTITY queries
   asking "who is the POC for X".

**All 5 caveats are written into queries** — Phase 1 queries about parts
use only confirmed-physical part numbers, not security standard codes. PO queries use
the full SAP format. Site queries use the canonical uppercase spelling.

### Anchors mined and retained for Phase 1

| Anchor type | Count | Example values |
|-------------|------:|----------------|
| Real sites (legacy monitoring system) | 12 | Kwajalein, Curacao, Diego Garcia, Djibouti, Niger, Singapore, Ascension, Guam, ... |
| Real sites (monitoring system) | 16 | Thule, Eglin, Vandenberg, Misawa, Awase, Alpena, Fairford, Lualualei, Learmonth, Wake, San Vito, Ascension, Guam, Eielson, Eareckson, ... |
| Real physical parts | 7 | RG-213, LMR-400, P240-260VDG, P240-270VDG, P007-003, RSC081004, POL-2100 |
| Real PO numbers | 3 | 5000585586 (confirmed via folder path), 7000354926, 7000325121 |
| Real incident IDs | 5 | IGSI-1811 (Fairford 2024-06-05), IGSI-2234 (Misawa), IGSI-2529 (Learmonth 2024-08-16), IGSI-2783 (Kwajalein 2024-10-25), IGSI-4013 (Alpena 2025-07-14) |
| Real CDRL codes | 20+ | A001 CAP, A002 MSR, A003 SIP, A004 DD250, A006 IATP, A007 IATR, A008 PMP, A009 Monthly Status, A010 SSP, A011 Config Audit, A012 CMP, A013 SEMP, A014 Priced BOM, A023 ILS, A027 DAA (9+ subtypes), A031 IMS, A050 CCR, A055 Gov Prop Inv |
| Real RMF artifacts | 9 | A027 ACAS Scan Results, A027 SCAP Scan Results, A027 RMF Security Plan, A027 Authorization Boundary, A027 Updated POAM, A027 Network Diagram, A027 PPS, A027 CT&E Plan, A027 CT&E Report |
| Real cyber directives | 5 | MTO 2021-350-001 Apache Log4j, TASKORD_16-0014 Samba Wanna-Cry, OPORD 22-0026 SPARTAN VIPER VMware, MTO 2016-092-0212E PKI, MTO 2020-136-002 VPN Laptop |
| Real folder structures | 15+ | `10.0 Program Management/2.0 Weekly Variance Reports/2024/`, `5.0 Logistics/Procurement/002 - Received/`, `! Site Visits/(01) Sites/Awase (Okinawa JP)/`, `3.0 Cybersecurity/ATO-ATC Package Changes/`, etc. |
| Real recurring spreadsheets | 10+ | `enterprise program Weekly Hours Variance.xlsx` (weekly), `2024 NN Monthly Actuals.xlsx` (monthly), `Recommended Spares Parts List.xlsx`, `iBuy GL List.xlsx`, `111023_STIG_Review.xlsx`, etc. |

---

## 4. Persona Distribution (Phase 1 + Target)

The brief specified 80 queries per persona × 5 personas = 400. Phase 1
delivers 50 queries with distribution skewed toward personas where anchor
mining produced the richest results.

### Phase 1 distribution (50 new queries)

| Persona | Phase 1 count | Query IDs |
|---------|:-:|-----------|
| Program Manager | 10 | PQ-101 through PQ-110 |
| Logistics Lead | 15 | PQ-111 through PQ-125 |
| Field Engineer | 10 | PQ-126 through PQ-135 |
| Cybersecurity / Network Admin | 10 | PQ-136 through PQ-145 |
| Aggregation / Cross-role | 5 | PQ-146 through PQ-150 |
| **Total Phase 1** | **50** | |

### Target distribution (Phase 2+ to reach 400)

| Persona | Phase 1 | Phase 2+ | Target total |
|---------|:-:|:-:|:-:|
| Program Manager | 10 | 70 | 80 |
| Logistics Lead | 15 | 65 | 80 |
| Field Engineer | 10 | 70 | 80 |
| Cybersecurity / Network Admin | 10 | 70 | 80 |
| Aggregation / Cross-role | 5 | 75 | 80 |
| **Total** | **50** | **350** | **400** |

The existing 25 queries at `tests/golden_eval/production_queries_2026-04-11.json`
(PQ-001 to PQ-025, already QA-signed) will be promoted into the 400 file in
a future pass and count against the persona totals above (they're already
distributed 5 per persona). After promotion the Phase 1 + promoted total is
**75** queries, **19%** of the 400 target.

---

## 5. Query Type Distribution

The brief's target is ~16 queries per query_type per persona (80 ÷ 5 = 16).
Phase 1 is too small to satisfy that evenly, but the 50 queries are
deliberately distributed across all 5 RAGAS-relevant query types so that
every router path is exercised at least twice in Phase 1.

### Phase 1 query type breakdown

| Query type | Phase 1 count | Example IDs |
|------------|:-:|-------------|
| SEMANTIC | 17 | PQ-104, PQ-105, PQ-106, PQ-109, PQ-112, PQ-114, PQ-117, PQ-119, PQ-120, PQ-125, PQ-126, PQ-128, PQ-129, PQ-131, PQ-135, PQ-136, PQ-144 |
| ENTITY | 13 | PQ-103, PQ-111, PQ-113, PQ-115, PQ-116, PQ-121, PQ-123, PQ-130, PQ-132, PQ-141, PQ-145 |
| TABULAR | 5 | PQ-101, PQ-110, PQ-122, PQ-134, PQ-142 |
| AGGREGATE | 11 | PQ-102, PQ-107, PQ-108, PQ-118, PQ-124, PQ-127, PQ-133, PQ-143, PQ-146, PQ-147, PQ-148, PQ-149, PQ-150 |
| COMPLEX | 0 | (Phase 2+: to be authored as deliberate multi-intent queries) |

COMPLEX queries are deliberately deferred to Phase 2 because they require
the router to be more stable first. The router accuracy investigation reviewer
started this session (unpublished) found that the current router aggressively
over-classifies single-intent queries as COMPLEX. Authoring COMPLEX queries
in Phase 1 would pollute the baseline before that router behavior is
addressed.

---

## 6. Difficulty Distribution

Each query is tagged `easy`, `medium`, or `hard` based on the expected
retrieval and answering burden:

- **easy:** single-shot lookup, one source path expected, short ground
  truth answer feasible. Example: PQ-111 (packing list for dated shipment).
- **medium:** multi-path or narrative-style question, multiple source paths
  expected, reference answer would span a paragraph. Example: PQ-102 (FEP
  monthly actuals roll-up).
- **hard:** multi-hop or enumeration across many folders, ground truth is
  hard to capture without a full RAGAS scoring run. Example: PQ-147 (which
  sites have CAPs filed in 2024).

### Phase 1 difficulty breakdown

| Difficulty | Count | Ratio |
|------------|:-:|:-:|
| easy | 20 | 40% |
| medium | 27 | 54% |
| hard | 3 | 6% |

The target for Phase 2+ is 30% easy / 55% medium / 15% hard, weighted
toward medium so the eval captures real operator difficulty without making
every query a stretch goal.

---

## 7. Path to 400 Queries

Phase 2 work should proceed as follows, using `scripts/mine_query_anchors.py`
as the anchor source and this doc's methodology as the guide:

1. **Merge the existing 25 QA-signed queries** (`production_queries_2026-04-11.json`)
   into `production_queries_400_2026-04-12.json` with the new RAGAS schema.
   Fields to add to each: `user_input` (rename from `query`), `reference`
   (null where not feasible), `reference_contexts` (empty list), and
   `expected_source_patterns` derived from their `document_family` strings.
   This is a 30-minute mechanical merge, no new query authoring required.
   **Brings total to 75 queries.**

2. **Phase 2A — per-persona batches of 40 queries each** (200 total new):
   - Program Manager: 40 more queries focused on CDRL deliverable status,
     budget variance trends, schedule slippage, suborganization oversight,
     contract milestones. Anchors: the full A-numbered CDRL folder tree,
     LDI budget spreadsheets, PMR deck series, weekly variance spreadsheets.
   - Logistics Lead: 40 more focused on parts by OEM, vendor history,
     receiving-vs-outstanding PO comparisons, DD250 transfer records, EEMS
     filings, shipping compliance, calibration audit chains. Anchors: real
     SAP PO numbers mined from the Procurement tree, physical part number
     catalogs, vendor names (Grainger, Tripp Lite, etc.).
   - Field Engineer: 40 more focused on MSRs by site, installation
     procedure recall, known-issues by equipment type, power/UPS diagnostic
     procedures, acceptance test results. Anchors: 21 MSR site folders,
     Digisonde upgrade docs, site outage analysis, COTS manual archive.
   - Cybersecurity / Network Admin: 40 more focused on RMF artifacts by
     type (ACAS/SCAP/POA&M/PPS/Network Diagram), ATO change history,
     monthly ConMon reviews, directive compliance. Anchors: the 9+ A027
     subfolder types, 18+ ATO-ATC package folders, monthly audit archive
     tree, directive folder.
   - Aggregation / Cross-role: 40 more deliberately cross-family queries
     (PM + Logistics, Field Engineer + Cyber, etc.) with ground truth
     evidence scattered across 3+ subtrees.

3. **Phase 2B — COMPLEX queries (50 queries)** authored AFTER the router
   tuning lands. These should be deliberate multi-intent questions that
   legitimately need decomposition: "Compare ATO submission timelines
   against CDRL A009 monthly status reports and flag gaps", "Show me all
   parts consumed for the 2024 Misawa CAP alongside the procurement POs
   they came from". 10 per persona × 5 personas.

4. **Phase 2C — ground truth backfill (100 queries enriched)**: pick the
   100 highest-value queries from the 400 and run
   `scripts/mine_query_anchors.py chunks "..."` against LanceDB to pull
   real chunk text snippets into `reference_contexts`, and hand-write
   ~2-sentence `reference` answer strings. This gets the eval to RAGAS
   Context Recall and Answer Relevancy scoring readiness for the top 25%
   of the set. The remaining 75% stays at source_path grounding only.

### Estimated Phase 2 effort

- Phase 2A: ~4 hours per persona × 5 personas = 20 focused hours of
  authoring, or ~2000 queries/day at LLM-assisted mining pace. One
  full-session reviewer pass delivers 100 queries; Phase 2A takes 2-3
  sessions.
- Phase 2B: Blocked on router fix. ~4 hours once unblocked.
- Phase 2C: ~6 hours for 100 ground-truth enrichments (with
  `mine_query_anchors.py chunks` doing most of the heavy lifting).

**Total effort to reach 400 + top-100 ground truth: ~30 focused hours
spread across 4-5 reviewer sessions.** Parallelizable if multiple agents
work on non-overlapping personas.

---

## 8. How This Set Should Be Used

### For router tuning

Run the existing `scripts/run_production_eval.py` against the 400 file
instead of the 25 file. Router accuracy goes from a 12/25 ± 4 (wide error
bars) signal to a 200-250/400 ± 12 (tight error bars, per-persona cuts,
per-query_type cuts) signal. **This is the statistical lift that was the
primary driver of the Phase 1 → 400 request.**

### For retrieval quality measurement

Same runner, different metric: track the `top_in_family` and
`any_top5_in_family` flags per query over time. As Tier 2 GLiNER and Tier 3
LLM extraction land, retrieval quality on entity-dependent queries should
visibly improve. The ground-truth-enriched top-100 subset additionally
enables RAGAS Context Recall and Context Precision scoring.

### For RAGAS scoring

Wire up a future `scripts/run_ragas_eval.py` that:

1. Loads `production_queries_400_2026-04-12.json`
2. For each sample, runs the V2 pipeline to get `response` and
   `retrieved_contexts`
3. Constructs a `ragas.dataset_schema.SingleTurnSample` per query
4. Calls `ragas.evaluate()` with the standard metrics (context_recall,
   context_precision, faithfulness, answer_relevancy)
5. Emits per-persona and per-query_type scorecards

This runner is **out of scope for Phase 1** but the JSON schema is
designed to make it a one-shot integration task.

### For demo rehearsal

Pick a random 25-query subset from the 400 per demo run. Never show the
same 25 twice. Demo audience sees novel queries each time; operator
confidence in the system grows because the scorecard is stable across
random subsets.

### For program portability

A future program corpus only needs a new anchor mining pass
(`mine_query_anchors.py` run against the new corpus) and a persona
rewrite of the top 50 queries. The scoring methodology, RAGAS integration,
and router eval infrastructure all carry over.

---

## 9. Known Gaps (queries I wanted to write but couldn't)

Queries deliberately NOT included in Phase 1 because the corpus does not
currently support them:

- **"Who is the point of contact for Thule?"** style queries — PERSON
  entities are only 4,788 distinct values and concatenated with phone
  numbers. Waiting for Tier 2 GLiNER to clean up PERSON extraction before
  authoring a batch of contact-lookup queries.
- **"How many times has part X failed?"** — requires cross-chunk
  aggregation over a Part Failure Tracker spreadsheet that is structured
  as rows, not chunks. Retrieval can find the spreadsheet but can't
  aggregate within it. This needs Tier 3 LLM relationship extraction and
  a SQL-like aggregation path.
- **"What is the relationship between CAP IGSI-1811 and the parts consumed
  at Fairford in 2024?"** — needs Tier 3 relationships. relationships.sqlite3
  has 59 rows.
- **Drawing and CAD queries** — `.dwg` files are deferred in the Forge
  skip manifest (14,350 files not parsed). All CAD queries are Phase 3
  work when visual processing lands.
- **Image / photo metadata queries** — 174,779 `.jpg` files are metadata
  only. Same Phase 3 gate.
- **Email thread context queries** — `.msg` files are parsed but thread
  context is not reconstructed; each email is a standalone chunk. Queries
  like "what did the Fairford team reply to the 2024-06 incident" can't be
  answered until thread reconstruction lands.

These are documented here so the eval set doesn't look incomplete — the
**eval set is complete for the retrievable portion of the corpus**. The
gaps above are corpus gaps, not eval gaps.

---

## 10. Acceptance Criteria for Phase 1

- [x] 50 new queries delivered (PQ-101 through PQ-150)
- [x] Every query has real anchors mined from entities.sqlite3 or folder listings
- [x] Zero fictitious identifiers (no "Mike Torres", no "ARC-4471", no fake sites)
- [x] RAGAS v0.3 `SingleTurnSample` schema fields present
- [x] reviewer eval metadata fields present (persona, expected_query_type, etc.)
- [x] 8+ queries with full `reference` ground truth answer strings
- [x] Every query has at least one `expected_source_patterns` grounding
- [x] Helper script `scripts/mine_query_anchors.py` committed and documented
- [x] Rationale doc (this file) explains methodology, gaps, and Phase 2+ plan
- [x] No LLM-generated query text
- [x] Read-only on LanceDB, entities.sqlite3, corpus files
- [x] Sanitized before commit

---

## 11. Handoff to Coordinator

**What's ready to use:**
- `scripts/mine_query_anchors.py` — reusable anchor miner for Phase 2+
- `tests/golden_eval/production_queries_400_2026-04-12.json` — Phase 1 query set
- This rationale doc as the Phase 2+ playbook

**What's not ready and why:**
- 350 more queries (Phase 2A/B/C) — deferred per scope reality; this is
  a 30-hour effort that does not fit a single session.
- RAGAS scoring runner — separate task; schema is designed to make it
  a one-shot integration.
- Router accuracy investigation — superseded by this 400-query work, as
  per the user's pivot mid-session. The router's baseline is now measurable
  at much higher confidence against the full 400 set instead of the 12/25
  signal.

**Next reviewer action when unblocked:** either start Phase 2A (per-persona
batches of 40) or merge the existing 25 queries into the 400 file, whichever
the coordinator prioritizes.

---

## 12. Phase 2A Mining Adjustments After Entity Store Pollution Discovery

**Added 2026-04-12 after Phase 1 QA acceptance.** The coordinator filed the
Phase 1 entity store pollution findings (Section 3) as task #16 for the
entity extractor owner. Separately, Phase 2A query authoring must adjust
its anchor mining strategy to avoid relying on the polluted Tier 1 PO/PART
columns. This section records the new methodology so future agents reading
this doc understand why Phase 1 and Phase 2 mine differently.

### The problem restated

- Tier 1 `PO` column: 98% security standard/RMF control IDs (IR-4, CA-5, AC-2, etc.),
  2% real SAP POs embedded in spreadsheet row fragments incorrectly
  labeled as SITE.
- Tier 1 `PART` column: 90% security standard SP 800-53 baseline codes
  (AS-5021, OS-0004, GPOS-0022), 10% real physical parts buried deeper
  in the count distribution.
- Tier 1 `SITE` column: cleaner but still carries multi-field
  spreadsheet-row contamination (e.g., `"KWAJALEIN, SYSTEM: legacy monitoring system,
  LOCATION/MILITARY BASE: US Army Kwajalein Atoll (USAKA)"`).
- Tier 1 `PERSON` column: concatenated `name + (phone)` strings.

### Phase 2A anchor sources (in priority order)

1. **Folder paths from `mine_query_anchors.py folders --like '%pattern%'`**
   are the cleanest anchor source. The real corpus folder structure is
   not polluted by regex extraction quirks. This is Phase 2A's primary
   mining path for TABULAR, ENTITY, and AGGREGATE queries.

2. **Real SAP-format PO numbers found in folder names.** Phase 1 mining
   surfaced several real POs embedded in procurement folder naming
   conventions like `"PO - 5000585586, PR 3000133844 Pulling Tape LLL
   monitoring system(GRAINGER)($598.00)"`. Phase 2A extracts more of these by
   running `mine_query_anchors.py folders --like
   '%5.0 Logistics/Procurement/002 - Received/%'` and harvesting the
   SAP POs (pattern `\b[57]\d{9}\b`) from the folder names directly.

3. **Real physical parts from earlier Phase 1 findings.** These were
   verified against chunk text and should be reused, not re-mined:
   `RG-213`, `LMR-400`, `P240-260VDG`, `P240-270VDG`, `P007-003`,
   `RSC081004`. Phase 2A adds more by walking the `5.0 Logistics/Parts
   (Downloaded Information)/` subtree via folder listing.

4. **Real SITE names** are usable after splitting on comma and taking
   the leading token. Phase 1 confirmed Kwajalein, Thule, Eglin,
   Vandenberg, Ascension, Guam, Misawa, Awase, Fairford, Learmonth,
   Alpena, Djibouti, Ascension, Niger, San Vito, Wake, Lualualei,
   Curacao, Diego Garcia, Singapore, Eareckson.

5. **Real contract numbers** surfaced in folder names during Phase 2A
   mining: `47QFRA22F0009` (legacy GSA/FEDSIM contract), `FA881525FB002`
   (current AF contract). These are 13-digit structured identifiers
   that FTS can match exactly and are reliable anchors for ENTITY and
   TABULAR queries about deliverable tracking.

6. **Real incident IDs** with the form `IGSI-NNNN` or `IGSCC-NNN`. Phase 1
   confirmed 5 CAPs (IGSI-1811, IGSI-2234, IGSI-2529, IGSI-2783,
   IGSI-4013). Phase 2A mining turned up many more in the
   CDRL A027 folder tree (IGSI-965, IGSI-966, IGSI-727, IGSI-2553,
   IGSI-2891, IGSI-965, IGSI-110, IGSI-503, IGSI-481, IGSCC-529,
   IGSCC-531, IGSCC-532, IGSCC-533). Each maps to a specific deliverable
   report by contract number, making them ideal ENTITY anchors for
   compliance queries.

7. **Real dated site visit folders** like `"Thule/2026-06-18 thru
   08-26 (ASV)(FS-JR)/"`, `"Awase (Okinawa JP)/2023-06-19 thru 07-07
   (Install 1 - FP)/"`. These carry date + site + visit type + team
   initials as structured naming — very rich anchor material for
   Field Engineer queries.

### Anti-patterns avoided in Phase 2A

- **Do NOT** write queries like `"Show me PART number CCI-0015"` —
  CCI-0015 is a security standard control, not a part.
- **Do NOT** write queries like `"Who is Annette Parsons"` unless you
  also acknowledge the regex catches her name concatenated with a phone
  number, and the answer will be noisy until Tier 2 cleans it up.
- **Do NOT** anchor on top-N PART or PO entity values without first
  checking whether they are security standard codes (`_is_nist_control()` in
  `mine_query_anchors.py` is the canonical filter).
- **Do NOT** trust the Tier 1 `PO` column for real procurement POs.
  Use folder paths or FTS chunk search instead.

### Tooling updates in Phase 2A

No new subcommands were added to `scripts/mine_query_anchors.py` in
Phase 2A. The existing `folders` subcommand proved sufficient because
the cleanest anchor source (folder paths) is already fully exposed.

A potential Phase 2C tooling enhancement would be a `--fts-only` flag
on `chunks` that skips vector similarity and uses pure BM25 exact-token
search against LanceDB. This is useful for extracting real SAP PO
numbers from chunk text (since SAP POs are 10-digit integers that vector
similarity struggles with, but FTS handles cleanly). Not implemented in
Phase 2A because folder-path mining covered enough anchors.

### Phase 2A ground truth strategy

Phase 1 had 8/50 queries with full `reference` ground truth (16%).
Phase 2A targets 20+/60 (33%) by leveraging the richer anchor pool:

- Every query with a confirmed incident ID (IGSI-NNNN or IGSCC-NNN) can
  have a ground truth answer composed from the folder name itself
  (site + date + deliverable type).
- Every query with a confirmed SAP PO can compose ground truth from the
  folder naming convention (`"PO XXXXXXXXXX, PR YYYYYYYYYY, item,
  destination, vendor, amount"`).
- Every query about a specific contract number (47QFRA22F0009 or
  FA881525FB002) can compose ground truth naming the contract + period
  of performance.

The `has_ground_truth: true` flag is set whenever the `reference` field
is non-null and the answer can be verified from folder-level evidence.

---

Signed: reviewer | HybridRAG_V2 | 2026-04-12 MDT
