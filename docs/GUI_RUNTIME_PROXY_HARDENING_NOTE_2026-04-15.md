# GUI Runtime Proxy Hardening Note

Date: 2026-04-15
Scope: shared GUI runtime preflight for launcher wrappers
Status: runtime hardening landed

## What is hardened at runtime

The GUI launchers now share one repo-side PowerShell preflight:

- `scripts\gui_runtime_preflight_2026-04-15.ps1`

Current wrappers using it:

- `start_gui.bat`
- `start_eval_gui.bat`
- `RUN_IMPORT_AND_EXTRACT_GUI.bat`
- `start_qa_workbench.bat`

The shared runtime hardening covers:

- `PYTHONUTF8=1`
- `PYTHONIOENCODING=utf-8`
- loopback bypass merge into `NO_PROXY` / `no_proxy`
  - `localhost`
  - `127.0.0.1`
  - `::1`
- inherited proxy env pass-through
  - `HTTP_PROXY` / `http_proxy`
  - `HTTPS_PROXY` / `https_proxy`
  - `ALL_PROXY` / `all_proxy`
- operator-visible runtime state
  - proxy values
  - loopback bypass
  - cert-env presence
  - UTF-8 state
- dry-run / debug visibility in the launchers

## What is not claimed

This is not a full install-time self-healing system.

It does **not**:

- auto-discover the correct corporate proxy
- write persistent Windows environment variables
- repair broken certificates
- rewrite pip configuration
- guarantee model downloads succeed behind every proxy

Those remain install-time or workstation-configuration responsibilities.

## Install-grade vs runtime-grade

Install-grade concerns:

- creating `.venv`
- pip config / trusted hosts
- certificate bootstrap
- package downloads
- workstation-specific proxy persistence

Runtime-grade concerns handled here:

- keep Python UTF-8 safe
- preserve inherited proxy env
- keep loopback traffic off the proxy
- surface operator-visible proxy/debug state consistently
- make GUI wrappers behave the same way

## QA Workbench parity

`start_gui.bat`, `start_eval_gui.bat`, `RUN_IMPORT_AND_EXTRACT_GUI.bat`,
and `start_qa_workbench.bat` now use the same shared preflight path, so the
current GUI launcher set has one consistent runtime hardening surface instead
of split proxy/encoding setups.
