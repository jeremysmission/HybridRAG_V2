# Format Porting Guardrail 2026-04-07

## Purpose

Prevent future ingest and indexing repos from inheriting silent parser-coverage drift, hidden allowlist gaps, or invisible deferred-format behavior when code is copied from earlier stacks.

---

## The Lesson

`CorpusForge` is a new repo, but it reused a meaningful amount of ingest logic from `HybridRAG3`.

That means copied ingest code can carry forward:

- parser coverage assumptions
- placeholder parser behavior
- deferred CAD and drawing policies
- stale allowlists
- discovery filters that no longer match the parser registry

The dangerous failure mode is not just "format unsupported."

The dangerous failure mode is:

- the operator thinks the run covered the source folder
- but some formats were silently dropped or under-accounted for

That is a production risk.

---

## Mandatory Checks Before Trusting A Port

Every future ingest/indexing port must explicitly answer:

1. What formats are fully parsed?
2. What formats are placeholder-only?
3. What formats are hashed-only or deferred?
4. What formats are unsupported?
5. Does the live discovery filter exactly match the intended coverage policy?
6. Are deferred formats visible to the operator and written into skip accounting?

If any of these are unknown, the port is not yet production-trustworthy.

---

## Required Engineering Rule

Before production use of any ported ingest path:

1. Diff parser registry coverage against the active allowlist or discovery filter.
2. Diff parser registry coverage against workstation and operator docs.
3. Confirm deferred formats are surfaced in preflight and final accounting.
4. Confirm the operator can distinguish:
   - parsed
   - deferred
   - unsupported
5. Treat silent format disappearance as a bug, not a limitation.

---

## Current Applied Example

`CorpusForge` surfaced this exact issue:

- some drawing/CAD formats were intentionally deferred
- but the original Forge discovery path could let them disappear before the skip-manager stage
- that made the run boundary look cleaner than it really was

The fix direction is now explicit:

- deferred formats must still be discovered
- deferred formats must be counted
- deferred formats must be written to `skip_manifest.json`
- unsupported formats must be called out clearly

---

## Standard Going Forward

Do not copy parser/indexer code blindly.

For any future repo:

- coverage audit first
- operator accounting second
- production trust only after both are documented
