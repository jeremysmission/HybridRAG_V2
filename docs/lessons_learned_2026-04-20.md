# Lessons Learned — 2026-04-20

**Scope:** local-only retrospective after the merged v3 push

## 1. Multi-agent triangulation beats single-thread certainty

- Cross-model review caught bugs that a single lane missed.
- The strongest pattern today was:
  1. one lane reports
  2. another lane challenges
  3. push owner verifies live
- This should be preserved as a repeatable operating pattern, not treated as incidental.

## 2. Behavioral fatigue signals matter more than self-report alone

- Cosmetic xfail suggestions
- number-chasing without contract checking
- queue-management posts without artifacts
- overconfident ETA language

Those were more reliable than “I’m fine” style self-assessment.

## 3. Live-test > grep > hypothesis

- When investigators disagreed, the fastest resolution was:
  - run the live CLI / pipeline
  - inspect grep/static clues only second
  - avoid broad theory until runtime evidence exists

This was especially important on:
- G3 adversarial path verification
- sanitize workflow diagnosis
- merge-tree route verification

## 4. Dispatch ETA estimates were consistently too optimistic

- Even after aggressive division, ETA language still anchored expectations badly.
- Better rule:
  - dispatch scope
  - state dependency
  - omit time estimates unless they are operationally critical

## 5. Sanitizer process was the day’s push fragility

- The standing rule was correct.
- The code implementation was not.
- The push succeeded only because the runbook was paused and re-derived live.

## Candidate memory-worthy rules

- Never run in-place sanitize on the active working tree.
- Push-gate scripts must encode policy, not rely on tribal memory.
- If Scan 1/3/4 are clean and Scan 2 only shows historical archive/tool-config/business-title hits, document judgment and proceed instead of reopening the whole tree.
