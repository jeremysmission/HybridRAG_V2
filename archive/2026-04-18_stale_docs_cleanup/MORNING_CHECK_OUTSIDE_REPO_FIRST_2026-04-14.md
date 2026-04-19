# Morning Check Outside Repo First - 2026-04-14

If the machine survives the night, check the outside-repo location first:

```text
C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\
```

Before drilling into any individual run folder, open this file first:

```text
C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\README_HYBRIDRAG_LOCAL_ONLY_2026-04-14.md
```

It is the contract for what the outside-repo root is for, what belongs there,
and what must stay out of the canonical repos.

## Most likely folders to inspect first

### 1. Master overnight run

```text
C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01\
```

First files to open there:

1. `00_meta\MORNING_REVIEW_INDEX_2026-04-14.md`
2. `04_final_summary\MORNING_HANDBACK_claude_master_2026-04-14.md`
3. `04_final_summary\OVERNIGHT_FINAL_EVIDENCE_claude_master_2026-04-14.md`
4. `01_hardtail_extraction\EXTRACTION_COMPARE_SUMMARY_hardtail_50.md`
5. `03_regex_mining\REGEX_PRIORITY_RECOMMENDATIONS_2026-04-14.md`

### 2. Hardtail stress test

```text
C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_02_hardtail\
```

Check this if the focused stress-test lane produced more usable results than the master lane.

### 3. Completed round-1 Claude bakeoff

```text
C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_01\
```

This already contains the completed first bakeoff and usage capture.

## Quick open commands

```powershell
code C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY
code C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\overnight_autonomous_runs\2026-04-14_master_01
code C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\provider_dev_bakeoffs\2026-04-14_claude_bakeoff_02_hardtail
```

## Reminder

- These are development-only artifacts.
- They are intentionally outside the repo.
- Do not push them.
- Use the repo only for pointer docs and curated summaries.
- If any repo-visible summary is selected for remote push later, sanitize only that curated repo subset as a pre-push step.
- Do not run broad sanitizer apply against the local working tree or the outside-repo bakeoff folders.
