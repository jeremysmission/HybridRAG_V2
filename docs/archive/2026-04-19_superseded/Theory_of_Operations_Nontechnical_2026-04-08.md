# HybridRAG V2 — Theory of Operations (Non-Technical)

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-08 MDT
**Audience:** Program managers, operators, stakeholders, demo attendees
**Status:** Current

---

## What Is HybridRAG V2?

HybridRAG V2 is a document search and question-answering system built to help engineers, program managers, and operators find answers buried in hundreds of thousands of technical documents — maintenance reports, logistics spreadsheets, trip reports, configuration guides, and more.

Instead of manually searching through folders and files, operators type a question in plain English. The system finds the relevant information across the entire document library and returns a clear, sourced answer with confidence levels.

---

## How It Works (Plain Language)

### Step 1: Documents Get Prepared (Overnight, Automatic)

Every night, a separate application called CorpusForge processes new and updated documents:

- **Downloads** any new files that have arrived
- **Removes duplicates** — about half of all files are copies, automatically detected and skipped
- **Reads** documents in 60+ formats (PDFs, Word docs, Excel spreadsheets, emails, presentations, scanned images)
- **Breaks** each document into searchable passages (like cutting a book into paragraphs)
- **Labels** each passage with context ("This passage is from the 2024 Maintenance Report, Section 4, about equipment failures")
- **Identifies** key facts: part numbers, people, sites, dates, failure descriptions
- **Packages** everything into a format the search system can use

This happens automatically. Operators never touch it.

### Step 2: Operator Asks a Question (Daytime)

During the workday, an operator opens the application and types a question. Examples:

- "How many preamp replacements happened at a given site in 2024?"
- "Who is the point of contact for a specific location?"
- "What is the status of a particular purchase order?"
- "Explain the antenna calibration procedure"
- "Compare failure rates at two different sites"

### Step 3: The System Decides How to Answer

Not all questions are the same. The system classifies each question and chooses the best method:

| Question Type | Method | Example |
|---------------|--------|---------|
| **Conceptual** | Searches for relevant passages by meaning | "Explain the calibration procedure" |
| **Fact lookup** | Looks up the answer in a structured database | "Who is the POC for a specific site?" |
| **Counting/aggregation** | Runs a database count across all documents | "How many failures in 2024?" |
| **Spreadsheet data** | Queries extracted table data directly | "Status of a specific PO?" |
| **Complex** | Breaks the question into parts, answers each, combines | "Compare two sites" |

### Step 4: The Answer Comes Back

The system returns:

1. **The answer** — in plain language, streamed word-by-word so the operator sees progress immediately
2. **Confidence level** — GREEN (high confidence, directly from sources), YELLOW (partial information found), RED (information not in the documents)
3. **Sources** — exactly which documents and sections the answer came from, so the operator can verify
4. **Structured data** — if the answer involves numbers or tables, they are displayed as tables, not buried in prose

### What Makes V2 Different from V1?

V1 could only search for passages similar to the question. This works for "explain X" questions but fails for counting, lookups, and spreadsheet queries.

| Capability | V1 | V2 |
|------------|----|----|
| "Explain the procedure" | Works | Works (better, with enriched context) |
| "How many failures at a site?" | Fails — returns random passages | Works — counts across all documents |
| "Who is the POC?" | Fails — returns spreadsheet fragments | Works — returns the actual name |
| "Status of a PO?" | Fails — cannot find spreadsheet data | Works — queries extracted table data |
| "Compare site A vs site B" | Fails — cannot decompose the question | Works — breaks into sub-questions |

---

## What Operators See

The interface looks and feels like V1 — same color scheme, same button layout, same query input. Changes are additive:

- **Streaming text** — answers appear word-by-word instead of all-at-once after a long wait
- **Confidence badge** — green/yellow/red indicator so operators know how much to trust the answer
- **Query path label** — shows whether the system used passage search, database lookup, or both
- **Source panel** — expandable list of exactly which documents were used
- **Table display** — when the answer is structured data, it shows as a table

---

## What Operators Do NOT Need to Know

- How the overnight processing works (fully automatic)
- What "embeddings" or "vectors" are (internal implementation)
- How the system classifies questions (automatic routing)
- What cloud services are used (transparent to the operator)

---

## Reliability and Trust

### Confidence Levels

Every answer includes a confidence assessment:

- **HIGH (green):** The answer is directly stated in one or more source documents. The system quotes the relevant text and cites the exact source.
- **PARTIAL (yellow):** Some information was found but there are gaps. The system tells you what it found AND what is missing.
- **NOT FOUND (red):** The documents do not contain this information. The system says so clearly and does not guess.

### Source Attribution

Every factual claim in every answer cites a specific document and section. Operators can expand the source and read the original text. This is not a black box — every answer is traceable.

### What the System Will NOT Do

- It will not make up information. If the documents do not contain the answer, it says so.
- It will not combine real facts with guesses. Partial answers are clearly labeled.
- It will not access the internet or any system outside the approved document library.
- Queries are sent to approved API endpoints over HTTPS. Source document text included in the query context is not scrubbed for PII before transmission. A PII redaction layer is a planned future enhancement.

---

## Availability

- **Daytime queries:** Available whenever the operator workstation is on and has network connectivity to the approved API endpoints
- **Overnight processing:** Runs automatically on a dedicated machine, no operator intervention needed
- **Offline capability:** The search database is local. If the API endpoint is down, queries fail with an error message. The operator retries when connectivity returns. Query queueing is not yet implemented.

---

## Data Flow Summary (Non-Technical)

```
Source Documents        Overnight Processing        Daytime Use
(700GB, 420K files)     (automatic, nightly)        (operator-driven)
       |                        |                        |
       v                        v                        v
  New/updated files     Read, label, organize      Operator asks question
  arrive via network    every passage with         System finds answer
                        context and key facts      across ALL documents
                                |                        |
                                v                        v
                        Ready for next-day          Answer with sources
                        queries                     and confidence level
```

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
