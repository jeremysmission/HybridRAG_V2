# Workstation Stack Install -- V2 + CorpusForge

Date: 2026-04-06

## Bottom Line

Yes, the stack is now ready for workstation install.

The key lesson from `HybridRAG3_Educational` was not "use the same path everywhere."
It was:

- do not track machine-specific paths in git-managed config
- do not rely on ad-hoc pip commands on work machines
- do not assume corporate proxy / cert / PowerShell behavior will "just work"

V2 and CorpusForge are safer than old HybridRAG3 on that front because their shipped configs are repo-relative:

- `HybridRAG_V2/config/config.yaml`
- `CorpusForge/config/config.yaml`

That means the repo can live under different roots on laptop and desktop without recreating the old `config.yaml` overwrite failure from `HybridRAG3`.

## What Changed For Workstation Readiness

Both repos now have:

- root installer launcher: `INSTALL_WORKSTATION.bat`
- PowerShell process bypass via `-ExecutionPolicy Bypass`
- UTF-8 / no-BOM-safe setup handling
- `NO_PROXY=localhost,127.0.0.1`
- `pip-system-certs`
- trusted-host pip installs for corporate proxy paths
- auto-written `.venv\pip.ini` without BOM
- pinned CUDA torch install lane: `torch==2.7.1` from `cu128`

CorpusForge also now checks for:

- Tesseract
- Poppler `pdftoppm`

and warns if they are missing.

## Recommended Repo Paths

### Workstation Laptop

Use the same parent you already used for HybridRAG3:

```text
C:\Users\randaje\Desktop1\CorpusForge
C:\Users\randaje\Desktop1\HybridRAG_V2
```

That keeps your operator muscle memory intact.

### Workstation Desktop

The desktop can use a different local SSD path.
The important rule is stability per machine, not sameness across machines.

Example:

```text
D:\AI\CorpusForge
D:\AI\HybridRAG_V2
```

If you already have a preferred desktop path, keep it stable and use that.

## Install Order

1. Install Python 3.12.
2. Install Git.
3. Install Ollama.
4. Install Tesseract OCR.
5. Install Poppler.
6. Clone or download `CorpusForge`.
7. Run `CorpusForge\\INSTALL_WORKSTATION.bat`.
8. Clone or download `HybridRAG_V2`.
9. Run `HybridRAG_V2\\INSTALL_WORKSTATION.bat`.

## Exact Operator Flow

### CorpusForge

```text
Open the CorpusForge folder
Double-click INSTALL_WORKSTATION.bat
```

After install:

```text
Double-click start_corpusforge.bat
```

Optional dry run from terminal:

```powershell
cd <CorpusForge repo root>
start_corpusforge.bat --dry-run
```

### HybridRAG V2

```text
Open the HybridRAG_V2 folder
Double-click INSTALL_WORKSTATION.bat
```

After install:

```text
Double-click start_gui.bat
```

Optional dry run from terminal:

```powershell
cd <HybridRAG_V2 repo root>
start_gui.bat --dry-run
```

## Required External Dependencies

### CorpusForge

Required:

- Python 3.12
- Tesseract OCR
- Poppler

Needed for optional/local enrichment:

- Ollama
- `phi4:14b-q4_K_M`

### HybridRAG V2

Required:

- Python 3.12

Needed for local demo / local extraction / stress paths:

- Ollama
- `phi4:14b-q4_K_M`

Needed for operational GPT-backed answer generation:

- OpenAI or Azure OpenAI credentials

## Why This Is Safer Than Old HybridRAG3

Referenced HybridRAG3 lessons:

- `docs/WorkDesktop_IndexChunk_Investigation_3_27_2026.md`
- `docs/03_guides/DESKTOP_AUTHORITY_LAPTOP_DELTA_WORKFLOW_2026-03-30.md`
- `docs/01_setup/WORK_COMPUTER_ZIP_INSTALL_AND_AUTOMATED_SETUP.md`

The old failure mode was:

- tracked machine-specific config paths
- work-machine installs missing pip trust/cert hardening
- mismatched CUDA torch lanes

The V2/Forge workstation lane now avoids those mistakes by:

- keeping config paths repo-relative by default
- installing CUDA torch from the PyTorch CUDA index
- baking trusted-host settings into `.venv\pip.ini`
- using the workstation installer instead of manual piecemeal pip commands

## Remaining Reality Checks

These are still real:

- CorpusForge scanned-PDF OCR still depends on Tesseract + Poppler being installed on that machine
- local Ollama model pulls can still be blocked by work-network policy
- if a machine has no NVIDIA GPU, install still works, but it will fall back to CPU torch and be slower

## Recommended First Machine

Follow the HybridRAG3 lesson here too:

- test one machine first
- only then roll the same install flow to the second machine

If you want the least-risk first pass:

- install on the laptop under `Desktop1` first
- verify both repos launch
- then repeat on the desktop
