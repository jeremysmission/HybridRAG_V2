# Workstation Proxy And Python Path Fix

**Date:** 2026-04-06 MDT  
**Purpose:** Explain the work-machine install issue clearly and provide the exact non-admin fix steps.  
**Audience:** Operator on work laptop and work desktop

---

## Bottom Line

Two separate workstation issues were happening at the same time:

1. `pip` and PyTorch downloads needed the corporate proxy variables set
2. plain `python` in normal shells was resolving to system Python `3.9`, not the repo `.venv`

This created a confusing situation where:

- the repo installer was trying to use `Python 3.12`
- but normal terminal checks like `python --version` were still showing `3.9.6`
- and `pip` traffic failed unless proxy settings were present

The fix is:

- set proxy vars in the PowerShell session
- use the repo `.venv` Python directly
- do not rely on bare `python`

---

## What This Means

## Problem 1: Proxy Settings

On the work machines, `pip` needed:

- `HTTP_PROXY`
- `HTTPS_PROXY`
- `NO_PROXY`

Without those, package install attempts could fail with:

- proxy authentication errors
- SSL/certificate errors
- inability to find torch wheels even though they exist

## Problem 2: Wrong Python On PATH

The repo does **not** install Python 3.9.

What happened is:

- system `python` on the workstation was still `3.9.6`
- the repo `.venv` was separate
- in a normal shell, `python --version` showed the global Python, not the repo venv

So:

- `python --version` in a plain shell is **not** proof that the repo is using 3.9
- `.\.venv\Scripts\python.exe --version` is the check that matters

---

## Do Not Use The Windows Env Var UI First

If you open the Windows Environment Variables dialog and try to set machine-wide variables, it may trigger badge/admin prompts.

That is not necessary for this install flow.

If your desktop admin rights are unstable, avoid that path for now.

Use:

- session-only PowerShell variables
- or user-level environment variables

Both are enough for the repo installs.

---

## Fastest Non-Admin Fix: PowerShell Session Variables

Open PowerShell and run these commands in the same window where you plan to install:

```powershell
$env:HTTP_PROXY = "http://centralproxy.northgrum.com:80"
$env:HTTPS_PROXY = "http://centralproxy.northgrum.com:80"
$env:NO_PROXY = "127.0.0.1,localhost"
```

These are temporary.

They apply only to that PowerShell window and go away when it is closed.

This is the safest immediate fix when admin rights are flaky.

---

## User-Level Persistent Fix Without Admin

If you want the proxy values to persist for your Windows user account without requiring machine-wide admin changes, run:

```powershell
[Environment]::SetEnvironmentVariable("HTTP_PROXY","http://centralproxy.northgrum.com:80","User")
[Environment]::SetEnvironmentVariable("HTTPS_PROXY","http://centralproxy.northgrum.com:80","User")
[Environment]::SetEnvironmentVariable("NO_PROXY","127.0.0.1,localhost","User")
```

Then close PowerShell and open a new PowerShell window.

This usually does **not** require admin because it writes user variables, not system variables.

---

## Exact Checks To Run Before Install

Do these checks from the repo root.

### 1. Check the Python launcher

```powershell
py -3.12 --version
```

Expected:

- Python `3.12.x`

If this fails, the machine does not currently have a usable Python 3.12 launcher path for the installer.

### 2. Check what plain `python` means in the shell

```powershell
Get-Command python | Select-Object Source
python --version
```

This may still show system Python `3.9.6`.

That is useful to know, but it is **not** the repo truth.

### 3. Check the repo venv Python

```powershell
.\.venv\Scripts\python.exe --version
```

This is the Python that matters for the repo.

### 4. Check the repo venv pip

```powershell
.\.venv\Scripts\pip.exe --version
```

---

## Correct Rule For Workstation Repo Commands

Use one of these:

```powershell
.\.venv\Scripts\python.exe
```

or:

```powershell
.\.venv\Scripts\pip.exe
```

Do **not** assume bare:

```powershell
python
pip
```

are using the repo environment.

---

## Example: Safe Install Session

### CorpusForge

```powershell
cd "$env:USERPROFILE\Desktop1\CorpusForge"
$env:HTTP_PROXY = "http://centralproxy.northgrum.com:80"
$env:HTTPS_PROXY = "http://centralproxy.northgrum.com:80"
$env:NO_PROXY = "127.0.0.1,localhost"
py -3.12 --version
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\pip.exe --version
```

If torch download is still failing:

```powershell
.\.venv\Scripts\python.exe -m pip install pip-system-certs --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org
```

Then use one of these recovery paths:

```powershell
COPY_TORCH_FROM_EXISTING_HYBRIDRAG.bat
```

or:

```powershell
INSTALL_CUDA_TORCH_CU124_THEN_FORCE_CU128.bat
```

### HybridRAG V2

```powershell
cd "$env:USERPROFILE\Desktop1\HybridRAG_V2"
$env:HTTP_PROXY = "http://centralproxy.northgrum.com:80"
$env:HTTPS_PROXY = "http://centralproxy.northgrum.com:80"
$env:NO_PROXY = "127.0.0.1,localhost"
py -3.12 --version
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\pip.exe --version
```

---

## If Admin Rights Are Broken On The Desktop

If your badge/admin rights are malfunctioning on the desktop:

- do **not** block on machine-wide Environment Variables UI
- use session-level `$env:` commands instead
- if needed, use user-level `SetEnvironmentVariable(..., "User")`

Only open an IT ticket if you truly need machine-level permanent changes.

For repo install and pip work, you usually do **not** need machine-level admin env-var changes.

---

## What To Verify After Torch Install

Run:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print('built_cuda=', torch.version.cuda); print('cuda_available=', torch.cuda.is_available())"
```

Expected for the desired lane:

- `2.7.1+cu128`
- `built_cuda= 12.8`
- `cuda_available= True`

---

## Key Lessons

1. Proxy settings were a real dependency on the work machines.
2. The repo installer using `py -3.12` is different from a normal shell using bare `python`.
3. A plain shell showing `Python 3.9.6` does not automatically mean the repo venv is wrong.
4. The repo truth is always:
   - `.\.venv\Scripts\python.exe --version`
5. Session-level proxy variables are the fastest non-admin recovery path.

---

## Related Docs

- [WORKSTATION_STACK_INSTALL_2026-04-06.md](/C:/HybridRAG_V2/docs/setup/WORKSTATION_STACK_INSTALL_2026-04-06.md)
- [SPRINT_11_WORK_SEQUENCE_AND_TODO_2026-04-06.md](/C:/HybridRAG_V2/docs/planning/SPRINT_11_WORK_SEQUENCE_AND_TODO_2026-04-06.md)

