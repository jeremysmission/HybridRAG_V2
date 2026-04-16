# Lane 2 Evidence Memo

Date: 2026-04-13
Repo: `C:\HybridRAG_V2`
Scope: Structured + Tabular Foundation

## What changed

- Relationship-store path resolution is now canonicalized in code via `src/store/relationship_store.py`.
- `scripts/health_check.py`, `scripts/boot.py`, `src/api/server.py`, and `scripts/tiered_extract.py` now agree on the real sibling relationship store path instead of silently pointing `RelationshipStore` at `entities.sqlite3`.
- `scripts/health_check.py` now accepts `--config` so the clean Tier 1 baseline can be checked directly.
- `scripts/tiered_extract.py` now has:
  - a staged promotion path via `--stage-dir`
  - a clean-baseline write guard for Tier 2 and table work
  - an audit artifact output via `--audit-json`
  - a logistics-first deterministic table pilot via `--table-mode logistics`
  - Tier 2 filtering narrowed to `PERSON` / `ORG` / `SITE`
- Deterministic table extraction now covers:
  - markdown tables
  - `[ROW n]` spreadsheet fragments
  - comma-separated key/value record rows from logistics spreadsheets and DD250-style chunks
  - calibration projection rows
  - spares/inventory rows with trailing quantity structure

## Verified runtime truth

Command:

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe `
  C:\HybridRAG_V2\scripts\health_check.py `
  --config C:\HybridRAG_V2\config\config.tier1_clean_2026-04-13.yaml `
  --json
```

Observed counts:

- Lance chunks: `10,435,593`
- Entities: `5,781,766`
- Table rows: `0`
- Relationships: `59`
- Relationship path: `C:\HybridRAG_V2\data\index\clean\tier1_clean_20260413\relationships.sqlite3`

Command:

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe `
  C:\HybridRAG_V2\scripts\boot.py `
  --config C:\HybridRAG_V2\config\config.tier1_clean_2026-04-13.yaml
```

Observed:

- boot output now prints the real `Rel DB` path
- boot no longer implies relationships share `entity_db`

Command:

```powershell
@'
from src.api.server import create_app
app = create_app(r'C:\HybridRAG_V2\config\config.tier1_clean_2026-04-13.yaml')
print(app.title)
'@ | C:\HybridRAG_V2\.venv\Scripts\python.exe -
```

Observed:

- server startup logged `59 relationships`
- server startup logged the real relationship DB path

## Audited table pilot

Command:

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe `
  C:\HybridRAG_V2\scripts\tiered_extract.py `
  --tier 1 `
  --limit 1000 `
  --dry-run `
  --table-mode logistics `
  --table-limit 200 `
  --audit-json C:\HybridRAG_V2\docs\lane2_table_pilot_audit_2026-04-13.json `
  --config C:\HybridRAG_V2\config\config.tier1_clean_2026-04-13.yaml
```

Observed:

- Tier 1 slice result: `0` entities / `0` relationships in the first `1000` generic chunks
- Logistics table pilot: `289` raw rows
- Family row counts in this filtered sample:
  - `bom: 289`
- Audit artifact written:
  - [lane2_table_pilot_audit_2026-04-13.json](/C:/HybridRAG_V2/docs/lane2_table_pilot_audit_2026-04-13.json)

Interpretation:

- The substrate is no longer aspirational only; deterministic row recovery is working on real logistics-family chunks.
- This was intentionally a dry run against the clean baseline.
- In-place promotion is blocked unless a staged store is used or the operator explicitly overrides the guard.

## Audited Tier 2 path

Command:

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe `
  C:\HybridRAG_V2\scripts\tiered_extract.py `
  --tier 2 `
  --limit 200 `
  --dry-run `
  --audit-json C:\HybridRAG_V2\docs\lane2_tier2_audit_2026-04-13.json `
  --config C:\HybridRAG_V2\config\config.tier1_clean_2026-04-13.yaml
```

Observed:

- Device selected: `cuda:1`
- Raw Tier 2 entities on the limited slice: `471`
- Type counts:
  - `ORG: 242`
  - `SITE: 124`
  - `PERSON: 105`
- Audit artifact written:
  - [lane2_tier2_audit_2026-04-13.json](/C:/HybridRAG_V2/docs/lane2_tier2_audit_2026-04-13.json)

Interpretation:

- The audited Tier 2 promotion path is prepared and functioning.
- This was a scoped dry run only. It is evidence that the promotion slice is measurable, not a claim that the clean store has been fully re-promoted.

## Tests

Command:

```powershell
C:\HybridRAG_V2\.venv\Scripts\pytest.exe tests\test_extraction.py tests\test_tiered_extract.py -q
```

Result:

- `127 passed in 1.90s`

Coverage added in this lane:

- relationship path normalization
- relationship-store rebinding from `entities.sqlite3` to the sibling relationship DB
- logistics-family detection
- deterministic extraction for PR/PO, DD250, calibration, and spares/inventory chunk shapes
- filtered logistics table streaming
- staged store copy helper
- clean-baseline guard helper

## Remaining risks

- The table pilot result above is a filtered dry run, not a full-corpus promoted table store.
- Full Tier 2 promotion on the clean store is still pending a staged run plus audit review; broad aggregation claims remain out of scope.
- `scripts/tiered_extract.py` still runs Tier 1 before the optional table pass, so full-corpus table audits should use a bounded `--limit` or a staged overnight run plan.
- The old runtime miswiring is fixed in the owned surfaces, but non-owned scripts that instantiate `RelationshipStore(cfg.paths.entity_db)` still rely on the new resolver fallback rather than explicit path cleanup.
