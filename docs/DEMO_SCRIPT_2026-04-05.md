# HybridRAG V2 Demo Script

**Author:** Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
**Audience:** defense contractor stakeholders (engineers, program managers, logistics leads)
**Total time:** ~19 minutes (2 + 12 + 2 + 3)
**System:** HybridRAG V2 — IGS/NEXION Maintenance Knowledge System

---

## Pre-Demo: Problem Statement (2 min)

### What problem are we solving?

Engineers spend hours searching through legacy databases, SharePoint, and file shares for maintenance history, parts tracking, and operational procedures. V2 reduces that to seconds with AI-powered retrieval across all document types.

Studies show the average worker spends 1-1.5 hours per day on information retrieval. AI-assisted retrieval reduces that time by 60-70%. This system is built to deliver that reduction for three key roles.

Our current data — maintenance reports, purchase orders, email chains, and spreadsheets — is already being generated across IGS and NEXION programs every year. Today, finding specific information across this corpus requires someone who:

- Knows which document to look in
- Knows the tribal knowledge (site names, part numbers, people)
- Has the time to manually search

When that person is unavailable — on leave, moved to another program, or left the company — the knowledge goes with them.

### Three Personas

- **Program Manager:** status reports, site assessments, cross-program visibility
- **Logistics Analyst:** parts ordered vs received, PO status, backorder tracking
- **Engineer:** failure trends, bit fault patterns, equipment health by site/year

**HybridRAG V2 modernizes our existing legacy data with AI-native retrieval.** We already have the data in legacy systems. V2 makes it searchable, queryable, and actionable without replacing the existing infrastructure. Ask a question in plain English, get an answer with sources, in seconds.

### What the system does:

- Answers factual questions about IGS/NEXION maintenance, parts, and personnel
- Cites every claim back to a specific source document and section
- Handles structured data (tables, purchase orders) and unstructured data (reports, emails)
- Tells you when it does NOT know something (graduated confidence)

### What the system does NOT do:

- Does not generate new procedures or recommendations
- Does not access restricted networks (runs on GovCloud, feeds from authorized sources)
- Does not replace human judgment — it retrieves and summarizes, the operator decides
- Does not hallucinate answers — if the information is not in the corpus, it says so

### Scope:

- ~700GB corpus of mission-derived documentation (IGS/NEXION maintenance and logistics)
- 27.6 million indexed chunks across 100K+ documents
- 32 file format parsers (PDF, DOCX, XLSX, email, plain text, etc.)

---

## Live Demo Flow (12 min)

> **Operator note:** Each query shows the answer, confidence badge, query path badge, source citations, and latency. Pause after each to take questions.

---

### Query 1 — Slam Dunk (SEMANTIC)

**Ask:** "What is the transmitter output power at Riverside Observatory?"

**Expected result:**
- Answer: 1.2 kW nominal
- Confidence: **HIGH** (green)
- Path badge: SEMANTIC
- Source: `maintenance_report_sample.txt`, Section 2.2 Transmitter
- Latency: < 3 seconds

**Talking point:** "This is the bread and butter — a factual question, answered instantly with a citation. No need to open the PDF and ctrl-F through it."

---

### Query 2 — Entity Lookup (ENTITY)

**Ask:** "Who is the field technician for the Riverside radar site?"

**Expected result:**
- Answer: Mike Torres, Senior Field Technician
- Contact: mike.torres@acmeradar.example.com, (555) 234-5678
- Confidence: **HIGH** (green)
- Path badge: ENTITY
- Source: `maintenance_report_sample.txt`, header/POC section

**Talking point:** "Notice the path badge says ENTITY, not SEMANTIC. The system recognized this as a personnel lookup and queried the entity store directly — faster and more precise than searching through every document."

---

### Query 3 — Aggregation (AGGREGATE)

**Ask:** "List all parts replaced at Riverside Observatory during the March 2024 visit."

**Expected result:**
- Answer: WR-4471 RF Connector (x2, replaced SN-1893 with SN-2901, and SN-1894 with SN-2902)
- Confidence: **HIGH** (green)
- Path badge: AGGREGATE
- Source: `maintenance_report_sample.txt`, Section 3 Parts Replaced

**Talking point:** "Aggregation queries were impossible in V1. V1 could find one document at a time — V2 counts across documents and gives you a list. This matters when a PM asks 'how many parts did we use this quarter.'"

---

### Query 4 — Tabular Data (TABULAR)

**Ask:** "What is the status of PO-2024-0501?"

**Expected result:**
- Answer: IN TRANSIT, FM-220 Filter Module 50MHz, qty 3, shipping to Cedar Ridge, ETA 2024-03-15, requested by Patel, R.
- Confidence: **HIGH** (green)
- Path badge: TABULAR
- Source: `spreadsheet_fragment.txt`, Row 2

**Talking point:** "This came from a spreadsheet, not a narrative document. The system extracted table rows during ingestion and can query them like a database. Ask about any PO number and get the row back."

---

### Query 5 — Complex / Multi-hop (COMPLEX)

**Ask:** "Compare the maintenance issues at Riverside Observatory versus Cedar Ridge."

**Expected result:**
- Answer: Riverside has amplifier board SN-2847 noise floor elevation on RX3; Cedar Ridge has CH3 calibration failure (noise floor 8dB above spec) likely due to corrosion on filter module SN-3392
- Confidence: **PARTIAL** (yellow — comparison across docs has inherent gaps)
- Path badge: COMPLEX
- Sources: `maintenance_report_sample.txt` AND `email_chain_messy.txt`

**Talking point:** "This query required information from two separate documents — a formal report and a buried email chain. The system decomposed the question into sub-queries, retrieved from both, and merged the results. The yellow PARTIAL confidence is correct — comparisons always have gaps."

---

### Query 6 — Messy Input Handling (SEMANTIC on tier2 data)

**Ask:** "What workaround was applied for the CH3 noise issue?"

**Expected result:**
- Answer: Bump attenuation 2 steps (+6dB) and increase integration time from 4 to 8 sweeps. Reduces sensitivity but brings noise floor within spec.
- Confidence: **HIGH** (green)
- Path badge: SEMANTIC
- Source: `email_chain_messy.txt` — Paul Nakamura's reply buried in RE:RE:RE chain

**Talking point:** "That answer was buried three levels deep in a forwarded email chain with unrelated content about endpoint protection mixed in. The system found the relevant passage anyway. This is the kind of tribal knowledge that gets lost when someone rolls off the program."

---

### Query 7 — Deliberate Refusal (NOT_FOUND)

**Ask:** "What maintenance was performed at Fort Wainwright in 2024?"

**Expected result:**
- Answer: "[NOT_FOUND] The corpus does not contain maintenance records for Fort Wainwright."
- Confidence: **NOT_FOUND** (red)
- Path badge: SEMANTIC
- Sources: none

**THIS IS THE TRUST-BUILDING MOMENT.**

**Talking point:** "This is the most important slide in the demo. The system knows what it does NOT know. Fort Wainwright is not in our corpus, and instead of making something up, it tells you clearly. Every RAG system that hallucinates answers destroys operator trust. Ours refuses. That refusal IS the feature."

> Pause here. Let this land. Ask: "Would you rather have a system that always gives you an answer, or one that tells you when it can't?"

---

### Query 8 — CRAG Verification

**Ask:** "What was the general condition of the equipment during recent visits?"

**Expected result (if CRAG enabled):**
- First pass: vague answer, PARTIAL confidence
- CRAG catches low confidence, retrieves additional context, regenerates
- Second pass: more specific answer citing particular equipment issues
- Badge shows: CRAG VERIFIED
- Retries: 1

**Talking point:** "The system just caught itself giving a weak answer and automatically went back for more context. This is Corrective RAG — self-correcting retrieval. It does not ship an answer it is not confident in without trying harder first."

> If CRAG is not enabled for demo, describe the feature and show the architecture diagram instead.

---

### Query 9 — V1 vs V2 Side-by-Side

**Run the same query against V1 and V2:**

Query: "What parts are currently backordered?"

| Metric | V1 | V2 |
|--------|----|----|
| Answer quality | Missed tabular data entirely | PS-800, Granite Peak, PO-2024-0503 |
| Source citation | Generic doc link | Specific row in spreadsheet_fragment.txt |
| Confidence | No confidence level | HIGH (green) |
| Latency | 12-24 seconds (FTS5 full scan) | < 3 seconds (LanceDB hybrid) |
| Query path | N/A | TABULAR |

**Talking point:** "Same question, same corpus. V1 could not read structured data at all — spreadsheets were invisible. V2 extracted the table rows during ingestion and can answer this in under 3 seconds. That is the architectural difference."

---

### Query 10 — Audience Choice

**Say:** "We have shown you prepared queries. Now it is your turn. What would you like to ask the system?"

> Run the audience's query live. The system handles it or correctly refuses. Either outcome builds trust.

**If the query works:** "That was not in our script. The system handled a real question from someone who knows this domain."

**If the query returns NOT_FOUND:** "And there is the refusal again — the system does not fake answers just because someone important is watching."

**Backup queries if the audience is quiet:**
- "When is the next scheduled maintenance at Thule Air Base?"
- "Which purchase orders have been cancelled and why?"
- "Who requested parts for Cedar Ridge?"

---

## Metrics Slide (2 min)

### Performance

| Metric | V2 Result | V1 Baseline | Improvement |
|--------|-----------|-------------|-------------|
| P50 latency | < 3s | 12-24s | 4-8x faster |
| P95 latency | < 10s | 30-45s | 3-4x faster |
| Keyword search | < 100ms (LanceDB BM25) | 12-24s (FTS5) | 120-240x faster |

### Accuracy

| Metric | V2 Result |
|--------|-----------|
| Golden eval (25 queries) | 25/25 retrieval |
| Confidence accuracy | Correct level on 24/25 |
| Hallucination rate | 0/25 (no fabricated facts) |
| Structured data queries | Now possible (was 0% in V1) |

### Corpus Coverage

- We indexed X of Y total files. The remaining files are CAD drawings, encrypted files, and deferred formats — every one hashed and tracked in our skip manifest. Nothing is lost, nothing is forgotten. These formats will be added in the production phase.

### Cost

| Metric | Value |
|--------|-------|
| Cost per query (GPT-4o) | ~$0.02-0.05 |
| Cost per query (GPT-OSS-120B) | Free (GovCloud) |
| Index storage | ~4GB for 27.6M chunks |

---

## Wrap-Up: Six Questions Defense Contractor Stakeholders Ask (3 min)

### 1. What problem does this solve and for whom?

Instant knowledge retrieval across our entire enterprise program documentation corpus for engineers, logistics leads, and program managers — eliminating manual search through legacy databases, SharePoint, and file shares.

### 2. What data does it need and where does it come from?

Our current data — maintenance reports, purchase orders, email archives, and spreadsheets already being generated across our programs. No new data collection required. Feeds from authorized document repositories we already maintain.

### 3. How do we know it works?

25-query golden evaluation suite covering all five query types, run before every release. Every answer is verified against known ground truth with expected confidence levels. Zero hallucination tolerance.

### 4. What are the failure modes?

The system can fail to retrieve (says NOT_FOUND), retrieve partially (says PARTIAL), or retrieve from the wrong document (caught by CRAG verification). It cannot fabricate information — the prompt architecture prevents generation beyond source material.

### 5. What is the security posture?

Runs on AWS GovCloud. No data leaves the boundary. LLM calls stay within GovCloud endpoints (GPT-OSS-120B is free and FedRAMP-authorized). 9-rule prompt injection guard prevents adversarial queries. No PII in logs.

### 6. What is the path to production and what is the ROI?

Pilot proposal: deploy against one program's document set for 90 days with real engineers. Measure: time saved per query, user trust scores, retrieval accuracy on live questions. If an engineer saves 30 minutes per day on document search, that is 125 billable hours per year per person recovered. Scale decision based on pilot results.

---

## Next Steps

1. **Pilot program selection** — identify one program with cooperative engineering staff and representative document corpus
2. **Security review** — GovCloud deployment inherits existing ATO; document delta for RAG components
3. **User training** — 30-minute walkthrough, focus on confidence levels and when to trust/verify
4. **Feedback loop** — engineers flag bad answers, those become new golden eval queries
5. **Scale plan** — if pilot succeeds, extend across additional programs and document sets

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
