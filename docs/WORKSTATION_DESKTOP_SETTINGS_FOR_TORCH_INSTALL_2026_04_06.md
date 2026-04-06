# Workstation Desktop Settings for torch Install 2026_04_06

**Date:** 2026-04-06 MDT  
**Purpose:** Give a clear reminder for tomorrow on the work desktop and explain exactly which settings matter for `torch` install, where they can be set, and in what order to try things.  
**Applies To:** `HybridRAG_V2` and `CorpusForge`

---

## Bottom Line

Two different things are being mixed together:

1. proxy settings needed for `pip` to reach package servers at work
2. Python interpreter selection for the repo `.venv`

Those are separate.

- Setting proxy values in PowerShell affects the current session only.
- Setting proxy values in Windows Environment Variables persists them for future sessions.
- `PATH` decides what bare `python` and bare `pip` mean.
- The repo `.venv` is the truth for repo installs, not bare `python`.

---

## What Is Verified Right Now

### Work laptop

The work laptop still has Python 3.12 on `PATH`:

- `...\Programs\Python\Python312`
- `...\Programs\Python\Python312\Scripts`

That is good.

The laptop also proved that once proxy variables were set, `pip` traffic started working and the `torch 2.7.1+cu128` install path was able to proceed.

### Work desktop

The work desktop would not reliably let the Windows Environment Variables UI open/write because admin rights appeared to be broken again.

That does **not** block install work.

It means:

- do not depend on the Windows Environment Variables UI tomorrow
- use PowerShell session variables first
- if needed, use user-level persistent variables from PowerShell instead of the UI

---

## Session Vs Windows Env Vars

### PowerShell session variables

If you type:

```powershell
$env:HTTP_PROXY = "http://centralproxy.northgrum.com:80"
$env:HTTPS_PROXY = "http://centralproxy.northgrum.com:80"
$env:NO_PROXY = "127.0.0.1,localhost"
```

that affects only the current PowerShell window.

Anything launched from that same window inherits those values:

- `pip`
- `python`
- batch files started from that same window

When that PowerShell window closes, those values are gone.

### Windows Environment Variables

If you set the same variables in Windows Environment Variables:

- `User` scope = persistent for that Windows account
- `System` scope = persistent for the whole workstation and usually needs admin

Those settings survive new windows and reboots.

### Practical rule

For tomorrow's install work:

- session-level PowerShell vars are enough
- persistent Windows env vars are optional convenience
- do **not** block on system-level env var access

---

## Why `NO_PROXY` Matters

`NO_PROXY=127.0.0.1,localhost` keeps local traffic from being sent through the corporate proxy.

That matters for:

- local services
- local API endpoints
- loopback-only tools

Recommended:

- use `NO_PROXY` in the PowerShell session
- if possible, also save it as a Windows `User` env var later

---

## Why The Repo `.venv` Matters More Than Bare `python`

On the workstation, bare `python` or bare `pip` may point to the wrong interpreter.

The safe commands are:

```powershell
.\.venv\Scripts\python.exe
.\.venv\Scripts\pip.exe
```

Those always target the repo environment.

So the real checks are:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\pip.exe --version
.\.venv\Scripts\pip.exe show torch
```

Not:

```powershell
python --version
pip show torch
```

unless the shell is already known to be inside the right repo venv.

---

## Tomorrow's Desktop Sequence

Open PowerShell and do this in order.

### 1. Set session proxy values in that same PowerShell window

```powershell
$env:HTTP_PROXY = "http://centralproxy.northgrum.com:80"
$env:HTTPS_PROXY = "http://centralproxy.northgrum.com:80"
$env:NO_PROXY = "127.0.0.1,localhost"
```

### 2. Confirm they are present

```powershell
echo $env:HTTP_PROXY
echo $env:HTTPS_PROXY
echo $env:NO_PROXY
```

Expected:

- `http://centralproxy.northgrum.com:80`
- `http://centralproxy.northgrum.com:80`
- `127.0.0.1,localhost`

### 3. Move into the repo

For `HybridRAG_V2`:

```powershell
cd "$env:USERPROFILE\\Desktop1\\HybridRAG_V2"
```

For `CorpusForge`:

```powershell
cd "$env:USERPROFILE\\Desktop1\\CorpusForge"
```

Adjust the path if the desktop uses a different local directory.

### 4. Check the workstation Python 3.12 launcher

```powershell
py -3.12 --version
```

### 5. Check the repo venv directly

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\pip.exe --version
.\.venv\Scripts\pip.exe show torch
```

### 6. If `torch` is missing, use the repo venv explicitly

First bootstrap trust:

```powershell
.\.venv\Scripts\python.exe -m pip install pip-system-certs --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org
```

Then use the proven workstation fallback sequence:

```powershell
.\.venv\Scripts\pip.exe install torch --index-url https://download.pytorch.org/whl/cu124 --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org
.\.venv\Scripts\pip.exe install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128 --force-reinstall --no-deps --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org
```

### 7. Verify the result

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print('built_cuda=', torch.version.cuda); print('cuda_available=', torch.cuda.is_available())"
```

Expected target:

- `2.7.1+cu128`
- `built_cuda= 12.8`
- `cuda_available= True`

---

## If The Windows Env Var UI Is Still Blocked

Do not stop there.

Use the PowerShell session method above.

If you want persistent user-level values without using the UI, try:

```powershell
[Environment]::SetEnvironmentVariable("HTTP_PROXY","http://centralproxy.northgrum.com:80","User")
[Environment]::SetEnvironmentVariable("HTTPS_PROXY","http://centralproxy.northgrum.com:80","User")
[Environment]::SetEnvironmentVariable("NO_PROXY","127.0.0.1,localhost","User")
```

Then open a new PowerShell window and re-check:

```powershell
echo $env:HTTP_PROXY
echo $env:HTTPS_PROXY
echo $env:NO_PROXY
```

This usually does not need machine-level admin rights because it writes only the current user's environment.

---

## What Not To Do

- Do not assume bare `python` means the repo Python.
- Do not assume a successful install in one repo means the other repo has `torch`.
- Do not block on machine-level Environment Variables UI if session-level PowerShell vars are enough.
- Do not verify `torch` with the wrong interpreter.

---

## If `HybridRAG_V2` Works But `CorpusForge` Does Not

That can happen because each repo has its own `.venv`.

Success in one repo does not populate the other repo automatically.

If `HybridRAG_V2` already has a working `torch` inside its own `.venv`, `CorpusForge` can use the dedicated copy fallback:

```powershell
cd "$env:USERPROFILE\\Desktop1\\CorpusForge"
COPY_TORCH_FROM_EXISTING_HYBRIDRAG.bat
```

If needed, pass the source venv explicitly:

```powershell
COPY_TORCH_FROM_EXISTING_HYBRIDRAG.bat "{USER_HOME}\\Desktop1\\HybridRAG_V2\\.venv"
```

---

## Short Reminder For Tomorrow

1. Open PowerShell.
2. Set `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` in that same window.
3. `cd` into the repo.
4. Use `.\.venv\Scripts\python.exe` and `.\.venv\Scripts\pip.exe`.
5. If `torch` is missing, do the manual `cu124` then forced `cu128` path.
6. Verify `2.7.1+cu128`.

---

## Related Docs

- [WORKSTATION_PROXY_AND_PYTHON_PATH_FIX_2026-04-06.md](/C:/HybridRAG_V2/docs/WORKSTATION_PROXY_AND_PYTHON_PATH_FIX_2026-04-06.md)
- [WORKSTATION_STACK_INSTALL_2026-04-06.md](/C:/HybridRAG_V2/docs/WORKSTATION_STACK_INSTALL_2026-04-06.md)
- [SPRINT_11_WORK_SEQUENCE_AND_TODO_2026-04-06.md](/C:/HybridRAG_V2/docs/SPRINT_11_WORK_SEQUENCE_AND_TODO_2026-04-06.md)
