# Lane 9.2 Tier D Human Button Smash Plan 2026-04-11

## Purpose

This is the manual Tier D test plan for Lane 9.2 only.

- It is a human test plan and acceptance checklist, not a test result.
- It must be run by a person who did not author the Lane 9.2 changes.
- It is intended to take under 15 minutes.
- It does not replace the automated evidence packet in `docs/LANE9_2_EVIDENCE_PACKET_2026-04-11.md`.

## Automated vs Human Coverage

The automated harness in `docs/LANE9_2_EVIDENCE_PACKET_2026-04-11.md` already covers:

- launch path resolves `config/config.yaml`
- nav surface is limited to `Query`, `Entities`, and `Settings`
- Settings is read-only
- Settings renders the expected runtime values
- the single-config guidance contract exists at source level
- `Refresh Counts` updates the runtime counts label

This human Tier D test covers the operator interaction surface the automated harness deliberately skips:

- real GUI launch from the supported operator entrypoint
- visible tab switching and panel rendering
- visible Settings values matching the expected `config/config.yaml` baseline
- absence of edit/save controls in the live GUI
- manual `Refresh Counts` behavior under normal clicking and rapid clicking
- resize, close, reopen, and no-error operator flow

## Preconditions

- **Do NOT be the author of Lane 9.2 changes.**
- Repo location: `C:\HybridRAG_V2`
- Preferred launch path: `C:\HybridRAG_V2\start_gui.bat --terminal`
- Manual equivalent if needed:
  - `cd C:\HybridRAG_V2`
  - `.venv\Scripts\activate`
  - `python -m src.gui.launch_gui`
- Environment variables:
  - none are required for the Lane 9.2 checks below
  - if LLM credentials are missing, that is not a failure for this plan unless the GUI crashes or becomes misleading
- Starting state:
  - no other HybridRAG V2 GUI window is already open
  - `config\config.yaml` exists and has not been intentionally changed since the automated evidence packet was captured
  - do not edit `config\config.yaml` during this test
- Result file to create after the test:
  - `C:\HybridRAG_V2\docs\evidence\lane9_2_gui_20260411_205000\tier_d_human_result.md`

## Known Config Baseline

The current GUI does not render a literal `Config file: config/config.yaml` label.

For this human test, treat the single-runtime-config check as:

- the visible Settings values must match the current `config\config.yaml` baseline below
- no alternate config name such as `config.local.yaml` should appear anywhere in the GUI or launch console during the test

Expected baseline values:

| Area | Expected visible value |
|---|---|
| Retrieval | `Top-K: 10` |
| Retrieval | `Candidate Pool: 30` |
| Retrieval | `Min Score: 0.1` |
| LLM Configuration | `Model: gpt-4o` |
| LLM Configuration | `Provider: auto` |
| File Paths | `LanceDB: C:\HybridRAG_V2\data\index\lancedb` |
| File Paths | `Entity DB: C:\HybridRAG_V2\data\index\entities.sqlite3` |
| File Paths | `Corpus Source: C:\HybridRAG_V2\data\source` |
| File Paths | `Site Vocabulary: C:\HybridRAG_V2\config\site_vocabulary.yaml` |
| Hardware | `Preset: primary workstation` |

## Numbered Test Steps

1. Launch the GUI from `C:\HybridRAG_V2\start_gui.bat --terminal`.
Expected outcome:
The GUI window opens without a crash. The terminal should show normal startup messages and should not mention `config.local.yaml`.

2. Confirm the visible navigation surface.
Expected outcome:
The top-level tabs are exactly `Query`, `Entities`, and `Settings`. No extra operator tab such as `Index`, `Modes`, or `Profiles` is present.

3. Click `Query`, then `Entities`, then `Settings`, then repeat that cycle one more time.
Expected outcome:
Each tab opens cleanly. No blank panel, traceback, popup error, or frozen window appears during the tab switches.

4. In `Settings`, compare the visible values against the known config baseline above.
Expected outcome:
The Settings panel shows the expected baseline values from `config\config.yaml`, including `gpt-4o`, `auto`, `Top-K: 10`, `Candidate Pool: 30`, `Min Score: 0.1`, the `lancedb` path, the `entities.sqlite3` path, the `data\source` path, and `Preset: primary workstation`.

5. Confirm the single-config operator surface.
Expected outcome:
No alternate config filename such as `config.local.yaml` appears anywhere in the GUI or terminal. There is no mode selector, profile picker, or multi-config chooser visible to the operator.

6. Confirm the Settings panel is read-only.
Expected outcome:
There is no `Save`, `Apply`, or `Reset` button. There are no editable text boxes, checkboxes, spinboxes, or toggles in the Settings panel. The only operator action in that panel is `Refresh Counts`.

7. Click `Refresh Counts` once.
Expected outcome:
The counts label updates to a concrete runtime string in this format: `Chunks: <number> | Entities: <number> | Rels: <number>`. The numbers do not need to match the automated packet exactly, but the label must populate and remain well-formed.

8. Click `Refresh Counts` five times in rapid succession.
Expected outcome:
The GUI stays responsive. No duplicate dialogs, crash, freeze, or malformed counts label appears. The final counts label is still readable and in the same `Chunks / Entities / Rels` format.

9. Resize the window very small, then maximize it, then return it to a normal size.
Expected outcome:
The GUI remains usable. Text may wrap or scroll, but tabs and the `Refresh Counts` control remain accessible and the window does not freeze.

10. Close the GUI, relaunch it once, go back to `Settings`, and repeat steps 2, 4, and 7 in a quick spot-check.
Expected outcome:
The app closes cleanly and relaunches cleanly. The same three tabs are present, the Settings values still match the expected baseline, and `Refresh Counts` still populates the counts label.

## Failure Modes

If any step fails:

1. Record the exact failed step number.
2. Take a screenshot of the failure.
3. Save the screenshot in `C:\HybridRAG_V2\docs\evidence\lane9_2_gui_20260411_205000\` using a name like `tier_d_fail_step_04.png`.
4. If the app crashed or froze, stop the run and mark the result `FAIL`.
5. File the result back to the coordinator with these paths:
   `docs/LANE9_2_EVIDENCE_PACKET_2026-04-11.md`
   `docs/LANE9_2_TIER_D_HUMAN_BUTTON_SMASH_PLAN_2026-04-11.md`
   `docs/evidence/lane9_2_gui_20260411_205000/tier_d_human_result.md`

## Success Criteria

Lane 9.2 Tier D human testing is complete only when all of the following are true:

- all numbered steps above pass
- the tester is not the author of Lane 9.2
- tester name and date/time are filled in
- the result is written to `docs/evidence/lane9_2_gui_20260411_205000/tier_d_human_result.md`
- any failures include screenshots and failed step numbers

This document does not mark Lane 9.2 fully signed off by itself. Full signoff remains open until a non-author tester actually runs this plan and records the result.

## Result Recording Template

Save the filled result as:

`C:\HybridRAG_V2\docs\evidence\lane9_2_gui_20260411_205000\tier_d_human_result.md`

Use this template:

```md
Tester: [name]
Date/time: [YYYY-MM-DD HH:MM MDT]
Duration: [minutes]
Result: PASS / FAIL
Failed steps: [list]
Notes: [free text]

Automated packet reviewed:
- docs/LANE9_2_EVIDENCE_PACKET_2026-04-11.md

Screenshots:
- [list screenshot filenames, or "none"]
```
