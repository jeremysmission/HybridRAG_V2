# HybridRAG V2 — Operator Guide

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Audience:** End users who will be querying the system (not developers)

---

## 1. What This System Does

HybridRAG V2 is a search and question-answering tool for maintenance reports, operations documents, and technical records. You type a question in plain English, and the system finds relevant information across thousands of indexed documents, then gives you an answer with citations back to the original sources.

Think of it as a very smart search engine that reads the documents for you and summarizes what it finds — but it only knows about documents that have been indexed. It does not browse the internet or make things up.

Every answer includes:
- **A confidence level** telling you how much the system trusts its answer
- **Source citations** so you can verify the answer against the original document
- **A query path** showing which search strategy was used

---

## 2. Starting the System

The system has two parts that need to be running: the server (back end) and the GUI (front end).

### Option A: Command line

Open two terminal windows. In each one, activate the virtual environment first:

```
.venv\Scripts\activate
```

**Terminal 1 — Start the server:**

```
python -m src.api.server
```

Leave this running. You should see a message that the server started on port 8000.

**Terminal 2 — Start the GUI:**

```
python src/gui/launch_gui.py
```

The GUI window will open. The status bar at the bottom shows whether it successfully connected to the server.

### Option B: Start script

If a start script has been provided for your deployment, double-click it. It launches both the server and the GUI automatically.

---

## 3. Using the GUI

### 3.1 Query Tab

This is the main screen you will use.

1. **Type your question** in the text box at the top.
2. **Click "Ask"** (or press Enter).
3. **Read the answer** that appears below. The answer streams in word by word as the system generates it.
4. To stop a long answer mid-stream, click the **"Stop"** button.

### 3.2 Understanding Confidence Levels

Every answer starts with a colored confidence badge. This tells you how much you should trust the answer:

| Badge | Color | What It Means |
|-------|-------|--------------|
| **HIGH** | Green | The answer was found directly in the source documents. The system is confident. You can trust this answer, but always verify important decisions against the cited source. |
| **PARTIAL** | Yellow | Some information was found, but there are gaps. The answer tells you what it found and what is missing. Treat this as a starting point — you may need to search further or ask a more specific question. |
| **NOT_FOUND** | Red | The information is not in the indexed documents. The system did not find anything relevant. This does not mean the information does not exist — just that it is not in the current corpus. |

If you see **UNKNOWN** (no badge), the system could not determine confidence. Treat the answer with extra caution.

### 3.3 Understanding Query Path Badges

Below the confidence badge, you will see a colored label showing which search strategy the system used. Here is what each one means in plain terms:

| Badge | What It Means |
|-------|--------------|
| **SEMANTIC** | The system searched for documents that are conceptually related to your question. Best for "how does X work?" or "explain the procedure for Y" questions. |
| **ENTITY** | The system looked up a specific fact — a person's name, a site location, a part number. Best for "who is the POC for X?" or "what is the part number for Y?" questions. |
| **AGGREGATE** | The system counted or summarized across multiple documents. Best for "how many sites have X?" or "list all failures in 2025" questions. |
| **TABULAR** | The system searched structured data from spreadsheets and tables. Best for questions about data that was originally in rows and columns. |
| **COMPLEX** | The system used multiple search strategies together because the question required combining different types of information. |

You do not need to do anything differently based on the query path — it is informational only.

### 3.4 Source Citations

Every answer includes citations that trace back to the original document. Citations look like:

> [Source: IGS_Thule_Maintenance_Report_2025-Q3.pdf, Section 4.2]

To verify an answer:
1. Note the source filename and section from the citation.
2. Find that document in your organization's file share or document management system.
3. Navigate to the cited section to confirm the information.

Multiple sources may be cited if the answer draws from more than one document.

### 3.5 Entity Tab

The Entity tab lets you browse the structured data the system has extracted from documents:

- **Entity type summary** — shows counts of how many people, sites, part numbers, organizations, and other entities have been extracted.
- **Entity lookup** — select an entity type from the dropdown (e.g., PERSON, SITE, PART_NUMBER) and type a search term to find matching entries.
- **Relationship list** — shows connections between entities (e.g., "SSgt Webb is POC for Thule"). You can search by any name, site, or part number.

This is useful when you want to browse what the system knows rather than asking a specific question.

### 3.6 Settings Tab

The Settings tab shows the current system configuration. This is read-only — you cannot change settings from the GUI.

Key values shown:

| Setting | What It Means |
|---------|--------------|
| **top_k** | How many document chunks the system retrieves per query. Higher = more thorough but slower. Default is 10. |
| **min_score** | Minimum relevance score for a chunk to be included. Lower = more results but potentially less relevant. |
| **reranker_enabled** | Whether the system re-sorts results by relevance after the initial search. Should be "true" for best results. |
| **confidence_threshold** | Minimum confidence for an extracted entity to be stored. Default is 0.7 (70%). |

If you think settings need to be changed, contact the system administrator.

---

## 4. Using the API

If you prefer to query the system programmatically (or from scripts), you can use the REST API directly. The server runs at `http://127.0.0.1:8000`.

### Ask a question

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Who is the POC for Thule?\", \"top_k\": 10}"
```

The response includes the answer, confidence level, sources, query path, and timing information.

### Ask a question with streaming

```bash
curl -N -X POST http://127.0.0.1:8000/query/stream \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"What maintenance was performed at Eglin in Q3?\"}"
```

The answer streams back as Server-Sent Events (SSE). You will see metadata first, then tokens one at a time, then a done message with the final confidence level.

### Check system health

```bash
curl http://127.0.0.1:8000/health
```

Returns the system status, how many document chunks are loaded, how many entities are stored, and whether the LLM is available.

### View entity statistics

```bash
curl http://127.0.0.1:8000/entities/stats
```

Returns counts of entities by type (PERSON, SITE, PART_NUMBER, etc.) and relationship predicates.

### Full API documentation

Open `http://127.0.0.1:8000/docs` in a web browser for interactive Swagger documentation where you can test all endpoints.

---

## 5. Tips for Better Queries

**Be specific.** The more specific your question, the better the answer.

| Instead of... | Try... |
|--------------|--------|
| "Tell me about Thule" | "Who is the current POC for Thule?" |
| "What about maintenance?" | "What maintenance was performed at Eglin in Q3 2025?" |
| "Parts info" | "What is the status of part number ARC-1234?" |

**Use part numbers when you have them.** If you know a specific part number (ARC-1234, IGSI-5678, etc.), include it in your question. The system can look these up directly.

**If you get PARTIAL, try rephrasing.** A PARTIAL answer means some information was found but not everything. Try:
- Being more specific about what you need
- Breaking a complex question into two simpler questions
- Using different terminology (the system understands synonyms, but exact terms from the documents work best)

**If you get NOT_FOUND, the information may not be in the corpus.** This means the indexed documents do not contain the answer. Possible reasons:
- The document has not been indexed yet
- The information exists but uses different terminology
- The information genuinely does not exist in the document set

**For counting questions, be explicit.** Say "How many sites reported failures in 2025?" rather than "Were there failures?" The system handles aggregation queries differently and will give you a count with a list of sources.

---

## 6. What the System Cannot Do

- **It only searches indexed documents.** If a document has not been processed and imported, the system cannot find information from it.
- **It does not browse the internet.** All answers come from the local document corpus.
- **It does not update or modify documents.** It is read-only — it searches and answers, but never changes source files.
- **It can make mistakes.** While the confidence system helps, no automated system is perfect. Always verify critical decisions against the original source documents.
- **It does not learn from your questions.** Each query is independent. The system does not remember previous questions or adapt over time.
- **It cannot answer questions about events after the last data import.** The corpus is a snapshot in time. If you need information from recent documents, ask your administrator when the last import was run.

---

## 7. Getting Help

**If the system is not responding:**
- Check that the server terminal is still running (no error messages).
- Try the health check: `curl http://127.0.0.1:8000/health`
- Restart the server: close the server terminal, reopen it, activate the venv, and run `python -m src.api.server` again.

**If answers seem wrong or incomplete:**
- Check the confidence level — PARTIAL and NOT_FOUND answers are expected when information is limited.
- Try rephrasing your question (see Tips section above).
- Check whether the relevant documents have been imported.

**To report an issue:**
- Note the exact question you asked.
- Note the confidence level and answer you received.
- Note the time (for log correlation).
- Contact your system administrator with these details.

**To request new documents be indexed:**
- Contact your system administrator with the document locations. New documents need to be processed through the EmbedEngine pipeline and imported into V2 before they are searchable.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
