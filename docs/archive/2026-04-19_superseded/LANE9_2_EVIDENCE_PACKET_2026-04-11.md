# Lane 9.2 Evidence Packet 2026-04-11

## Scope

Lane 9.2 runtime config simplification and operator-clarity evidence for:

- `src/gui/app.py`
- `src/gui/panels/settings_panel.py`
- `src/gui/launch_gui.py`
- `tools/gui_evidence_capture.py`

**Explicit note:** "This is targeted evidence for Lane 9.2 scope only. A full Tier D human button smash by a non-author is still required before full signoff — this packet does NOT replace that, but provides the coded evidence QA can verify."

## Checks Run

The targeted capture script exercises only the Lane 9.2 surface:

1. `launch_gui_config_path`
   Confirms `src/gui/launch_gui.py` resolves the live runtime config from `C:\HybridRAG_V2\config\config.yaml`.
2. `simplified_nav_surface`
   Confirms the visible navigation surface is limited to `Query`, `Entities`, and `Settings`.
3. `settings_panel_read_only`
   Confirms the Settings panel contains no editable `Entry`, `Text`, `Spinbox`, `Checkbutton`, or `Radiobutton` widgets.
4. `settings_panel_runtime_config_display`
   Confirms the rendered Settings panel shows the active model, `LanceDB` path, `Corpus Source` path, and the `Refresh Counts` control.
5. `settings_guidance_source_contract`
   Confirms the `SettingsPanel` implementation still carries the Lane 9.2 single-runtime-config guidance phrase `config/config.yaml and restarting.` as a source-level contract. This is not a rendered widget-text check.
6. `refresh_counts_runtime_status`
   Confirms `Refresh Counts` updates the runtime count label end-to-end.

## Commands

```powershell
cd C:\HybridRAG_V2
python -m py_compile tools\gui_evidence_capture.py
python tools\gui_evidence_capture.py --output-dir C:\HybridRAG_V2\docs\evidence\lane9_2_gui_20260411_205000
```

## Results

### Verdict

- `PASS`

### Evidence JSON

- `C:\HybridRAG_V2\docs\evidence\lane9_2_gui_20260411_205000\gui_evidence_20260411_204337.json`

### Snapshot Artifacts

- `C:\HybridRAG_V2\docs\evidence\lane9_2_gui_20260411_205000\settings_before_refresh.txt`
- `C:\HybridRAG_V2\docs\evidence\lane9_2_gui_20260411_205000\settings_after_refresh.txt`

### Pass Matrix

| Check | Result | Evidence |
|---|---|---|
| `launch_gui_config_path` | PASS | JSON details show captured path equals `C:\HybridRAG_V2\config\config.yaml` |
| `simplified_nav_surface` | PASS | JSON details show `["Query", "Entities", "Settings"]` |
| `settings_panel_read_only` | PASS | JSON details show no interactive editor widgets found |
| `settings_panel_runtime_config_display` | PASS | JSON details show rendered `gpt-4o`, `LanceDB`, corpus source, and `Refresh Counts` |
| `settings_guidance_source_contract` | PASS | JSON details show the required `config/config.yaml and restarting.` phrase is present in the `SettingsPanel` source contract, with `rendered_guidance_present: false`; this is not a rendered-GUI proof |
| `refresh_counts_runtime_status` | PASS | After snapshot shows `Chunks: 12,345 | Entities: 678 | Rels: 90` |

## Boundaries

- This packet is intentionally narrow. It proves the Lane 9.2 GUI changes work in a code-driven pass without relying on the missing `src/gui/testing/` harness tree referenced by the GUI QA spec.
- The current Settings panel snapshots do not contain separate operator-visible restart/config guidance text. Check 5 is intentionally source-level only and should be read that way.
- This packet is not a replacement for full GUI QA tiers A-D.
- A Tier D human button smash by a non-author is still required before full signoff.
- If QA wants broader automated coverage later, `tools/gui_evidence_capture.py` is the repo-local starting point, not a claim that the full harness gap is closed.
