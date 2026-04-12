# V2 Index Architecture And Rebuild 2026-04-11

V2 does not use FAISS. V1 did. V2 uses LanceDB which provides vector search (IVF_PQ) and keyword search (FTS) from the same store. If you are grepping for FAISS references, you are looking at V1 documentation or historical commits.

## Short Answer

- V2 chunk retrieval lives in `data/index/lancedb`, not a FAISS file.
- V2 keyword search and vector search both come from the same LanceDB table.
- The normal import path builds FTS automatically and builds the IVF_PQ vector index when `--create-index` is passed.
- Tier 1 and Tier 2 extraction do not rebuild chunk indexes because they write entity and relationship SQLite stores, not `chunks.lance`.

## V1 Vs V2

| Topic | V1 (`HybridRAG3_Educational`) | V2 (`HybridRAG_V2`) |
|---|---|---|
| Vector store | FAISS index + separate vector sidecar/memmap patterns | LanceDB table with an internal IVF_PQ vector index |
| Keyword search | Separate SQLite FTS5 or equivalent keyword path | LanceDB FTS on the same chunk store |
| Hybrid retrieval | Cross-system fusion between separate stores | One LanceDB-backed store, plus hybrid builder chain in `LanceStore.hybrid_search()` |
| Rebuild command pattern | Separate FAISS rebuild and keyword-store rebuild workflows | `scripts/import_embedengine.py --create-index` for the normal path, or `LanceStore.create_vector_index()` + `LanceStore.create_fts_index()` manually |
| Post-extraction rebuild need | V1-specific and workflow-dependent | No chunk-index rebuild required; extraction writes entity/relationship SQLite stores only |

## What V2 Actually Stores

The V2 chunk store is implemented in `src/store/lance_store.py`.

- Table name: `chunks`
- Backing store: LanceDB under `data/index/lancedb`
- Vector field: `vector`
- Text field used for FTS: `text`
- Other retrieval fields: `enriched_text`, `source_path`, `chunk_index`, `parse_quality`

The important maintainer point is that this is one store with two index types, not a FAISS store plus a separate text index.

## When Indexes Get Built

### Vector IVF_PQ

Built by `LanceStore.create_vector_index()`.

- Called from `scripts/import_embedengine.py` after ingest when `--create-index` is passed
- Default index type is `IVF_PQ`
- Current implementation calls `self._table.create_index(..., index_type="IVF_PQ", replace=True)`
- Small stores under 10,000 rows intentionally skip vector index creation because the code treats them as too small to bother indexing

### FTS

Built by `LanceStore.create_fts_index()`.

- Called from `scripts/import_embedengine.py` after ingest
- Current implementation builds FTS on the `text` column
- Current implementation calls `self._table.create_fts_index("text", replace=True)`

### Import Behavior

The common production import path is:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\import_embedengine.py --source <export_dir> --create-index
```

That run gives you both indexes automatically:

- FTS is built unconditionally after ingest
- IVF_PQ is built by the `--create-index` branch

If you omit `--create-index`, V2 still builds FTS, but it does not build the IVF_PQ vector index.

## When Indexes Need Rebuilding

### Automatic cases

- After a fresh import, the normal import path handles index creation
- After appending chunks via later import runs, the same import path handles index creation again
- If you rerun import with `--create-index`, you get the same vector-index build path used for fresh stores

### Manual cases

- After a LanceDB version upgrade that changes index APIs or internal formats
- After detecting that an index exists in name only but query behavior is broken
- After debugging or recovery work that touches the LanceDB table directly outside the normal import path

### Cases that do not require rebuilds

- Tier 1 extraction runs
- Tier 2 extraction runs
- GUI extraction runs

Those paths read chunks from LanceDB and write entities/relationships into SQLite stores. They do not mutate the chunk table or rebuild the chunk indexes.

## Known API Evolution Traps

These are the exact class of silent dependency drift that future maintainers need to watch.

### Trap 1: `create_fts_index()` column API changed

- Older code path: `create_fts_index(["text", "enriched_text"], replace=True)`
- LanceDB 0.30+ requirement: a single string column name
- Current fix: `create_fts_index("text", replace=True)`
- Fixed in commit `715fe4b`

Why this matters:

- The break was silent enough that V2 ran for days with FTS effectively absent until real production-style retrieval probes exposed it
- If you upgrade LanceDB again, re-verify the FTS API before trusting a successful import log

### Trap 2: hybrid-search builder chain changed

- Older pattern: `search(vec, query_type="hybrid") ... .text(query_text)`
- LanceDB 0.30+ pattern: `search(query_type="hybrid").vector(vec).text(query_text)`
- Fixed in commit `957eaab`

Symptom to remember:

- If you see an error shaped like `You can either provide a string query in search()`, you are probably looking at another LanceDB API change around the hybrid builder

### Trap 3: real queries catch what imports can miss

Both of the bugs above were caught by real retrieval probes, not by happy-path import success alone.

History is recorded in:

- `docs/RETRIEVAL_BASELINE_PROBE_2026-04-11.md`
- `docs/RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md`

If you change LanceDB versions in the future, rerun real retrieval probes. Do not trust import success by itself.

## How To Verify Indexes Are Healthy

Run this from the repo root:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe -c "
from src.store.lance_store import LanceStore
s = LanceStore('data/index/lancedb')
print(f'Chunks: {s.count():,}')
print(f'Indexes: {s._table.list_indices()}')
results = s._table.search('maintenance', query_type='fts').limit(3).to_list()
print(f'FTS working: {len(results)} results')
"
```

Healthy signs:

- chunk count is non-zero when you expect a populated store
- `list_indices()` shows the vector index and the FTS/inverted index metadata
- the FTS query returns results instead of an index-missing error

Unhealthy signs:

- `list_indices()` is missing expected index metadata
- FTS query throws an inverted-index or FTS-missing error
- hybrid retrieval falls back to vector-only on production-style exact-token queries

## How To Rebuild Indexes Manually

Use this when you need a manual repair after version drift or direct table work:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe -c "
from src.store.lance_store import LanceStore
s = LanceStore('data/index/lancedb')
s.create_vector_index()
s.create_fts_index()
print('Both indexes rebuilt')
"
```

Notes:

- On small stores under 10,000 rows, `create_vector_index()` may intentionally skip creation
- FTS rebuild should still run
- After rebuild, rerun the health check and a real retrieval probe

## Files That Mention FAISS — Review These For Accuracy

These files are not automatically wrong. Many are historical design, waiver, or fallback-planning docs. They are, however, the places future maintainers are most likely to pick up the wrong V1 mental model if they read them without context.

- `docs/Architecture_Pseudocode_2026-04-04.md`
- `docs/Repo_Rules_2026-04-04.md`
- `docs/Requested_Waivers_2026-04-04.md`
- `docs/Sprint_Plan_2026-04-04.md`
- `docs/Sprint_Plan_Walking_Skeleton_2026-04-04.md`
- `docs/V2_Design_Proposal_2026-04-04.md`

Specific hit lines from the current grep are about:

- LanceDB replacing FAISS in the architecture description
- fallback planning if LanceDB had been blocked
- migration ideas from V1 FAISS into V2 LanceDB
- repo rules mentioning `.faiss` artifacts as files that should not be committed

Do not assume a FAISS mention in those docs means the current V2 runtime still uses FAISS.

## Related Files

- `src/store/lance_store.py` — the actual V2 chunk store, index creation, and hybrid search implementation
- `scripts/import_embedengine.py` — the import path that ingests chunks and builds FTS plus optional IVF_PQ
- `docs/HOW_TO_IMPORT_FORGE_EXPORT_TO_V2_LANCEDB.md` — operator import guide for the standard import path

## Maintainer Rule

If you are debugging V2 retrieval, start with LanceDB facts:

1. Does `data/index/lancedb` exist and contain the expected chunk count?
2. Does `list_indices()` show both vector and FTS index metadata?
3. Does an FTS probe succeed?
4. Does a hybrid probe succeed without builder-chain errors?

If you find yourself planning a FAISS rebuild for V2, stop. You are following a V1 path that does not apply here.
