# QA Workbench -- QA-Ready Checklist

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-17 MDT
**Target:** `src.gui.qa_workbench` via `start_qa_workbench.bat`
**Expectations doc:** `docs/QA_EXPECTATIONS_2026-04-05.md`
**GUI harness doc:** `docs/QA_GUI_HARNESS_2026-04-05.md`

---

## Pre-flight state (already proven, do not re-prove)

- `start_qa_workbench.bat --dry-run --debug-env` -- PASS (re-verified 2026-04-17)
- `pytest -q tests/test_qa_workbench.py` -- 20 passed, 1 skipped (re-verified 2026-04-17)
- Headless `tk.Tk()` smoke + assembled shell -- PASS (2026-04-15 run note)
- End-to-end runner proofs on real stores (2026-04-15 smoke runner):
  - aggregation self-check: 12/12
  - count benchmark frozen exact: 7/7
  - regression fixture: 50/50
- Cross-repo code review: PASS (2026-04-16 preflight checklist)
- Overview panel wired into QA Workbench shell (fix-forward 2026-04-15)

**The remaining gap the QA pass must close is human-eyes acceptance and real-run repeatability.**

---

## Tester pre-flight (2 min)

Before launching the GUI:

- [ ] Confirm no leftover eval GUI processes. `tasklist | findstr /I pythonw` -- if a `pythonw.exe` is sitting on >100 MB and you are not running anything, note its PID and flag before killing.
- [ ] Stale capture files at repo root are cosmetic clutter, not blockers. If you choose to move them aside, move -- do not delete:
  - `tmp_eval_gui_*.txt`
  - `eval_gui_overwrite_p6mxqkgg/`
  - `hybridrag_eval_gui_stop_*/`
  - `tmp_gpu1_diag/`
- [ ] `nvidia-smi` shows one workstation GPU free enough to load an embedder (< 4 GB in use on GPU 0).
- [ ] Proxy / cert env not set in this shell (workstation default). If you need online, set before launch.

---

## Environment snapshot (copy into report)

```
Python:                    [.venv\Scripts\python.exe --version]
torch / CUDA / GPU:        [python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"]
CUDA_VISIBLE_DEVICES:      0
venv:                      existing
Launcher dry-run:          PASS / FAIL
Headless pytest:           [N] passed, [N] skipped
```

---

## Pillar 1: Boot & Config (5 min)

- [ ] Double-click `start_qa_workbench.bat`. Window paints inside 10 seconds. No traceback in the console.
- [ ] Tab order top to bottom, left to right: **Overview -> Baseline -> Aggregation -> Count -> Regression -> History / Ledger**.
- [ ] Baseline nested notebook exposes: **Launch / Results / Compare / History**.
- [ ] Overview tab is the default on startup.
- [ ] Click **Refresh** on Overview -- sections populate with real numbers (baseline QA status, hardtail table, count / aggregation status, regression pass / partial / miss).
- [ ] Close with the window **X**. Process exits cleanly, no zombie `pythonw`.

## Pillar 2: Core Pipeline via Baseline Launch tab (10 min)

Runs 5 queries to exercise the real runner without burning 30+ minutes.

- [ ] Baseline -> Launch. Confirm default fields load (query pack, config, CUDA=0).
- [ ] Set **Max queries = 5**.
- [ ] Press **Start**. Phase label cycles: BOOT -> LOAD_EMBEDDER -> LOAD_STORE -> QUERY_LOOP -> done (PASS).
- [ ] Two output files appear in `docs/`: `PRODUCTION_EVAL_RESULTS_GUI_*.md` and `production_eval_results_gui_*.json`.
- [ ] Results tab **Load Results** -> Run Info strip shows pack, config, store path, GPU, timestamp, run_id.
- [ ] Compare tab: load same JSON twice as baseline + candidate. Delta row is all zeros, all green.
- [ ] History tab: new run appears, sortable columns work.

## Pillar 3: 3-Tier Behavior (via assembled-shell lanes, 10 min)

- [ ] Aggregation tab: start the frozen self-check (12 items). Expect 12/12 PASS inside the shell summary.
- [ ] Count tab: start the frozen exact target set. Expect 7/7. Artifact .md + .json persist under `tests/smoke_results/`.
- [ ] Regression tab: start the frozen fixture. Expect 50/50.
- [ ] Negative smoke: point the Aggregation lane at a non-existent manifest path -> rejected with a human-readable error, no traceback.
- [ ] Negative smoke: submit the Count lane with zero-mode selection -> rejected with a human-readable error.
- [ ] Negative smoke: submit the Regression lane with an invalid fixture path -> rejected with a human-readable error.

## Pillar 4: Real Data Pass (defer unless prod corpus is mounted)

- [ ] If and only if a real 50-100 file subset is available locally: run the Launch tab full, no max-cap, verify GPU peak < 20 GB, answers reference real content.
- [ ] Otherwise mark **SKIPPED -- no prod corpus local**. Do not skip silently.

## Pillar 5: Graceful Degradation (5 min)

- [ ] Click **Stop** mid-run on the Baseline Launch tab. Current query finishes, phase settles on `done (STOPPED)`. No orphan threads.
- [ ] Close the window during an active Baseline run. Runner stop path fires, process exits, no zombie.
- [ ] Unset API key, try Baseline Launch again: service returns a clean 503-style error surface or the run refuses to start with a readable message.
- [ ] Point Launch at an empty `lance_db` path: phase settles in LOAD_STORE with a "No data loaded" message, no crash.

---

## GUI Tier A / B / C / D (20 min, per `QA_GUI_HARNESS_2026-04-05.md`)

### Tier A -- scripted functional
- [ ] `pytest -q tests/test_qa_workbench.py` -- 20 passed, 1 skipped

### Tier B -- smart monkey (targeted chaos, 5 min)
- [ ] Rapid-click Start on Baseline Launch 10x inside 2 seconds -> single run fires, rest no-op.
- [ ] Tab-switch Overview <-> Baseline <-> Aggregation 30 times inside 5 seconds during an active Baseline run -> no desync, no uninitialized widgets, status bar consistent.
- [ ] Resize window to 800x600 and back to full during a streaming run -> no overlap, no crash.

### Tier C -- dumb monkey (random chaos, 60 s)
- [ ] Random click + type + resize for 60 seconds. Record any crash, freeze > 3 s, or unhandled traceback. Target: zero of each.

### Tier D -- human button smash (10 min, non-author)
- [ ] 10 full minutes of a non-developer trying to break it. Report crashes, freezes, visual glitches, data issues.

---

## QA Report (copy and fill in)

```
# QA Workbench QA Report
Date: 2026-04-17
Tester: [name]
Hardware: Beast (workstation GPU 0) / work single-CUDA / laptop
API: commercial / Azure / none
Launcher dry-run: PASS / FAIL
Headless pytest: [N] passed, [N] skipped

## Pillar 1 Boot & Config
- [ ] Launcher paints inside 10 s
- [ ] Tab order correct
- [ ] Overview populates with real numbers
- [ ] Clean close

## Pillar 2 Core Pipeline (5-query Baseline Launch)
- [ ] Phase labels cycle to done (PASS)
- [ ] Two artifacts written to docs/
- [ ] Results / Compare / History tabs consume the new JSON cleanly

## Pillar 3 3-Tier Lanes
- [ ] Aggregation 12/12
- [ ] Count 7/7
- [ ] Regression 50/50
- [ ] Three negative misuse paths rejected cleanly

## Pillar 4 Real Data
- [ ] Ran against prod subset: [details]  OR
- [ ] SKIPPED -- no local corpus (noted as gap)

## Pillar 5 Graceful Degradation
- [ ] Stop mid-run clean
- [ ] Close mid-run clean
- [ ] Missing API key clean
- [ ] Empty store clean

## GUI Tier A/B/C/D
- [ ] Tier A: 20 passed, 1 skipped
- [ ] Tier B smart monkey: [X] crashes, [X] freezes
- [ ] Tier C dumb monkey 60 s: [X] crashes, [X] freezes
- [ ] Tier D human 10 min: [summary]

## Issues Found
1. [severity, repro, file:line if known]

## Verdict
- [ ] PASS -- QA Workbench ready for operator repeat use
- [ ] CONDITIONAL -- [items]
- [ ] FAIL -- [blocking items]

Signed: [name] | HybridRAG_V2 | 2026-04-17 MDT
```

---

## What QA should NOT retest (already green, don't burn time)

- Headless `tk.Tk()` instantiation of `QAWorkbench()`
- Assembled-shell tab-order assertion
- Per-panel completion-state rendering from the pytest suite
- `py_compile` on the three wiring files
- Cross-repo code review items (IQT buttons, cert export, builder compile)

Re-run these only if a code change lands between now and the QA session.

---

## Known follow-ups (out of scope for this QA)

- Proxy-hardening parity between `start_qa_workbench.bat` and `start_eval_gui.bat` (tracked in `GUI_RUNTIME_PROXY_HARDENING_NOTE_2026-04-15.md`)
- Claim-level precision / recall in Overview strongest / weakest (needs schema extension)
- Aggregation / Count live-run widgets inside Overview (explicitly deferred to owning panels)

---

Signed: Jeremy Randall (CoPilot+) | HybridRAG_V2 | 2026-04-17 MDT
