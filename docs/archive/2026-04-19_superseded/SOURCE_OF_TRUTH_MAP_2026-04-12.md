# Source Of Truth Map — 2026-04-12

**Purpose:** Define which docs are canonical, which are historical, and which are unsafe for current operator or QA use.
**Rule:** If a doc conflicts with a live repo-local probe, the live repo-local probe wins.

## Canonical

| Need | Canonical source | Why |
|---|---|---|
| Canonical repo roots | `C:\CorpusForge` and `C:\HybridRAG_V2` | These are the only authoritative working repos for current QA and implementation |
| Live counts and reproducible evidence | `docs/AUTHORITATIVE_FACTS_AND_SOURCES_2026-04-12.md` | Probe-backed current facts with exact paths and commands |
| Current demo claims, guardrails, and pre-demo checks | `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` | Current operator-facing May 2 packet |
| Current demo query avoid list | `docs/QUERIES_TO_AVOID_FOR_DEMO_2026-04-13.md` | Consolidated list of aggregation-heavy and narration-unsafe queries to keep off stage |
| Honesty boundary on what V2 can and cannot claim | `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md` | Current RED/YELLOW read on retrieval, aggregation, router, and stage risk |
| Which legacy docs are retired or unsafe | `docs/STALE_DOC_RETIREMENT_MAP_2026-04-12.md` | Current stale-doc disposition map |
| Contributor research and recency rules | `docs/RESEARCH_STANDING_ORDERS.md` | Current implementation-time research rule |
| Current remaining-work execution order | `docs/SPRINT_SLICE_PRODUCT_COMPLETION_2026-04-13.md` | Current coordinated product-completion plan |
| Current eval truth for retrieval progress | `docs/PRODUCTION_EVAL_RESULTS_POST_CDRL_PATH_PATCH_400_2026-04-13.md` and `docs/PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md` | Current measured 400-query and clean-store baselines supersede older `25/25 final` language |
| Current operator / installer / OCR preflight evidence | `docs/LANE3_OPERATOR_INSTALLER_PREFLIGHT_EVIDENCE_2026-04-13.md` | Exact machine probes, commands, fixes, and remaining OCR dependency gap |
| Current coordinator continuity state | `docs/COORDINATOR_CONTINUITY_NOTES_2026-04-13.md` | Durable crash-recovery note for accepted QA outcomes, lessons learned, and pending items |
| Current full reboot handover | `docs/REBOOT_HANDOVER_2026-04-13.md` | Single-file recovery entrypoint for where we are, what passed QA, what is still running, and how to resume safely |

## Current Operator / QA Guardrails

- `{USER_HOME}\codex_tmp\...` copies are study or recovery clones only. They are non-authoritative unless explicitly promoted.
- Repo-local `.venv` is required for QA and local validation.
- OCR and scanned-document QA on this machine is currently partial because Tesseract is installed only at `C:\Program Files\Tesseract-OCR\tesseract.exe` and may be off-PATH, while `pdftoppm.exe` / Poppler is not currently discoverable.
- `scripts/health_check.py` and `scripts/validate_setup.py` now resolve LLM availability through the live credential path, including Windows keyring-backed credentials.

## Historical But Still Useful

Use these for context, not as final truth when counts or readiness claims disagree:

- `docs/CRASH_RECOVERY_2026-04-12.md`
- `docs/COORDINATOR_STATE_2026-04-11.md`
- `docs/PRODUCTION_EVAL_RESULTS_2026-04-11.md`
- `docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md`
- `docs/DEMO_DAY_RESEARCH_2026-04-12.md`
- `docs/CANARY_INJECTION_METHODOLOGY_2026-04-12.md`

## Unsafe Or Non-Canonical

Do not use these as current truth without reissue or direct reprobe:

- any `{USER_HOME}\codex_tmp\...` repo copy
- Untracked `docs/COORDINATOR_STATE_2026-04-12_evening.md`
- `docs/DEMO_DAY_CHECKLIST_2026-04-07.md`
- `docs/DEMO_SCRIPT_2026-04-05.md`
- `docs/ENVIRONMENT_ASSUMPTIONS_2026-04-08.md`
- `docs/SPRINT_SYNC.md`

## Conflict Resolution

1. For chunk, entity, relationship, or extracted-table counts: use direct repo-local probes.
2. For May 2 operator behavior: use the canonical demo packet unless it conflicts with live probes.
3. For claim boundaries: use the readiness gap analysis over older scripts, checklists, or sprint language.
4. If a doc is untracked or locally modified and conflicts with a tracked canonical doc, treat it as non-canonical until reissued.
5. Root onboarding notes are convenience indexes only; they do not override this map.
6. For QA environment readiness, prefer direct setup and health probes over narrative docs.

## Short Operator Rule

When in doubt:

- counts -> live repo-local probes
- demo posture -> `MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md`
- stale-doc calls -> `STALE_DOC_RETIREMENT_MAP_2026-04-12.md`
- QA machine readiness -> repo-local `.venv` + direct setup/health scripts
