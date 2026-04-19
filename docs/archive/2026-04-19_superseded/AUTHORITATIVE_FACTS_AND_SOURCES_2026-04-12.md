# Authoritative Facts And Sources — 2026-04-12

**Purpose:** Compact source-of-truth note for QA, docs work, and operator comms.
**Rule:** When counts disagree, live repo-local probes win over narrative docs.

## Verified Current Facts

| Fact | Value | Probe basis |
|---|---:|---|
| Chunks | **10,435,593** | `data/index/lancedb` |
| Entity rows | **19,959,604** | `data/index/entities.sqlite3` |
| Relationships | **59** | `data/index/relationships.sqlite3` |
| Extracted-table rows | **0** | `data/index/entities.sqlite3` |

## Exact Source Locations Probed

- `C:\HybridRAG_V2\data\index\lancedb`
- `C:\HybridRAG_V2\data\index\entities.sqlite3`
- `C:\HybridRAG_V2\data\index\relationships.sqlite3`

## Canonical Vs Non-Canonical

### Canonical

- Direct repo-local probes against the three paths above
- Tracked docs that remain accurate for non-count guidance:
  - `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md`
  - `docs/DEMO_DAY_RESEARCH_2026-04-12.md`
  - `docs/CANARY_INJECTION_METHODOLOGY_2026-04-12.md`

### Non-Canonical When They Conflict With Live Probes

- Untracked `docs/COORDINATOR_STATE_2026-04-12_evening.md`
- Older count snapshots such as:
  - `docs/CRASH_RECOVERY_2026-04-12.md`
  - `docs/COORDINATOR_STATE_2026-04-11.md`
  - any checklist, script, or environment doc still anchored to obsolete store counts

## Operator Note

If a narrative doc and a live repo-local probe disagree on chunk, entity, relationship, or extracted-table counts, use the live repo-local probe and treat the doc as stale until reissued.

## Reproducible Probe Commands

```powershell
@'
import sqlite3
import sys
sys.path.insert(0, r'C:\HybridRAG_V2')
from src.store.lance_store import LanceStore

ls = LanceStore(r'C:\HybridRAG_V2\data\index\lancedb')
print('chunks', ls.count())
ls.close()

conn = sqlite3.connect(r'C:\HybridRAG_V2\data\index\entities.sqlite3')
print('entity_rows', conn.execute('select count(*) from entities').fetchone()[0])
print('extracted_table_rows', conn.execute('select count(*) from extracted_tables').fetchone()[0])
conn.close()

conn = sqlite3.connect(r'C:\HybridRAG_V2\data\index\relationships.sqlite3')
print('relationships', conn.execute('select count(*) from relationships').fetchone()[0])
conn.close()
'@ | & 'C:\HybridRAG_V2\.venv\Scripts\python.exe' -
```

## Probe Result Captured

- `chunks 10435593`
- `entity_rows 19959604`
- `extracted_table_rows 0`
- `relationships 59`
