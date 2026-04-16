# Lane 3 Operator / Installer / Preflight Evidence — 2026-04-13

Purpose: capture the exact machine probes, the installer/precheck/runtime OCR mismatch that was found, the fixes landed in Lane 3, and the remaining gap.

## What Was Wrong

1. Precheck already resolved off-PATH Tesseract from `C:\Program Files\Tesseract-OCR\tesseract.exe`, but runtime OCR parsers did not use the same fallback logic.
2. The installer checked OCR tools and warned, but it did not leave a clearly usable runtime path for Tesseract when the binary existed off-PATH.
3. Operator docs still implied `where.exe tesseract` / `tesseract --version` were the primary readiness checks, which is misleading on this workstation because Tesseract is installed but not on PATH.
4. Poppler / `pdftoppm.exe` is still missing, so scanned-PDF OCR was ambiguous in docs and only indirectly surfaced in tooling.

## What Was Fixed

### CorpusForge code

- `src/parse/parsers/image_parser.py`
  - runtime now resolves Tesseract from `TESSERACT_CMD`, PATH, or the known fallback path.
  - emits a one-time warning when fallback resolution is used.
- `src/parse/parsers/pdf_parser.py`
  - runtime now resolves both Tesseract and Poppler from env, PATH, or known fallback locations.
  - emits a one-time warning when scanned-PDF OCR is unavailable because `pdftoppm.exe` is missing.
- `tools/precheck_workstation_large_ingest.py`
  - now reports `Image OCR runtime` separately from `Scanned-PDF OCR runtime`.
  - explicitly says when runtime is using a fallback Tesseract path and when scanned-PDF OCR is unavailable.
- `tools/setup_workstation_2026-04-06.ps1`
  - now persists `TESSERACT_CMD` to the user environment when Tesseract is found.
  - warns clearly when Poppler is missing and scanned-PDF OCR is unavailable.
- `PRECHECK_WORKSTATION_700GB.bat`
  - now pauses on success for interactive operator runs so the result is visible.

### Entry-point docs

- `C:\CorpusForge\___OnboardingInfo_2026_04_09.md`
- `C:\CorpusForge\docs\OPERATOR_QUICKSTART.md`
- `C:\CorpusForge\docs\MORNING_OPERATOR_QUICKSTART_2026-04-09.md`
- `C:\CorpusForge\docs\DEDUP_ONLY_PASS_GUIDE_2026-04-08.md`
- `C:\HybridRAG_V2\___OnboardingInfo_2026_04_09.md`
- `C:\HybridRAG_V2\docs\SOURCE_OF_TRUTH_MAP_2026-04-12.md`
- `C:\HybridRAG_V2\docs\COORDINATOR_HANDOVER_2026-04-10.md`

These now point contributors and operators at canonical repo roots, repo-local `.venv`, the preferred Forge -> V2 staging path, the latest 400-query / clean-store eval truth, and the actual OCR state on this workstation.

## What Remains Missing

1. `pdftoppm.exe` / Poppler is still not installed or discoverable on this machine.
2. Scanned-PDF OCR remains unavailable until Poppler is installed or `HYBRIDRAG_POPPLER_BIN` points to a valid Poppler `bin` directory.
3. Image OCR is available through Tesseract, but already-open shells may not show `TESSERACT_CMD` in the process environment until a new shell is started. Runtime fallback logic now covers that gap.

## Exact Machine Probes

### Raw machine state before repair

```powershell
$ErrorActionPreference='SilentlyContinue'
Write-Host ('TESSERACT_CMD=' + $env:TESSERACT_CMD)
Write-Host ('HYBRIDRAG_POPPLER_BIN=' + $env:HYBRIDRAG_POPPLER_BIN)
where.exe tesseract
where.exe pdftoppm
```

Observed:

- `TESSERACT_CMD=` blank
- `HYBRIDRAG_POPPLER_BIN=` blank
- `where.exe tesseract` returned no match
- `where.exe pdftoppm` returned no match

### Direct fallback path probe

```powershell
Test-Path 'C:\Program Files\Tesseract-OCR\tesseract.exe'
Test-Path 'C:\Program Files\poppler\Library\bin\pdftoppm.exe'
```

Observed:

- Tesseract fallback path: `True`
- Poppler fallback path: `False`

### Repo-local dependency probe

```powershell
@'
import importlib
mods=['PIL','pytesseract','pdf2image','pypdf','pdfplumber']
for m in mods:
    try:
        importlib.import_module(m)
        print(f'{m}\tOK')
    except Exception as e:
        print(f'{m}\tFAIL\t{e}')
'@ | C:\CorpusForge\.venv\Scripts\python.exe -
```

Observed:

- `PIL OK`
- `pytesseract OK`
- `pdf2image OK`
- `pypdf OK`
- `pdfplumber OK`

## Exact Commands Run

### Precheck

```powershell
C:\CorpusForge\.venv\Scripts\python.exe C:\CorpusForge\tools\precheck_workstation_large_ingest.py
```

Observed key lines:

- `PASS: Image OCR runtime`
- `proof: Tesseract via fallback path: C:\Program Files\Tesseract-OCR\tesseract.exe | tesseract v5.4.0.20240606 | runtime uses fallback path because TESSERACT_CMD is not set`
- `WARNING: Scanned-PDF OCR runtime`
- `proof: no usable pdftoppm.exe found on PATH, HYBRIDRAG_POPPLER_BIN, or fallback locations; scanned-PDF OCR is unavailable`
- `RESULT: PASS`

Report written to:

- `C:\CorpusForge\logs\precheck_workstation_20260413_195757.txt`

### Runtime resolver probe

```powershell
@'
from src.parse.parsers.image_parser import _resolve_tesseract_cmd as image_tess
from src.parse.parsers.pdf_parser import _resolve_tesseract_cmd as pdf_tess, _resolve_poppler_bin
print('image_tesseract', image_tess())
print('pdf_tesseract', pdf_tess())
print('pdf_poppler', _resolve_poppler_bin())
'@ | C:\CorpusForge\.venv\Scripts\python.exe -
```

Observed:

- `image_tesseract ('C:\\Program Files\\Tesseract-OCR\\tesseract.exe', 'fallback path')`
- `pdf_tesseract ('C:\\Program Files\\Tesseract-OCR\\tesseract.exe', 'fallback path')`
- `pdf_poppler (None, 'missing')`

### Image OCR smoke

```powershell
@'
from pathlib import Path
from PIL import Image, ImageDraw
from src.parse.parsers.image_parser import ImageParser
out = Path('temp') / 'lane3_ocr_probe.png'
out.parent.mkdir(exist_ok=True)
img = Image.new('RGB', (480, 140), color='white')
draw = ImageDraw.Draw(img)
draw.text((20, 40), 'Lane 3 OCR Probe 2026', fill='black')
img.save(out)
result = ImageParser().parse(out)
print('text=', repr(result.text[:120]))
print('quality=', result.parse_quality)
print('size=', result.file_size)
out.unlink(missing_ok=True)
'@ | C:\CorpusForge\.venv\Scripts\python.exe -
```

Observed:

- OCR returned text instead of metadata fallback.
- Sample output: `text= 'Lane 3 OCRProte 2028'`
- Confirms Tesseract fallback path is active at runtime.

### Installer path

```powershell
$env:HYBRIDRAG_NO_PAUSE='1'
& "$env:ProgramFiles\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\CorpusForge\tools\setup_workstation_2026-04-06.ps1
```

Observed key lines:

- `PASS Tesseract found: C:\Program Files\Tesseract-OCR\tesseract.exe`
- `WARN Tesseract is not on PATH -- persisting TESSERACT_CMD so runtime OCR still works`
- `PASS Persisted TESSERACT_CMD for future shells: C:\Program Files\Tesseract-OCR\tesseract.exe`
- `WARN Poppler not found -- scanned-PDF OCR is unavailable until pdftoppm.exe is installed or HYBRIDRAG_POPPLER_BIN points to it`

### User-environment verification after installer

```powershell
Get-ItemProperty -Path HKCU:\Environment | Select-Object TESSERACT_CMD, HYBRIDRAG_POPPLER_BIN
```

Observed:

- `TESSERACT_CMD = C:\Program Files\Tesseract-OCR\tesseract.exe`
- `HYBRIDRAG_POPPLER_BIN =` blank

## Verification Summary

- Python syntax check passed for:
  - `C:\CorpusForge\tools\precheck_workstation_large_ingest.py`
  - `C:\CorpusForge\src\parse\parsers\pdf_parser.py`
  - `C:\CorpusForge\src\parse\parsers\image_parser.py`
- PowerShell parse check passed for:
  - `C:\CorpusForge\tools\setup_workstation_2026-04-06.ps1`
