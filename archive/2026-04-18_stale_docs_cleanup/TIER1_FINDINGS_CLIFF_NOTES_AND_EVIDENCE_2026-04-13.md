# Tier1 Findings Cliff Notes And Evidence 2026-04-13

## Purpose

This is the shortest high-visibility evidence summary for the Tier 1 lane.

It exists so future coordinators, agents, and reviewers can verify that the current plan is backed by:

- repo history
- concrete testing
- corpus/store analysis
- external research

## Cliff Notes

1. The old live Tier 1 store was polluted enough that `PO` and `PART` could not be trusted for business-facing answers.
2. A blind full rerun is the wrong validation mechanism.
3. Tier 1 regex should be treated as **candidate generation plus validation**, not final truth.
4. A `5,000-10,000` chunk shadow run is required before any future full Tier 1 rerun.
5. Future data should follow a **stage -> audit -> promote** path so dirty deltas never reach the authoritative store.
6. The next execution sequence is:
   - run the regex gate
   - run the shadow Tier 1 slice
   - approve or reject the full rerun
   - run one clean full Tier 1 rerun only if approved
   - rerun the 400-query baseline on the cleaned store

## Repo-History Evidence

### Regex hardening

- `34b64d8` Tighten Tier 1 PO and part boundary guards
- `1620084` docs: formalize tier1 regex acceptance gate

Supporting docs:

- [docs/TIER1_REGEX_ACCEPTANCE_GATE_2026-04-12.md](./docs/TIER1_REGEX_ACCEPTANCE_GATE_2026-04-12.md)
- [docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md](./docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md)

### Corpus/store evidence

- `d0476bb` docs: audit tier1 PO and PART confusion sets
- `54eadec` docs: add tier1 regex corpus rerun audit

Supporting docs:

- [docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12.md](./docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12.md)
- [docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12_RERUN.md](./docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12_RERUN.md)

Key proven facts:

- old live `PO` was dominated by control-family junk
- old live `PART` was polluted by STIG / baseline / advisory debris
- preserve-set real POs and parts still exist in the clean rerun cross-check store

### Automated gate evidence

- `f3bafb7` Add Tier 1 regex pre-rerun gate
- `a45e62f` strengthen tier1 regex gate curated cases

Supporting docs:

- [docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md](./docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md)
- [TIER1_RESEARCH_TO_EXECUTION_SPRINT_PLAN_2026-04-13.md](./TIER1_RESEARCH_TO_EXECUTION_SPRINT_PLAN_2026-04-13.md)

### Evaluation and downstream impact

- [docs/PRODUCTION_EVAL_400_BASELINE_2026-04-12.md](./docs/PRODUCTION_EVAL_400_BASELINE_2026-04-12.md)
- [docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md](./docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md)
- [ENGINEERING_STATUS_AND_ARCHITECTURE_RESET_2026-04-12.md](./ENGINEERING_STATUS_AND_ARCHITECTURE_RESET_2026-04-12.md)

Key proven facts:

- current baseline is usable enough to show miss families
- retrieval/router work should start from a cleaned Tier 1 baseline, not the polluted store

## External Research Evidence

Primary synthesis:

- [docs/TIER1_REGEX_RESEARCH_SYNTHESIS_2026-04-12.md](./docs/TIER1_REGEX_RESEARCH_SYNTHESIS_2026-04-12.md)

Top research-backed conclusions:

- regex should be treated as candidate generation, not truth
- shadow-run approval should happen before a full rerun
- shape-aware blocking is better than naive prefix-only blocking
- ambiguous identifiers should fail closed
- the eventual model should separate business purchase orders from report/control identifiers

## Cross-Document Synthesis

If someone wants the shortest chain of proof, read these in order:

1. [docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12.md](./docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12.md)
2. [docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12_RERUN.md](./docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12_RERUN.md)
3. [docs/TIER1_REGEX_ACCEPTANCE_GATE_2026-04-12.md](./docs/TIER1_REGEX_ACCEPTANCE_GATE_2026-04-12.md)
4. [docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md](./docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md)
5. [docs/TIER1_REGEX_RESEARCH_SYNTHESIS_2026-04-12.md](./docs/TIER1_REGEX_RESEARCH_SYNTHESIS_2026-04-12.md)
6. [TIER1_RESEARCH_TO_EXECUTION_SPRINT_PLAN_2026-04-13.md](./TIER1_RESEARCH_TO_EXECUTION_SPRINT_PLAN_2026-04-13.md)

## One-Paragraph Coordinator Summary

The Tier 1 lane is already backed by both repo evidence and external research. Repo history proves the old store was polluted, the hardening work exists, the confusion sets are documented, and an automated pre-rerun gate exists. External research supports the same execution model: treat regex as candidate generation with validators, do a shadow run before any full rerun, and use a staged promotion model for future deltas. The only correct next move is disciplined execution, not more rediscovery.
