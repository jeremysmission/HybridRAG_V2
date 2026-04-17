# Eval Tools Automated Install Guide

**Purpose:** Install RAGAS evaluation tools for QA Workbench and Eval GUI.
**Time:** ~5 minutes (longer behind a corporate proxy).

## Prerequisites

- HybridRAG V2 is already installed (`INSTALL_WORKSTATION.bat` has been run)
- `.venv` folder exists in the repo root
- Windows 10/11 with PowerShell 5.1+

## Steps

### 1. Double-click `INSTALL_EVAL_TOOLS.bat`

The installer will:
1. Check that Python and `.venv` exist
2. Export CA certificates from Windows cert store (for SSL proxy compatibility)
3. Auto-detect corporate proxy settings
4. Configure pip with proxy, certificates, and trusted hosts
5. Install all packages from `requirements_eval_gui.txt`
6. Verify each package imports correctly
7. Write an install manifest to `docs/EVAL_TOOLS_INSTALL_MANIFEST.txt`

### 2. Follow the prompts

The installer pauses at key checkpoints. Press any key to continue at each pause.

### 3. Expected output

You should see:
```
== Pre-Flight Checks ==
   [OK] Python: Python 3.12.x
   [OK] .venv exists
   [OK] pip found
   ...
== CA Certificate Export ==
   [OK] Exported NN CA certs to: .venv\ca-bundle.pem
   ...
== Installing Eval Tools ==
   [OK] pip install completed
   ...
== Post-Install Verification ==
   [OK] ragas v0.4.3
   [OK] rapidfuzz v3.14.5
   ...
SUCCESS -- All eval tools installed and verified
```

### 4. Verify

After install, test manually:
```cmd
.venv\Scripts\python.exe -c "import ragas; print(ragas.__version__)"
```

Expected output: `0.4.3`

Then launch QA Workbench or Eval GUI -- the RAGAS tab should no longer show "not installed".

## Walk-Away Mode

To skip all pauses (for automated/unattended installs):
```cmd
INSTALL_EVAL_TOOLS.bat -NoPause
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Pre-flight checks failed" | Run `INSTALL_WORKSTATION.bat` first |
| SSL/certificate errors | The installer auto-exports CA certs. If it still fails, see the manual install guide |
| Timeout errors behind proxy | The installer sets 120s timeout and 5 retries. If still failing, check your proxy URL is correct |
| "ragas not installed" in GUI | Re-run the installer. Check `docs/EVAL_TOOLS_INSTALL_MANIFEST.txt` for details |

---

Jeremy Randall | HybridRAG_V2 | 2026-04-16 MDT
