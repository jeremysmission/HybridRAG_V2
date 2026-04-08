# QA1 Trivial-Only Acceptance Matrix (2026-03-21)

Purpose
- Provide a reusable QA1 acceptance pack for `S4-R No-claim grounding and transparency truth`.
- Cover the operator-visible cases where a low-information, courtesy, or scope-free query should not hard-block.
- Keep the acceptance target tied to the current known regressions on `3ffb0db` without over-constraining the final implementation.

Why this pack exists
- Current planning and audit notes already confirm that trivial-only / no-claim paths can hard-block instead of staying unscored:
  - `docs/09_project_mgmt/SPRINT_2026-03-18_REAL_WORLD_CHECKS.md`
  - `{USER_HOME}\.tool_handoff\teams\hybridrag3_educational\extqa1_2026-03-21_1452_mdt_COMPLETE_batch_6_audits_E1_1_4_5_6_7_9.md`
  - `{USER_HOME}\.tool_handoff\teams\hybridrag3_educational\qa3_2026-03-21_1510_mdt_COMPLETE_release_gate_rerun_plus_3_deep_audits.md`
- Minimum confirmed current-head repro from the planning notes: `Thanks`
- Shared-handoff repros from QA3: `Hello there`, `Overview`

Acceptance rules
- PASS if the reply is non-empty and stays operator-honest:
  - no hard block/refusal text such as `I found relevant documents but cannot provide a fully verified answer...`
  - no `INSUFFICIENT SOURCE DATA`
  - no misleading green `verified` cue for a low-information reply
  - acceptable outcomes are:
    - a short acknowledgement
    - a clarification request
    - a low-information guidance reply
    - an unscored or warning-only cue
- FAIL if the system:
  - hard-blocks solely because there were zero verifiable claims
  - labels the result as source-verified when it is really low-information
  - shows red blocked/refusal behavior for a simple courtesy or clarification query

Preferred backend truth after the S4-R fix
- `grounding_blocked = false`
- `verifiable_claims = 0` is acceptable
- `grounding_score = -1.0` or another explicit unscored representation is acceptable
- any transparency mode must not imply source-backed verification for these cases

Suggested evidence capture
- exact prompt
- answer text
- visible grounding/transparency banner text
- visible banner color/severity
- `grounding_score`
- `grounding_blocked`
- `transparency_mode`
- `transparency_notice`

## Matrix

| ID | Exact prompt | Intent class | Current status on `3ffb0db` | PASS outcome after `S4-R` |
|----|--------------|--------------|------------------------------|---------------------------|
| T1 | `Thanks` | Courtesy acknowledgement | Confirmed minimum repro in sprint notes | Short acknowledgement or low-information reply; unscored/non-blocking; never hard-blocked |
| T2 | `Hello there` | Greeting | Confirmed repro in shared QA notes | Short greeting or clarification; unscored/non-blocking; never hard-blocked |
| T3 | `Overview` | One-word fragment / no subject | Confirmed repro in shared QA notes | Clarification request or brief guidance; unscored/non-blocking; never hard-blocked |
| T4 | `Continue` | Transition fragment | Coverage extension | Clarification or continuation guidance; unscored/non-blocking; never hard-blocked |
| T5 | `Okay` | Short acknowledgement | Coverage extension | Short acknowledgement; unscored/non-blocking; never hard-blocked |
| T6 | `Please summarize.` | Scope-free request | Coverage extension | Ask what to summarize or give short guidance; unscored or warning-only; never hard-blocked |
| T7 | `Can you help?` | Capability / clarification request | Coverage extension | Brief help/clarification prompt; unscored or warning-only; never hard-blocked |
| T8 | `What should I ask next?` | Meta-guidance request | Coverage extension | Short safe-guidance reply; unscored or warning-only; never hard-blocked |
| T9 | `Where should I start?` | Operator uncertainty | Coverage extension | Brief next-step guidance; unscored or warning-only; never hard-blocked |
| T10 | `Quick overview?` | Low-context summary request | Coverage extension | Clarification request or generic safe overview guidance; unscored or warning-only; never hard-blocked |

Validation spot-check
- Echo-path verifier run on `2026-03-21 17:21 MDT` against `ClaimExtractor.extract_claims(...)` plus `_gqe_fallback_score(...)`
- Result:
  - `T1`, `T2`, `T3`, `T4`, `T6`, `T7`, `T8`, `T9`, `T10` all map to `verifiable_claims=0` and `score=-1.0` if echoed back literally
  - `T5` (`Okay`) produces zero extracted claims, which is still valid no-claim coverage for this pack

## Rerun guidance

Desktop acceptance
- Run the prompts from `Eval/qa1_trivial_only_queries_2026-03-21.txt`
- Capture the visible answer and status banners for each
- Mark the tranche FAIL immediately if any prompt hard-blocks

Browser/API follow-on
- Reuse the same prompt list after the coder patch lands if the same guard logic is surfaced through `/query` or `/query/stream`
- Do not require citations for these low-information prompts; the acceptance target is truthful non-blocking behavior, not retrieval depth

Release implication
- This pack is a gating subset of `S4-R`.
- QA1 overall repo verdict cannot move to `PASS` while the confirmed trivial-only hard-block behavior remains.
