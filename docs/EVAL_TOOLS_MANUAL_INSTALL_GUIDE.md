# Eval Tools Manual Install Guide

**Purpose:** Step-by-step manual installation of RAGAS evaluation tools.
**Use when:** The automated installer (`INSTALL_EVAL_TOOLS.bat`) fails or when you need to install packages one at a time for debugging.

## Prerequisites

1. Python 3.10+ installed and on PATH
2. HybridRAG V2 `.venv` exists (`python -m venv .venv` if not)
3. Activate the venv: `.venv\Scripts\activate`

## Step 1: Configure Proxy (if behind corporate proxy)

### 1a. Find your proxy URL

```cmd
REM Check environment variables
echo %HTTPS_PROXY%

REM Check Windows Registry
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer

REM Check WinHTTP
netsh winhttp show proxy
```

### 1b. Export CA certificates

If behind an SSL-intercepting proxy, export your corporate CA certificates:

```powershell
# Run in PowerShell
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'LocalMachine')
$store.Open('ReadOnly')
$pemLines = @()
foreach ($cert in $store.Certificates) {
    $b64 = [Convert]::ToBase64String($cert.RawData, 'InsertLineBreaks')
    $pemLines += "-----BEGIN CERTIFICATE-----"
    $pemLines += $b64
    $pemLines += "-----END CERTIFICATE-----"
    $pemLines += ""
}
$store.Close()
[System.IO.File]::WriteAllText(".venv\ca-bundle.pem", ($pemLines -join "`n"))
Write-Host "Exported $($store.Certificates.Count) certs"
```

### 1c. Create pip.ini

Create `.venv\pip.ini` with your proxy settings:

```ini
[global]
disable-pip-version-check = true
timeout = 120
retries = 5
proxy = http://your.proxy.server:8443
cert = C:\path\to\your\repo\.venv\ca-bundle.pem
trusted-host =
    pypi.org
    pypi.python.org
    files.pythonhosted.org
```

Replace `proxy =` with your actual proxy URL, or remove the line if not behind a proxy.

## Step 2: Set Environment Variables

```cmd
set HF_HUB_OFFLINE=1
set PIP_CERT=.venv\ca-bundle.pem
set SSL_CERT_FILE=.venv\ca-bundle.pem
set REQUESTS_CA_BUNDLE=.venv\ca-bundle.pem
```

## Step 3: Install Packages (in order)

Install dependencies first, then RAGAS last.

```cmd
REM Core dependencies (many already in .venv from INSTALL_WORKSTATION)
pip install numpy==1.26.4
pip install pydantic==2.11.1
pip install tqdm==4.67.3
pip install rich==13.9.4

REM OpenAI + LangChain stack
pip install openai==2.32.0
pip install tiktoken==0.8.0
pip install langchain-core==1.2.30
pip install langchain==1.2.15
pip install langchain-community==0.4.1
pip install langchain-openai==1.1.13

REM Data + ML
pip install datasets==4.8.4
pip install scikit-learn==1.8.0
pip install scikit-network==0.33.5
pip install networkx==3.6.1

REM Utilities
pip install appdirs==1.4.4
pip install diskcache==5.6.3
pip install nest-asyncio==1.6.0
pip install pillow==12.1.0
pip install typer==0.24.1
pip install instructor==1.15.1

REM RAGAS dependencies (install BEFORE ragas)
pip install rapidfuzz==3.14.5

REM RAGAS (install LAST)
pip install ragas==0.4.3
```

## Step 4: Verify Each Package

```cmd
python -c "import ragas; print('ragas', ragas.__version__)"
python -c "import rapidfuzz; print('rapidfuzz', rapidfuzz.__version__)"
python -c "import datasets; print('datasets', datasets.__version__)"
python -c "import langchain_core; print('langchain-core', langchain_core.__version__)"
python -c "import tiktoken; print('tiktoken', tiktoken.__version__)"
python -c "import instructor; print('instructor', instructor.__version__)"
python -c "import openai; print('openai', openai.__version__)"
```

All should print the package name and version without errors.

## Step 5: Test RAGAS

```cmd
python -c "from ragas.metrics import NonLLMContextRecall; print('NonLLMContextRecall imported OK')"
```

## Troubleshooting

### SSL Certificate Errors

```
pip install ... 
ERROR: Could not fetch URL ... SSL: CERTIFICATE_VERIFY_FAILED
```

**Fix:** Make sure `ca-bundle.pem` exists and `pip.ini` has the `cert =` line pointing to it.

### Proxy Connection Timeout

```
pip install ...
ERROR: Connection to pypi.org timed out
```

**Fix:** Verify your proxy URL is correct. Try:
```cmd
pip install --proxy http://your.proxy:8443 --trusted-host pypi.org ragas
```

### Package Conflicts

If pip reports version conflicts:
```cmd
pip install --no-deps ragas==0.4.3
pip install --no-deps rapidfuzz==3.14.5
```

Then install missing dependencies individually.

### "ragas not installed" in GUI

After installation, restart the GUI application. The import check runs at startup.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-16 MDT
