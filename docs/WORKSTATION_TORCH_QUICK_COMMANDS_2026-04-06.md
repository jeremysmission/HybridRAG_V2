# Workstation torch Quick Commands 2026-04-06

**Purpose:** Short copy-paste commands for work laptop and work desktop torch troubleshooting.  
**Use case:** You are in PowerShell, in the repo root, and ideally already in the green `(.venv)` prompt.

---

## Fast Rules

- If you already have the green `(.venv)` prompt, `python -m pip ...` is fine.
- If there is any doubt, use the explicit repo venv path version instead.
- Proxy session variables only last for the current PowerShell window.
- `pip-system-certs` installs once per repo `.venv`, not once per session.

---

## 20 Quick Commands

### 1. Go to HybridRAG_V2

```powershell
cd "$env:USERPROFILE\Desktop1\HybridRAG_V2"
```

### 2. Go to CorpusForge

```powershell
cd "$env:USERPROFILE\Desktop1\CorpusForge"
```

### 3. Set session proxy vars

```powershell
$env:HTTP_PROXY="http://centralproxy.northgrum.com:80"; $env:HTTPS_PROXY="http://centralproxy.northgrum.com:80"; $env:NO_PROXY="127.0.0.1,localhost"
```

### 4. Verify current proxy vars

```powershell
echo $env:HTTP_PROXY; echo $env:HTTPS_PROXY; echo $env:NO_PROXY
```

### 5. Check active Python in the current shell

```powershell
python --version
```

### 6. Check active pip in the current shell

```powershell
python -m pip --version
```

### 7. Check repo venv Python explicitly

```powershell
.\.venv\Scripts\python.exe --version
```

### 8. Check whether `pip-system-certs` is already installed

```powershell
python -m pip show pip-system-certs
```

### 9. Install `pip-system-certs`

```powershell
python -m pip install pip-system-certs --proxy http://centralproxy.northgrum.com:80 --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --use-feature=truststore
```

### 10. Upgrade pip

```powershell
python -m pip install --upgrade pip --proxy http://centralproxy.northgrum.com:80 --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --use-feature=truststore
```

### 11. Quick proxy test without touching torch

```powershell
python -m pip index versions pip --proxy http://centralproxy.northgrum.com:80 --trusted-host pypi.org --trusted-host files.pythonhosted.org --use-feature=truststore
```

### 12. Check whether torch is already in this repo venv

```powershell
python -m pip show torch
```

### 13. Bootstrap torch with `cu124`

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cu124 --proxy http://centralproxy.northgrum.com:80 --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --use-feature=truststore
```

### 14. Force-reinstall `cu128`

```powershell
python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128 --proxy http://centralproxy.northgrum.com:80 --force-reinstall --no-deps --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --use-feature=truststore
```

### 15. Verify torch version and CUDA lane

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

### 16. Show installed torch package metadata

```powershell
python -m pip show torch
```

### 17. Explicit venv pip upgrade command

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip --proxy http://centralproxy.northgrum.com:80 --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --use-feature=truststore
```

### 18. Explicit venv torch force-install command

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128 --proxy http://centralproxy.northgrum.com:80 --force-reinstall --no-deps --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --use-feature=truststore
```

### 19. Save proxy vars persistently for your Windows user

```powershell
[Environment]::SetEnvironmentVariable("HTTP_PROXY","http://centralproxy.northgrum.com:80","User"); [Environment]::SetEnvironmentVariable("HTTPS_PROXY","http://centralproxy.northgrum.com:80","User"); [Environment]::SetEnvironmentVariable("NO_PROXY","127.0.0.1,localhost","User")
```

### 20. Forge fallback: copy torch from working HybridRAG_V2

```powershell
COPY_TORCH_FROM_EXISTING_HYBRIDRAG.bat "C:\Users\randaje\Desktop1\HybridRAG_V2\.venv"
```

---

## Best Minimal Sequence

If you only want the shortest reliable sequence:

1. Command 3
2. Command 8
3. Command 10
4. Command 11
5. Command 13
6. Command 14
7. Command 15

---

## How To Read The Results

- If command 11 works, proxy and cert path are probably good enough.
- If command 11 throws `NewConnectionError`, proxy or reachability is still broken.
- If command 11 throws SSL or certificate errors, trust is still broken.
- If command 15 prints `2.7.1+cu128`, `12.8`, and `True`, you are done.

---

## Related Docs

- [WORKSTATION_DESKTOP_SETTINGS_FOR_TORCH_INSTALL_2026_04_06.md](/C:/HybridRAG_V2/docs/WORKSTATION_DESKTOP_SETTINGS_FOR_TORCH_INSTALL_2026_04_06.md)
- [WORKSTATION_PROXY_AND_PYTHON_PATH_FIX_2026-04-06.md](/C:/HybridRAG_V2/docs/WORKSTATION_PROXY_AND_PYTHON_PATH_FIX_2026-04-06.md)
- [WORKSTATION_STACK_INSTALL_2026-04-06.md](/C:/HybridRAG_V2/docs/WORKSTATION_STACK_INSTALL_2026-04-06.md)
