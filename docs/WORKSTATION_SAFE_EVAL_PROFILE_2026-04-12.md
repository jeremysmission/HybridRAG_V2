# Workstation-Safe Eval Profile — 2026-04-12

## Purpose

Create a workstation-only derived variant of the 400-query production eval corpus without editing the canonical source file.

- Canonical source: `tests/golden_eval/production_queries_400_2026-04-12.json`
- Derived profile: `tests/golden_eval/profiles/workstation_safe/production_queries_400_workstation_safe_2026-04-12.json`
- Validation report: `tests/golden_eval/profiles/workstation_safe/workstation_safe_eval_validation_2026-04-12.json`

This profile is not the canonical corpus. It exists so workstation-side eval runs can avoid banned program-specific tokens in workstation-facing narrative fields while keeping the canonical corpus intact.

## Rewritten Token Policy

The generator rewrites only workstation-facing narrative fields:

- `user_input`
- `reference`
- `rationale`
- `corpus_grounding_evidence`

Program-specific tokens are rewritten with the same intent as the repo sanitizer:

- `IGS` -> `enterprise program`
- `ISTO` -> `legacy monitoring system`
- `NEXION` -> `monitoring system`
- paired forms such as `IGS/NEXION` are rewritten before single-token fallthrough rules

## What Remains Intentionally Unchanged

The generator preserves exact machine-grounding fields:

- `reference_contexts`
- `expected_source_patterns`
- `expected_anchor_entities`
- all other non-narrative eval metadata

Reason: these fields still need to line up with the live corpus and current eval tooling. Rewriting exact source-path strings or filename patterns would make the profile safer-looking but less faithful to the retrieval contract.

Identifiers that are supposed to remain intact are also preserved:

- `IGSI-*`
- `IGSCC-*`

## Current Derived Profile Result

Generated on 2026-04-12 from the live canonical 400-query file:

- `400` total queries
- `37` queries changed
- `47` narrative fields rewritten
- `0` disallowed banned-token hits remaining in sanitized fields
- `126` allowed residual hits retained in preserved machine-grounding fields

Residual exact-path hits are currently confined to:

- `reference_contexts`: `97`
- `expected_source_patterns`: `29`

That is expected. The validation report records those residuals explicitly so they are visible rather than silently ignored.

## Generation Command

From `C:\HybridRAG_V2`:

```powershell
python .\scripts\generate_workstation_safe_eval.py
```

Explicit paths:

```powershell
python .\scripts\generate_workstation_safe_eval.py `
  --canonical .\tests\golden_eval\production_queries_400_2026-04-12.json `
  --output-json .\tests\golden_eval\profiles\workstation_safe\production_queries_400_workstation_safe_2026-04-12.json `
  --validation-json .\tests\golden_eval\profiles\workstation_safe\workstation_safe_eval_validation_2026-04-12.json
```

## Validation Command

Validate the already-generated derived profile without regenerating it:

```powershell
python .\scripts\generate_workstation_safe_eval.py `
  --canonical .\tests\golden_eval\production_queries_400_2026-04-12.json `
  --validate-only `
  --input-json .\tests\golden_eval\profiles\workstation_safe\production_queries_400_workstation_safe_2026-04-12.json `
  --validation-json .\tests\golden_eval\profiles\workstation_safe\workstation_safe_eval_validation_2026-04-12.json
```

Passing validation means:

- no disallowed `IGS` / `ISTO` / `NEXION` tokens remain in sanitized narrative fields
- any remaining exact-token hits are confined to preserved machine-grounding fields and are listed in the report

## Warning

The derived profile must never overwrite the canonical corpus.

- The generator reads the canonical file and writes to `tests/golden_eval/profiles/workstation_safe/`
- `scripts/generate_workstation_safe_eval.py` refuses to use the canonical file as its output path
- If the canonical corpus needs real content changes, update the canonical file directly in its own lane, then regenerate the workstation-safe profile
