# Entity Store Audit — V1 vs V2 Data Split

**Date:** 2026-04-08 MDT
**Author:** Jeremy Randall (CoPilot+)
**Store:** data/index/entities.sqlite3

---

## Summary

The entity store contains a mix of V1 and V2 data. This is expected and acceptable for demo. A clean V2-only re-extraction will happen after Forge Sprint 5 delivers the full corpus.

---

## Data Split

| Source | Entities | Share | Origin |
|--------|----------|-------|--------|
| V1 (HybridRAG3/Clone1 paths) | 40,400 | 98.6% | Overnight extraction from V1 corpus via phi4:14b |
| V2 golden corpus (data/source/) | 234 | 0.6% | Extracted from 5 curated golden eval files |
| Forge-imported (absolute C: paths) | 347 | 0.8% | GLiNER extraction from Forge S3 export |
| **Total** | **40,981** | **100%** | |

## Entity Type Distribution by Origin

| Type | Golden | V1 | Forge | Total |
|------|--------|-----|-------|-------|
| PART | 66 | 13,477 | 0 | 13,543 |
| CONTACT | 10 | 9,332 | 0 | 9,342 |
| DATE | 65 | 7,000 | 45 | 7,110 |
| ORG | 13 | 5,399 | 175 | 5,587 |
| PERSON | 43 | 2,075 | 112 | 2,230 |
| SITE | 25 | 2,096 | 15 | 2,136 |
| PO | 12 | 1,021 | 0 | 1,033 |

## V1 Source Path Pattern

V1 entities have paths like:
```
{USER_HOME}\Documents\HybridRAG3\data\source\verified\IGS\! Site Visits\...
```

These are real IGS maintenance documents extracted during overnight phi4 runs on the original V1 corpus (Clone1 copy).

## Why This Is Acceptable for Demo

1. **V1 entities are real data** -- they were extracted from genuine IGS/NEXION maintenance documents
2. **The entity store schema is the same** -- V1 and V2 entities use identical types (PERSON, PART, SITE, etc.)
3. **Golden eval passes 25/25** -- the entity retriever serves correct answers from both V1 and V2 entities
4. **The 234 golden entities are V2-native** -- demo queries trace to these curated files

## Plan for Clean V2 Re-extraction

When Forge Sprint 5 delivers the full corpus:
1. Run `import_forge_entities.py` on the S5 export (entities.jsonl with full GLiNER extraction)
2. Optionally truncate the V1 entities: `DELETE FROM entities WHERE source_path LIKE '%HybridRAG3%'`
3. Re-run golden eval to verify no regression
4. Document the new entity count and source distribution

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
