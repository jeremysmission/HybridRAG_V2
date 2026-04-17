# Operator Surface QA Report

**Date:** 2026-04-08 MDT
**Tester:** CoPilot+ QA
**Scope:** Mainline operator-facing experience across `C:\CorpusForge` and `C:\HybridRAG_V2`
**Repos / branches:** `C:\CorpusForge` on `master`; `C:\HybridRAG_V2` on `master`
**Venvs:** `C:\CorpusForge\.venv`; `C:\HybridRAG_V2\.venv`
**Hardware:** 2x NVIDIA GeForce RTX 3090
**GPU choice:** `CUDA_VISIBLE_DEVICES=0`
**GPU selection rationale:** At test start, GPU 0 was the lesser-used device (`12394 MiB / 24576 MiB`, `0%` util) and GPU 1 was saturated (`24270 MiB / 24576 MiB`, `100%` util).
**OCR prerequisites:** `where.exe tesseract` -> not found; `where.exe pdftoppm` -> not found

## Recommendation

**Final recommendation: not signoff-ready.**

The two highest-risk demo problems are launch-path/documentation mismatches and misleading Stop behavior. An operator following the current docs can launch the wrong thing, and an operator clicking Stop in either GUI can be told the action was cancelled while work continues in the background.

## Findings

### 1. High — CorpusForge quickstart documents the wrong GUI launch command

- File: `C:\CorpusForge\archive\2026-04-17\docs\setup\OPERATOR_QUICKSTART.md:51`
- File: `C:\CorpusForge\scripts\boot.py:18`
- The quickstart tells operators to launch the GUI with `python scripts/boot.py`.
- Observed behavior: that command prints a boot summary and exits. It does not open the GUI.
- This is a direct operator failure on the documented path.

### 2. High — HybridRAG V2 operator guide describes a server-backed start flow that the shipped start script does not perform

- File: `C:\HybridRAG_V2\docs\setup\OPERATOR_GUIDE_2026-04-05.md:24`
- File: `C:\HybridRAG_V2\docs\setup\OPERATOR_GUIDE_2026-04-05.md:48`
- File: `C:\HybridRAG_V2\docs\setup\OPERATOR_GUIDE_2026-04-05.md:52`
- File: `C:\HybridRAG_V2\start_gui.bat:92`
- File: `C:\HybridRAG_V2\src\gui\launch_gui.py:76`
- File: `C:\HybridRAG_V2\src\gui\panels\status_bar.py:20`
- The guide says the system needs both server and GUI, says the status bar shows server connection, and says the start script launches both automatically.
- Observed behavior: `start_gui.bat` launches only the local GUI path. After launch, `curl http://127.0.0.1:8000/health` returns connection failure. The status bar code has no server-connectivity indicator at all.
- This is a live-demo risk because operator recovery steps are based on an architecture the shipped GUI does not use.

### 3. High — Stop is misleading in both GUIs; the UI says work is cancelled while the underlying job keeps running

- CorpusForge files:
  - `C:\CorpusForge\src\gui\app.py:393`
  - `C:\CorpusForge\src\gui\launch_gui.py:234`
  - `C:\CorpusForge\src\gui\launch_gui.py:310`
  - `C:\CorpusForge\src\gui\launch_gui.py:346`
- HybridRAG V2 files:
  - `C:\HybridRAG_V2\src\gui\panels\query_panel.py:279`
  - `C:\HybridRAG_V2\src\gui\panels\query_panel.py:287`
  - `C:\HybridRAG_V2\src\gui\model.py:155`
  - `C:\HybridRAG_V2\src\gui\model.py:181`
  - `C:\HybridRAG_V2\src\query\pipeline.py:59`
- CorpusForge live drill: Stop was requested `0.37s` after start; the pipeline still completed `2.3s` later.
- HybridRAG V2 live drill: Stop was requested `0.34s` after ask; the query panel immediately returned to idle and showed `Query cancelled.`, but background work still finished `2.16s` later.
- For a demo operator, this is the worst kind of control bug: the UI claims a state transition that did not actually occur.

### 4. Medium — Scanned-PDF failure handling is opaque when OCR prerequisites are missing

- File: `C:\CorpusForge\src\parse\parsers\pdf_parser.py:97`
- File: `C:\CorpusForge\src\parse\parsers\pdf_parser.py:121`
- File: `C:\CorpusForge\src\pipeline.py:703`
- Missing-PDF-OCR exceptions are swallowed into debug logging in `pdf_parser.py`, then surfaced to the operator as a generic `Empty parse result`.
- Live drill on an image-only PDF with both `tesseract` and `pdftoppm` absent produced:

```text
Empty parse result: {USER_HOME}\temp\cf_ocr_drill\ocr_probe.pdf
No chunks produced -- nothing to embed or export.
```

- No recovery guidance was shown about installing Tesseract or Poppler. On a real demo corpus, that looks like product failure instead of a prerequisite gap.

### 5. Medium — HybridRAG V2 startup logs are internally contradictory when the LLM is unavailable

- File: `C:\HybridRAG_V2\src\llm\client.py:105`
- File: `C:\HybridRAG_V2\src\gui\launch_gui.py:156`
- File: `C:\HybridRAG_V2\src\gui\launch_gui.py:183`
- File: `C:\HybridRAG_V2\src\gui\launch_gui.py:218`
- With API credentials removed, the live startup log showed:

```text
No API key found -- LLM client unavailable
[OK] LLM client initialized (model=gpt-4o)
[WARN] Pipeline incomplete (missing: generator)
```

- The final state is technically safe, but the logging is misleading for the operator or responder reading the console during a demo incident.

## What Passed

- `C:\CorpusForge\start_corpusforge.bat --terminal` launched the GUI from the mainline repo and attached to the configured pipeline environment.
- CorpusForge bad-input recovery was good for a missing source path: the GUI logged `Source not found: C:\does\not\exist`, returned controls to idle, and did not wedge the window.
- CorpusForge image OCR failure surfaced a clear prerequisite message on a PNG input:

```text
Image OCR failed for ocr_probe.png: tesseract is not installed or it's not in your PATH. See README file for more information.
```

- `C:\HybridRAG_V2\.venv\Scripts\python.exe -m src.api.server --host 127.0.0.1 --port 8001` launched successfully on GPU 0, served `/health`, and returned a clear `/query` error when the API key was missing:

```json
{"detail":"LLM not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."}
```

- CorpusForge automated GUI smash coverage exists and passed on the current mainline state:

```text
Command: C:\CorpusForge\.venv\Scripts\python.exe -m pytest C:\CorpusForge\tests\test_gui_button_smash.py -q
Result: 12 passed in 0.78s
```

## Failure Matrix

| Scenario | Exact command / action | Observed behavior | Expected behavior | Severity | Recovery quality |
|---|---|---|---|---|---|
| CorpusForge documented GUI launch | `C:\CorpusForge\.venv\Scripts\python.exe C:\CorpusForge\scripts\boot.py` | Prints boot validation and exits; no GUI window | Opens the GUI or docs point to the real launcher | High | Broken |
| CorpusForge actual GUI launch | `cmd /c C:\CorpusForge\start_corpusforge.bat --terminal` | GUI launches; GPU 0 applied | Launch succeeds | Pass | Clear |
| CorpusForge missing source path | GUI run with source `C:\does\not\exist` | `Source not found` error, controls return to idle | Clear error and recovery | Pass | Clear |
| CorpusForge missing Tesseract on image OCR | GUI pipeline run on `ocr_probe.png` | Explicit Tesseract-not-installed error emitted | Clear prerequisite error | Pass | Clear |
| CorpusForge missing OCR prereqs on scanned PDF | GUI pipeline run on `ocr_probe.pdf` | Generic `Empty parse result`; no prerequisite guidance | Explicit missing Poppler/Tesseract guidance | Medium | Confusing |
| CorpusForge stop mid-run | Live stop drill on a slow in-flight pipeline | UI says stop requested; work continues to completion | Cooperative cancel or explicit "stop after current file" messaging | High | Broken |
| HybridRAG V2 start script | `cmd /c C:\HybridRAG_V2\start_gui.bat --terminal` then `curl http://127.0.0.1:8000/health` | GUI boots, port 8000 remains closed | If docs promise both parts, the server should also start | High | Confusing |
| HybridRAG V2 missing API key via server path | Start server on port 8001 with API env cleared, POST `/query` | `/health` OK, `/query` returns `503` with useful remediation text | Clear, actionable failure | Pass | Clear |
| HybridRAG V2 stop mid-query | QueryPanel drill with slow background query | UI flips to idle and shows `Query cancelled.` while work continues | Cooperative cancel or honest pending-work message | High | Broken |

## Scenarios Executed

- Repo-state verification on the real roots:
  - `C:\CorpusForge`
  - `C:\HybridRAG_V2`
- Venv / CUDA verification in both repos
- OCR prerequisite verification:
  - `where.exe tesseract`
  - `where.exe pdftoppm`
- GPU usage snapshot with `nvidia-smi`; GPU 0 selected as lesser-used
- CorpusForge:
  - documented GUI launch path
  - actual launcher path
  - bad source path drill
  - image OCR failure drill
  - scanned-PDF OCR failure drill
  - stop-mid-run drill
  - automated GUI smash test
- HybridRAG V2:
  - actual start script
  - direct server boot
  - missing-API-key `/health` and `/query` drills
  - backend-unavailable check after GUI-only start script
  - query stop/cancel drill

## Key Log Snippets

### CorpusForge bad source path

```text
Source not found: C:\does\not\exist
Pipeline complete: 0 parsed, 0 failed, 0 skipped in 0.0s
```

### CorpusForge stop drill

```text
[parse] 0/1 — starting slow run
Pipeline stop requested by user.
Pipeline complete: 1 parsed, 0 failed, 0 skipped in 2.5s
```

### HybridRAG V2 start script with no API key

```text
[STARTUP ...] Backend: model attached. GUI ready.
No API key found -- LLM client unavailable
[OK] LLM client initialized (model=gpt-4o)
[WARN] Pipeline incomplete (missing: generator)
curl: (7) Failed to connect to 127.0.0.1 port 8000
```

### HybridRAG V2 direct server with no API key

```json
{"status":"ok","chunks_loaded":49750,"entities_loaded":61388,"relationships_loaded":9497,"llm_available":false}
{"detail":"LLM not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."}
```

## Residual Risks

- HybridRAG V2 GUI harness documentation exists at `C:\HybridRAG_V2\docs\qa\QA_GUI_HARNESS_2026-04-05.md`, but no `C:\HybridRAG_V2\src\gui\testing\` harness package was present on disk during this QA pass. I used live launch/drill coverage instead.
- Tier D human button smash by a non-author was not performed by me in this pass.
- OCR validation remains partial because native OCR prerequisites are absent on this workstation.
