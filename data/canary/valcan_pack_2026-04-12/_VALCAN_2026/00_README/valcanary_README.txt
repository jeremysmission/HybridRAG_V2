[CANARY-VALIDATION-DOCUMENT-DO-NOT-USE-IN-PRODUCTION]
Canary Namespace: VALCAN-2026
Canary Document ID: VALDOC-001
Canary Bundle: 00_README
Synthetic Owner: Jane Canary
Production Use: prohibited
Repo Pack Root: data/canary/valcan_pack_2026-04-12/_VALCAN_2026/00_README/
Future Deploy Root: E:\CorpusTransfr\verified\IGS\_VALCAN_2026\

VALCAN Validation Pack README
=============================

This folder contains a synthetic validation pack for Task 18 canary-backed aggregation testing.
All sites, parts, contracts, people, and directives in this subtree are synthetic.
Document-level identifiers use the VALCAN / VALDOC namespace, while extractor-visible PO, PART, and SITE values are intentionally shaped to match the current V2 extraction path.
The pack is designed for deterministic aggregation validation and for rehearsed demo controls.
It contains five persona lanes: program management, logistics, field engineering, cybersecurity, and cross-role readiness.
Future deployment path for injection is E:\CorpusTransfr\verified\IGS\_VALCAN_2026\
Repo-local authoring path for this staged pack is data/canary/valcan_pack_2026-04-12/_VALCAN_2026/.
Do not merge this subtree into production source roots without an explicit coordinator decision.

Current synthetic token shapes
-----------------------------

- PO values land through the current labeled SAP-style regex path as:
  PO 9001000001 through PO 9001000012
- PART values land through the active generic part regex as:
  QZ-3001 through QZ-3016
- SITE values land through labeled fields as:
  Site: Validation Alpha Site through Site: Validation Echo Site

Ground truth source
-------------------

Authoritative known-answer facts live in:
data/canary/valcan_pack_2026-04-12/ground_truth_registry.json

That registry is the source of truth for:
- the two canary-backed demo controls
- the three real-scoped manual-count demo checks
- per-file SHA-256 hashes for the authored pack

Hash policy
-----------

- valcanary_source_manifest.txt is a human-readable in-pack hash ledger for every other file under _VALCAN_2026.
- The manifest intentionally does not hash itself, because a self-embedded SHA-256 entry is not stable.
- The authoritative hash for valcanary_source_manifest.txt itself is stored in ground_truth_registry.json.
- ground_truth_registry.json is therefore the complete integrity record for all 40 authored pack files.

Operational use
---------------

1. Keep this pack out of live production source roots until a coordinator explicitly approves injection.
2. When staged for rehearsal, preserve the folder name `_VALCAN_2026` and the `valcanary_` filename prefix.
3. In the authoritative Forge repo at C:\CorpusForge, the nightly-delta path currently uses a broad `*canary*` glob, so `valcanary_*` files are surfaced by that path today.
4. Before any rehearsal, verify:
   - 40 authored files exist
   - the registry file matches this pack revision
   - the marker string is present in imported chunks
   - the canary entity values land in V2 as expected
5. Treat any mismatch between the registry and live query answers as a rehearsal blocker.
