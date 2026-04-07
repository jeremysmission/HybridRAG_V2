# Overnight Enriched Outputs Action Plan 2026-04-06

**Purpose:** Explain what can be done immediately with the current structured-store outputs and existing CorpusForge export packages while other work is still in flight.  
**Audience:** Operator and sprint lead  
**Scope:** Uses the current V2 structured store plus existing CorpusForge export packages. It does not depend on installer cleanup.

---

## What Is Already Available

The current audit shows the V2 structured store is usable now:

- `20,450` entities
- `4,683` relationships
- `3,397` table rows
- `12` chunks currently in the live LanceDB store

The newest deduped CorpusForge export package also exists and is ready to consume:

- `31,606` chunks
- `292` unique source files
- `0` non-empty `enriched_text` chunks in that sample export package
- source mix dominated by PDF, then JSON, then TXT

That means the immediate leverage is not more installer work. It is using what already exists:

- current structured store
- current export packages
- canonical rebuild preparation
- audit and comparison tooling

---

## What To Do First

### 1. Run the audit tool on the current state

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\structured_progress_audit.py
```

This reports:

- current V2 LanceDB count
- entity / relationship / table-row totals
- export package chunk counts
- whether non-empty `enriched_text` is present
- source coverage by extension and source directory

### 2. Review the newest export package

Use the audit output to decide whether the latest export package is worth importing or whether it should be treated as a dedup/canonical rebuild candidate.

If you want to inspect a specific export directly:

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\structured_progress_audit.py --export-dir C:\CorpusForge\data\output\sprint6_scale_subset_20260405_1810\export_20260405_1753_dedup
```

### 3. Use the structured store for immediate demo-safe work

The structured store is already populated enough to support:

- health checks
- demo gates
- golden-eval reruns
- targeted structured-query debugging

Recommended commands:

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\health_check.py
.\.venv\Scripts\python.exe scripts\demo_gate.py --config config\config.sprint8_demo.yaml --json-output results\demo_gate_latest.json
```

---

## What The Export Data Suggests

The export package is heavily weighted toward PDF content, with some JSON and TXT support files. The current sample export did not show non-empty enriched text, so the export should be treated as a dedup / rebuild input unless a different enriched package is found.

Practical implication:

- do not burn time assuming enrichment is already present in the export
- verify enrichment coverage with the audit tool first
- if a better enriched package exists, point the audit tool at that directory and compare the counts

---

## Recommended Parallel Work

Run these two tracks in parallel:

### Track A: Dedup / Rebuild Preparation

Use the recovery dedup output to decide what the canonical rebuild input should be.

```powershell
cd C:\CorpusForge
.\.venv\Scripts\python.exe scripts\build_document_dedup_index.py --input <source-folder>
```

Then review the duplicate output and freeze `canonical_files.txt` before the next rebuild.

### Track B: Structured-Store Exploitation

Use the current V2 structured store and the existing export package to keep demo and QA progress moving.

Recommended order:

1. audit the store and export packages
2. confirm the structured store still answers the current demo-critical queries
3. use `demo_gate.py` and `health_check.py` to validate current readiness
4. only then decide whether more extraction work is needed

---

## What Is Blocked

- full-corpus rebuild from the raw 700 GB source tree until canonical dedup is reviewed
- any installer cleanup work that does not affect current query or store progress
- enrichment assumptions unless a real export package with non-empty `enriched_text` is identified

---

## Useful Reference Commands

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\structured_progress_audit.py
.\.venv\Scripts\python.exe scripts\health_check.py
```

```powershell
cd C:\CorpusForge
.\.venv\Scripts\python.exe scripts\build_document_dedup_index.py --input <source-folder>
.\.venv\Scripts\python.exe scripts\run_pipeline.py --input-list <canonical_files.txt>
```

---

## Bottom Line

The immediate win is to use the current structured store and export packages to keep QA and demo work moving while the canonical rebuild path is being prepared. Do not wait on installer cleanup to make progress on the data side.
