# Cross-Repo Real Hardware Pre-Flight Checklist

**Date:** 2026-04-16
**Reviewer:** CoPilot+ (QA)
**Repos:** Ionogram_Quality_Tracker, Career Moves, HybridRAG V2
**Context:** QA agent added stop button, info button, cert export fix, guide updates
**Code-level verdict:** PASS (P1 column collision found and fixed)
**Remaining:** Real hardware verification below

---

## IQT GUI -- Button Bar (3 min)

```
Launch: Launch_IQT_GUI.bat
```

- [ ] **Visual:** 4 buttons in a row -- Run Command, Stop, Copy Output, Open Last Output -- no overlap, no stacking
- [ ] **Stop at rest:** grayed out / disabled
- [ ] **Run a fetch** (pick a short date range like 1 day): Stop button enables, output streams
- [ ] **Click Stop mid-fetch:** output shows `[Stopped by operator]`, status says "Stopping command...", GUI returns to ready
- [ ] **After stop:** Stop disables, Run re-enables, Copy Output still works
- [ ] **Double-click Stop rapidly:** no crash, no traceback in console
- [ ] **Run completes normally:** Stop disables on its own, Open Last Output enables

## IQT GUI -- Info Button (1 min)

- [ ] **Info button visible** in top-right header area
- [ ] **Click Info:** Word opens `docs/IQT_GUI_User_Guide.docx`
- [ ] **Skim DOCX:** cover page, "Your First 5 Minutes", troubleshooting, glossary, APA refs present

## IQT -- Cert Export (2 min)

```powershell
# From non-elevated PowerShell with proxy set:
$env:HTTPS_PROXY = "http://your-proxy:port"
.\Install_Ionogram_Quality_Tracker.ps1
```

- [ ] Console prints `Auto-exported Windows CA bundle:`
- [ ] `.venv\ca-bundle.pem` exists and is >10KB
- [ ] `.venv\pip.ini` has both `proxy =` and `cert =` lines

## Career Moves -- Cert Export (1 min)

```powershell
$env:HTTPS_PROXY = "http://your-proxy:port"
.\Setup_Career_Moves.bat
```

- [ ] `.venv\ca-bundle.pem` exists
- [ ] `.venv\pip.ini` has `proxy =` and `cert =`

## Career Moves -- User Guide (1 min)

- [ ] Open `docs/DOCX/User_Guides/Career_Moves_GUI_User_Guide.docx` in Word
- [ ] Formatting: Calibri 11pt body, Navy accent headings, all 7 tabs documented

## V2 -- Guide Regeneration (2 min)

```
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\build_user_guides.py
```

- [ ] Both `docs/QA_WORKBENCH_USER_GUIDE_V2.docx` and `docs/EVAL_GUI_USER_GUIDE_V2.docx` regenerate without error
- [ ] Open each: "Your First 5 Minutes" section present, Eval GUI is self-contained (not "see QA Workbench")
- [ ] APA references with dates at end of each

---

## Verdict

If all boxes check, post `Passed QA` on the board.
If the Stop button or Info button misbehaves under real clicks, post `Return to Coder for` with exact repro.

---

## Code Review Findings (completed)

| # | Item | Verdict | Notes |
|---|------|---------|-------|
| 1 | CA cert export (IQT) | PASS | X509Store .NET API correct, proper Close(), retry after venv |
| 2 | Stop button (IQT) | PASS | Logic sound, column collision fixed (col 2 -> col 3) |
| 3 | Info button (IQT) | PASS | Windows guard, existence check, fallback warning correct |
| 4 | CA cert export (Career Moves) | PASS | Identical fix to IQT, verified |
| 5 | V2 guide builder | PASS | Compiles, STAGE_DIR correct, First 5 Minutes + APA refs confirmed |
| 6 | V2 button smash harness Tier D | PASS | Generates checklist with proxy section P1-P5 |

## P1 Bug Found and Fixed

**gui_layout.py:291** -- Copy Output and Open Last Output both gridded at column=2.
Fixed to column=3. Button bar now: Run(0), Stop(1), Copy(2), Open(3).

Signed: CoPilot+ (QA) | HybridRAG_V2 | 2026-04-16 | 01:30 MDT
