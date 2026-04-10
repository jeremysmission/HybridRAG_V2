# Changelog

This file retroactively tracks notable changes from git metadata for `HybridRAG_V2`.

The repo did not use formal release tags or semantic versions during the initial buildout, so the historical sections below are grouped by commit date. Future revisions should keep `Unreleased` at the top and cut explicit versions only when a meaningful integrated change lands.

## Unreleased

- Revision policy and formal version tagging not yet started.

## 2026-04-09

### Added

- Import fallback audit trail and updated operator-facing import documentation.

### Notes

- This is the latest committed history point as of `2026-04-09T07:32:08-06:00` (`592f64f`).

## 2026-04-08

### Added

- Overnight QA hardening for adversarial inputs, edge-case queries, and demo-prep documentation.
- Entity-store audit and golden-eval traceability documentation.
- Retrieval tuning sweep tooling and related research notes.
- Tiered entity extraction with concurrent execution.
- Additional golden-eval hallucination-trap coverage.
- Real field-data import and regex pre-extraction assessment.

### Changed

- CPU reservation handling was tightened and later expanded with per-layer status logging.
- Golden-eval assets, V1 tuning artifacts, and retrieval research were consolidated.
- Remote-push hygiene and repository sanitization were tightened across the repo.

## 2026-04-07

### Added

- Recovery-dedup sprint tracking and closure artifacts.
- Sprint 12 import hardening, Sprint 13 canonical rebuild flow, Sprint 14 entity promotion, and Sprint 15 operator hardening.
- Rebuild scripts and retrieval-only entity-store fixes.
- Demo rehearsal and latency hardening with documented `P50=20ms`.

### Changed

- Golden-eval coverage was restored to passing after rebuild and entity-store fixes.
- The repo shifted from recovery work into a stable canonical rebuild and operator-hardening path.

## 2026-04-06

### Added

- Packaged Sprint 10 work and pivoted Sprint 11 into dedup recovery.
- Hardened workstation setup, torch recovery lanes, and related install guidance.
- Recovery evidence, action plans, workstation notes, and assembly-line/operator planning docs.

### Changed

- Installer and setup guidance became a first-class lane rather than ad hoc notes.

## 2026-04-05

### Added

- Sprint 2 tri-store extraction and query-router path.
- Sprint 3 CRAG verification, GUI, enrichment flow, and larger golden-eval set.
- Sprint 4 performance tuning, setup validation, deployment-readiness checks, launcher BAT, and demo tooling.
- Sprint 5 infrastructure work including A/B testing, import hardening, setup scripts, and compatibility fixes.
- Separate model selection for bulk extraction vs query-time work.
- Demo-gate and autonomous execution planning for subsequent sprints.

### Changed

- Query and demo workflows were hardened through QA fixes, bootstrap fixes, and benchmark wiring fixes.
- Planning shifted to a dependency-ordered sprint structure backed by the V1 400-query golden set.

## 2026-04-04

### Added

- Initial repo design proposal, architecture pseudocode, waivers, and sprint planning.
- Repo rules, sanitization script, and theory-of-operations documents.
- Sprint 0 baseline: config schemas, LanceDB store, query pipeline, and first golden-eval pass.
- Sprint 1 reranking, context builder upgrade, streaming SSE, expanded evaluation, and QA packet.

### Changed

- The repo moved from planning state to a working query pipeline on day one.

## Notes

- This is a retroactive changelog assembled from commit metadata on `2026-04-09`.
- Historical entries are grouped by milestone day because the repo did not yet maintain formal semantic-version releases.
- Repeated `sanitize before push` commits are retained in the appendix for auditability, but summarized into the adjacent workday section above.

## Appendix: Commit Metadata Ledger

| Timestamp | SHA | Subject |
|---|---:|---|
| `2026-04-04T18:26:44-06:00` | `5715704` | Initial V2 repo: design proposal, waivers, sprint plan, architecture pseudocode |
| `2026-04-04T18:30:00-06:00` | `6b89a52` | Add repo rules, sanitization script, and theory of operations docs |
| `2026-04-04T18:57:19-06:00` | `4f81d87` | Add unified Walking Skeleton sprint plan across both repos |
| `2026-04-04T21:34:08-06:00` | `09a498e` | Sprint 0: config schemas, LanceDB store, query pipeline, golden eval 5/5 |
| `2026-04-04T21:34:35-06:00` | `d221819` | Sanitize for remote push |
| `2026-04-04T21:45:14-06:00` | `b0961a6` | Sprint 1: FlashRank reranking, context builder upgrade |
| `2026-04-04T22:07:47-06:00` | `a8f18d6` | Sprint 1 complete: streaming SSE, expanded golden eval 10/10 |
| `2026-04-04T22:13:40-06:00` | `c26a80d` | Sprint 1 QA: 12/12 pass, eval results updated |
| `2026-04-04T22:24:30-06:00` | `01bc8ed` | Add Sprint 0+1 handoff doc |
| `2026-04-05T10:47:20-06:00` | `aaad37c` | feat: Sprint 2 complete — tri-store extraction, query router, QA 11/11 |
| `2026-04-05T10:47:37-06:00` | `2277111` | chore: sanitize for remote push |
| `2026-04-05T10:57:08-06:00` | `c0a1db7` | feat: Sprint 3 complete — CRAG verification, GUI, enrichment, 25 golden queries |
| `2026-04-05T11:29:39-06:00` | `a7d2221` | fix: Sprint 3 QA defects — CRAG wiring, GUI bootstrap, SQLite thread safety |
| `2026-04-05T11:48:16-06:00` | `925b4f7` | feat: Sprint 4 complete — perf tuning, V1vsV2 harness, demo prep, docs |
| `2026-04-05T11:48:30-06:00` | `93e58fe` | chore: sanitize for remote push |
| `2026-04-05T12:01:13-06:00` | `70824b1` | docs: add 70-point GUI human visual checklist for demo gate |
| `2026-04-05T12:06:10-06:00` | `dd94d4f` | feat: setup validator (16 checks) + health dashboard for deployment readiness |
| `2026-04-05T12:08:17-06:00` | `207cf4b` | fix: Sprint 4 QA defects — boot helper, benchmark wiring, generator prompts |
| `2026-04-05T12:09:36-06:00` | `9159eec` | feat: one-click GUI launcher bat with venv checks and GPU pinning |
| `2026-04-05T12:21:23-06:00` | `60a6d21` | feat: demo script personas + skip notes, improved import script |
| `2026-04-05T12:21:31-06:00` | `275a176` | chore: sanitize for remote push |
| `2026-04-05T13:08:25-06:00` | `b976f40` | docs: revised 5-sprint plan (dependency-ordered) + 400-query golden set from V1 |
| `2026-04-05T13:17:32-06:00` | `e8e321c` | feat: separate extraction model config — gpt-4o-mini for bulk, gpt-4o for queries |
| `2026-04-05T15:03:42-06:00` | `ddaa06e` | feat: Sprint 5 infrastructure — A/B test, import hardening, setup scripts, compatibility fixes |
| `2026-04-05T17:08:26-06:00` | `476eb6c` | docs: theory of operations, pipeline guide, AWS enrichment concept, overnight extraction |
| `2026-04-05T17:29:39-06:00` | `39fb9e9` | docs: session 2 handover -- Sprint 5 complete, Sprint 6 ready |
| `2026-04-05T17:32:33-06:00` | `5222dbe` | docs: handover updated with autonomous Sprint 6+7 execution plan |
| `2026-04-05T18:42:18-06:00` | `1456449` | sprint6-7: scale proof, demo prep, and qa follow-up |
| `2026-04-05T22:36:27-06:00` | `3b71cd2` | feat: add dedicated Sprint 8 demo gate path |
| `2026-04-06T06:59:25-06:00` | `20ec3f5` | feat: close sprint 9 gaps and package sprint 10 |
| `2026-04-06T08:00:34-06:00` | `5b6e9d7` | docs: pivot sprint 11 to dedup recovery |
| `2026-04-06T08:05:36-06:00` | `7f3377f` | docs: add legacy dedup evidence from a prior system |
| `2026-04-06T08:23:57-06:00` | `00e0557` | install: harden workstation setup lane |
| `2026-04-06T08:24:29-06:00` | `8dc9eb5` | docs: sanitize workstation install guide |
| `2026-04-06T10:34:53-06:00` | `eeb4f2f` | install: clarify torch proxy failures |
| `2026-04-06T10:50:14-06:00` | `249d0f3` | install: add blackwell torch recovery lane |
| `2026-04-06T12:05:03-06:00` | `aca279b` | install: fix workstation setup flow |
| `2026-04-06T12:22:27-06:00` | `e8789ba` | docs: add sprint 11 work sequence and todo |
| `2026-04-06T17:25:11-06:00` | `cc0b63a` | docs: add workstation desktop torch install note |
| `2026-04-06T17:27:05-06:00` | `1c3d02f` | docs: rename root guide and sanitize content |
| `2026-04-06T17:34:46-06:00` | `197017c` | docs: add workstation torch quick commands |
| `2026-04-06T18:08:07-06:00` | `91718e1` | setup: add assessment pause to workstation installer |
| `2026-04-06T18:11:40-06:00` | `25d92c1` | docs: update sprint 11 queue with sidecar workstreams |
| `2026-04-06T18:12:11-06:00` | `1d052ce` | docs: add structured progress audit and action plan |
| `2026-04-06T18:36:19-06:00` | `3833ce3` | docs: carry forward proven workstation install lessons |
| `2026-04-06T18:59:38-06:00` | `0f99b09` | docs: add operation freeload chronology and assembly line plan |
| `2026-04-06T19:51:51-06:00` | `d38cd53` | tools: pause root workstation installer on exit |
| `2026-04-06T20:37:26-06:00` | `2c12c1a` | docs: add 2026_7_4 todo list |
| `2026-04-06T21:17:27-06:00` | `49cb58f` | docs: add recovery demo handover |
| `2026-04-07T07:50:47-06:00` | `ad37176` | Document Forge QA closure and recovery dedup sprint |
| `2026-04-07T07:52:51-06:00` | `c281d1b` | Start recovery dedup sprint |
| `2026-04-07T07:53:50-06:00` | `a75fdfa` | Update recovery dedup sprint status |
| `2026-04-07T07:54:44-06:00` | `7586052` | Update dedup sprint coverage status |
| `2026-04-07T21:05:01-06:00` | `8001953` | Sprint 12: harden import pipeline, close recovery dedup |
| `2026-04-07T21:05:29-06:00` | `d56418b` | Sanitize before push |
| `2026-04-07T21:29:04-06:00` | `f615604` | Add CoPilot+.md, Sprint 13 rebuild scripts, golden eval 25/25 |
| `2026-04-07T21:29:27-06:00` | `3790eba` | Sanitize before push |
| `2026-04-07T21:52:55-06:00` | `66e9433` | Sprint 13: canonical rebuild from Forge S2 export, 20/25 golden eval |
| `2026-04-07T21:53:07-06:00` | `0da26db` | Sanitize before push |
| `2026-04-07T22:17:59-06:00` | `ae1f49b` | Fix golden eval: enable entity store in retrieval-only mode, 25/25 |
| `2026-04-07T23:12:13-06:00` | `153c4f3` | Sprint 14: entity promotion from Forge S3, 25/25 golden eval |
| `2026-04-07T23:12:30-06:00` | `27736ee` | Sanitize before push |
| `2026-04-07T23:42:41-06:00` | `df5ba9d` | Sprint 15: operator hardening, demo rehearsal 10/10, P50=20ms |
| `2026-04-08T01:00:15-06:00` | `086a160` | Overnight QA: adversarial input fix, edge case queries, demo prep docs |
| `2026-04-08T01:11:16-06:00` | `beb1b2b` | Add entity store audit and golden eval traceability docs |
| `2026-04-08T01:11:30-06:00` | `64f03b4` | Sanitize before push |
| `2026-04-08T01:14:05-06:00` | `b2737c3` | Consolidate all golden eval data into tests/golden_eval/ |
| `2026-04-08T01:14:15-06:00` | `25de6c5` | Sanitize before push |
| `2026-04-08T01:16:06-06:00` | `4c22235` | Consolidate V1 tuning scripts, autotune, probe results, benchmarks |
| `2026-04-08T01:16:18-06:00` | `bfe6e0d` | Sanitize before push |
| `2026-04-08T01:25:09-06:00` | `efc1828` | Add retrieval tuning sweep script and research doc |
| `2026-04-08T01:26:55-06:00` | `5c31386` | Document reranker finding: zero accuracy gain on current corpus |
| `2026-04-08T01:29:21-06:00` | `e5ff875` | Complete tuning research: entity extraction, retrieval, stress test design |
| `2026-04-08T01:29:33-06:00` | `b521527` | Sanitize before push |
| `2026-04-08T01:31:18-06:00` | `2884558` | Add 6 hallucination trap queries to golden eval (36 total) |
| `2026-04-08T01:31:28-06:00` | `5783335` | Sanitize before push |
| `2026-04-08T05:50:02-06:00` | `6e5b3a0` | Import 32K real field data, regex pre-extraction assessment, 3x variance |
| `2026-04-08T06:04:52-06:00` | `a5aec90` | Implement tiered entity extraction with ThreadPoolExecutor concurrency |
| `2026-04-08T07:56:13-06:00` | `812ee43` | docs: recovery action plan + tiered extraction + 53 tests |
| `2026-04-08T07:57:24-06:00` | `cb17f18` | docs: dedup-only pass operator guide (cross-repo reference) |
| `2026-04-08T12:16:56-06:00` | `1132142` | fix: 3-layer CPU reservation — affinity + priority + thread cap |
| `2026-04-08T12:19:54-06:00` | `172d729` | fix: sanitize 44 files — remove program-specific terms from remote |
| `2026-04-08T12:50:55-06:00` | `5357471` | fix: remove zip from tracking, add image/zip patterns to .gitignore |
| `2026-04-08T18:55:08-06:00` | `ae050d4` | fix: CPU reservation — per-layer status logging + 13 unit tests |
| `2026-04-08T19:16:03-06:00` | `91e016f` | fix: remove CoPilot+.md from tracking, pin gliner, sync sprint status |
| `2026-04-09T07:32:08-06:00` | `592f64f` | Add import fallback audit trail and updated operator docs |
