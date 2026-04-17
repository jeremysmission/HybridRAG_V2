# How HybridRAG V2 Works — Non-Technical Guide

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT

---

## The Big Picture

You have thousands of documents — PDFs, Word files, spreadsheets, emails. You want to ask questions and get answers with source citations. That's what this system does.

There are **two programs** that work together:

1. **CorpusForge** — Reads your documents and prepares them for searching
2. **HybridRAG V2** — Searches the prepared data and answers your questions

They run in order. CorpusForge goes first. V2 goes second.

---

## Step by Step: What Happens to Your Documents

### Step 1: CorpusForge reads your files

You point CorpusForge at a folder of documents. It reads every file it can — PDFs, Word docs, Excel sheets, emails, PowerPoints, HTML pages, and more. Files it can't read (like CAD drawings) get logged as "deferred" so nothing is lost or forgotten.

### Step 2: CorpusForge cuts documents into pieces

A single PDF might be 50 pages. That's too much to search at once. CorpusForge splits each document into small pieces called "chunks" — about 1 paragraph each. This is like cutting a book into index cards.

### Step 3: CorpusForge creates search fingerprints

Each chunk gets converted into a set of numbers called a "vector" — think of it as a fingerprint that captures the meaning of the text. Two chunks about the same topic will have similar fingerprints, even if they use different words. This is done by an AI model running on your GPU (the graphics card). This is the fastest step because the GPU processes hundreds of chunks per second.

### Step 4: CorpusForge saves a package

All the chunks and their fingerprints get saved as a package — two files that V2 can read.

**CorpusForge is now done. It does not run again unless you add new documents.**

---

### Step 5: V2 imports the package

V2 reads the package from CorpusForge and loads it into its search database (LanceDB). Now V2 can search the chunks by meaning (vector search) and by keywords (text search).

### Step 6: V2 extracts knowledge from chunks

This is where V2 reads through the chunks and pulls out structured information:
- **People** — names, roles, contact info
- **Parts** — part numbers, serial numbers
- **Sites** — locations, bases, facilities
- **Dates** — deadlines, schedules
- **Purchase orders** — PO numbers
- **Organizations** — teams, units, companies
- **Relationships** — who works where, what part is at what site, who ordered what

This is done by an AI model (phi4 or GPT-4o) that reads each chunk and returns structured data. This is the slowest step because the AI reads each chunk carefully.

The extracted knowledge goes into a separate database (SQLite). This gives V2 the ability to answer questions like "who is the POC at Thule?" or "what parts have failed at Riverside?" without searching through raw text.

**Extraction is a one-time process. Once done, the knowledge is stored permanently.**

---

### Step 7: You ask a question

You type a question into the V2 GUI or send it to the API. V2 does several things:

1. **Routes** your question — figures out what type of question it is (searching for text, looking up an entity, counting things, comparing data)
2. **Retrieves** relevant chunks — searches LanceDB by meaning and keywords, returns the best matches
3. **Retrieves** relevant entities — if your question is about a person, part, or site, looks them up directly in the entity database
4. **Builds context** — assembles the retrieved chunks and entities into a package for the AI
5. **Generates** an answer — sends the context to GPT-4o, which writes an answer with citations
6. **Verifies** the answer (optional) — a second AI check grades the answer for accuracy and may retry if it's not good enough

You get an answer with confidence level (HIGH/PARTIAL/NOT FOUND) and source citations pointing back to the original documents.

---

## The Order Things Happen

```
YOUR DOCUMENTS
     |
     v
[CorpusForge]  ------>  Package (chunks + fingerprints)
                              |
                              v
                        [V2 Import]  ------>  Search Database (LanceDB)
                              |
                              v
                        [V2 Extract]  ----->  Knowledge Database (SQLite)
                              |                    entities, relationships
                              v
                        [V2 Ready for Questions]
                              |
                              v
                         YOU ASK  ------>  ANSWER + CITATIONS
```

---

## What Runs Where

| Program | What it does | When it runs | How long |
|---------|-------------|-------------|----------|
| CorpusForge | Reads files, makes chunks + fingerprints | Once, when you add documents | Hours (depends on file count) |
| V2 Import | Loads CorpusForge output into search database | Once, after CorpusForge finishes | Minutes |
| V2 Extract | Pulls people/parts/sites/dates from chunks | Once, after import | Hours (runs overnight) |
| V2 Query | Answers your questions | Every time you ask | 2-5 seconds per question |

---

## Two Machines

- **primary workstation** (your home computer) — Development and testing. Proves the system works. Has two GPUs.
- **Work desktop** — Production. Processes the real 700GB of documents. Runs 24/7. Has better GPUs.

You build and test on primary workstation. When it works, you deploy to work and process the real data.

---

## Cost

- CorpusForge: **$0** — runs locally on your GPU
- V2 Import: **$0** — just copying data
- V2 Extract: **$0-50** — phi4 local is free, or GPT-4.1 Nano API for speed (~$10-30)
- V2 Queries: **pennies per question** — GPT-4o at demo time

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
