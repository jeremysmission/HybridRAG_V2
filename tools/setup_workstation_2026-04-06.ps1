#Requires -Version 5.1
<#
.SYNOPSIS
    HybridRAG V2 -- Non-interactive workstation setup.
.DESCRIPTION
    Installs venv, CUDA torch, requirements, and verifies the environment.
    Designed for workstation installs (Python 3.12, CUDA 12.8 lane when NVIDIA is present).
    NO interactive prompts. Auto-retry on failure. Colored diagnostics.
.NOTES
    Author: Jeremy Randall
    Date:   2026-04-06

    Single source of truth for critical dependency verification:
      scripts\verify_install.py (see CRITICAL_IMPORTS list)

    Any new critical runtime dependency goes in requirements.txt AND in
    scripts\verify_install.py::CRITICAL_IMPORTS. Do NOT add a parallel
    hand-rolled package list here -- Section 9 below delegates the entire
    import check to verify_install.py so the two paths cannot drift.
    Reference: commit 8a1361d introduced verify_install.py as the canonical
    install gate; this script was wired into it on 2026-04-12 to close the
    installer-drift gap that silently skipped gliner on a walk-away run.
#>

# ============================================================
# 1. Encoding + Helpers
# ============================================================
# PS 5.1 encoding fixes -- prevents garbled output and BOM injection
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:NO_PROXY = "localhost,127.0.0.1"
$env:no_proxy = "localhost,127.0.0.1"

$global:PassCount = 0
$global:FailCount = 0
$global:WarnCount = 0
$global:StepNum   = 0
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$TrustedHosts = @(
    "--trusted-host", "pypi.org",
    "--trusted-host", "pypi.python.org",
    "--trusted-host", "files.pythonhosted.org",
    "--trusted-host", "download.pytorch.org",
    "--timeout", "120",
    "--retries", "3"
)

function Write-Step  { param([string]$msg) $global:StepNum++; Write-Host "`n[$global:StepNum] $msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) $global:PassCount++; Write-Host "  [PASS] $msg" -ForegroundColor Green }
function Write-Fail  { param([string]$msg) $global:FailCount++; Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-Warn  { param([string]$msg) $global:WarnCount++; Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Info  { param([string]$msg) Write-Host "  [INFO] $msg" -ForegroundColor Gray }
function Format-Elapsed { $ts = $Stopwatch.Elapsed; return ("{0:D2}m {1:D2}s" -f [int]$ts.TotalMinutes, $ts.Seconds) }
function Wait-ForOperator {
    param([string]$Message = "Press any key to continue")
    if ($env:HYBRIDRAG_NO_PAUSE -eq "1") { return }
    Write-Host ""
    Write-Host "  $Message" -ForegroundColor White
    try {
        $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
    } catch {
        cmd /c pause
    }
}
function Remove-TempFileQuietly {
    param([string]$Path)
    try {
        Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
    } catch {
    }
}

function Write-Utf8NoBomFile {
    param([string]$Path, [string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
}

function Initialize-PipConfig {
    param(
        [string]$PipIniPath,
        [string]$ProxyUrl = ""
    )
    $lines = @(
        "[global]",
        "trusted-host =",
        "    pypi.org",
        "    pypi.python.org",
        "    files.pythonhosted.org",
        "    download.pytorch.org",
        "timeout = 120",
        "retries = 3",
        "disable-pip-version-check = true"
    )
    if (-not [string]::IsNullOrWhiteSpace($ProxyUrl)) {
        $lines += "proxy = $ProxyUrl"
    }
    $content = ($lines -join "`n") + "`n"
    Write-Utf8NoBomFile -Path $PipIniPath -Text $content
}

function Get-WorkstationProxyInfo {
    $result = [ordered]@{
        ProxyDetected = $false
        ProxyUrl = ""
        Source = ""
        AutoConfigUrl = ""
    }

    $explicitProxy = $env:HTTPS_PROXY
    if ([string]::IsNullOrWhiteSpace($explicitProxy)) {
        $explicitProxy = $env:HTTP_PROXY
    }
    if (-not [string]::IsNullOrWhiteSpace($explicitProxy)) {
        if ($explicitProxy -notmatch "^https?://") {
            $explicitProxy = "http://$explicitProxy"
        }
        $result.ProxyDetected = $true
        $result.ProxyUrl = $explicitProxy
        $result.Source = "environment"
        return [pscustomobject]$result
    }

    try {
        $inetSettings = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        $proxyEnabled = (Get-ItemProperty $inetSettings -ErrorAction SilentlyContinue).ProxyEnable
        $proxyServer  = (Get-ItemProperty $inetSettings -ErrorAction SilentlyContinue).ProxyServer
        $autoConfig   = (Get-ItemProperty $inetSettings -ErrorAction SilentlyContinue).AutoConfigURL
        if ($autoConfig) {
            $result.AutoConfigUrl = $autoConfig
        }

        if ($proxyEnabled -eq 1 -and $proxyServer) {
            if ($proxyServer -match "https=([^;]+)") {
                $resolvedProxy = $Matches[1]
            } elseif ($proxyServer -match "http=([^;]+)") {
                $resolvedProxy = $Matches[1]
            } else {
                $resolvedProxy = $proxyServer
            }
            if ($resolvedProxy -notmatch "^https?://") {
                $resolvedProxy = "http://$resolvedProxy"
            }
            $result.ProxyDetected = $true
            $result.ProxyUrl = $resolvedProxy
            $result.Source = "windows_registry"
        }
    } catch {
    }

    return [pscustomobject]$result
}

function Test-PipConfigReadable {
    param([string]$PythonExe)
    try {
        $pipConfigCheck = & $PythonExe -m pip config list 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { return $false }
        if ($pipConfigCheck -match "could not load") { return $false }
        return $true
    } catch {
        return $false
    }
}

function Test-NvidiaGpuPresent {
    try {
        & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Get-PythonRuntimeInfo {
    param([string]$PythonExe)
    $probe = @'
import json
import platform
import struct
import sys

print(json.dumps({
    "python_version": ".".join(map(str, sys.version_info[:3])),
    "python_tag": f"cp{sys.version_info[0]}{sys.version_info[1]}",
    "is_64bit": struct.calcsize("P") * 8 == 64,
    "platform": platform.platform(),
}))
'@
    try {
        $raw = & $PythonExe -c $probe 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) { return $null }
        return ($raw | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Write-TorchInstallGuidance {
    param(
        [string]$RepoName,
        [object]$RuntimeInfo,
        [switch]$CudaExpected
    )

    Write-Host ""
    Write-Host "  Torch install guidance for ${RepoName}:" -ForegroundColor Yellow
    if ($RuntimeInfo) {
        Write-Host "    Python version: $($RuntimeInfo.python_version)" -ForegroundColor Gray
        Write-Host "    Python tag:     $($RuntimeInfo.python_tag)" -ForegroundColor Gray
        Write-Host "    64-bit:         $($RuntimeInfo.is_64bit)" -ForegroundColor Gray
    }
    Write-Host "    Official PyTorch 2.7.1 cu128 wheels exist for Windows cp310-cp313." -ForegroundColor Gray
    Write-Host "    Official index: https://download.pytorch.org/whl/cu128/torch/" -ForegroundColor Gray
    Write-Host "    Official versions page: https://pytorch.org/get-started/previous-versions/" -ForegroundColor Gray
    if ($RuntimeInfo -and (-not $RuntimeInfo.is_64bit)) {
        Write-Warn "This interpreter is not 64-bit. PyTorch Windows wheels require 64-bit Python."
    }
    if ($RuntimeInfo -and $RuntimeInfo.python_tag -notin @("cp310", "cp311", "cp312", "cp313")) {
        Write-Warn "This interpreter tag is not in the official 2.7.1 cu128 Windows wheel set."
        Write-Host "    Fix: use Python 3.12 64-bit in the repo .venv." -ForegroundColor Gray
    } else {
        Write-Warn "If pip says 'from versions: none' here, the usual cause is proxy/cert access to download.pytorch.org, not a missing torch release."
    }
    if ($CudaExpected) {
        Write-Host "    Dedicated helper:" -ForegroundColor Gray
        Write-Host "      INSTALL_CUDA_TORCH_WORKSTATION.bat" -ForegroundColor Gray
        Write-Host "    Manual retry:" -ForegroundColor Gray
        Write-Host "      .venv\Scripts\pip.exe install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128 --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org" -ForegroundColor Gray
        Write-Host "    Direct wheel fallback example for Python 3.12 64-bit:" -ForegroundColor Gray
        Write-Host "      torch-2.7.1+cu128-cp312-cp312-win_amd64.whl" -ForegroundColor Gray
    } else {
        Write-Host "    CPU fallback:" -ForegroundColor Gray
        Write-Host "      .venv\Scripts\pip.exe install torch==2.7.1 --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org" -ForegroundColor Gray
    }
}

function Invoke-WithRetry {
    param(
        [scriptblock]$Action,
        [string]$Label,
        [int]$MaxAttempts = 3
    )
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        Write-Info "Attempt $i/$MaxAttempts -- $Label"
        try {
            & $Action
            if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) { return $true }
        } catch { }
        if ($i -lt $MaxAttempts) { Start-Sleep -Seconds 5 }
    }
    return $false
}

# ============================================================
# 2. Detect project root
# ============================================================
Write-Step "Detecting project root"
$ToolsDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ToolsDir

if (-not (Test-Path (Join-Path $ProjectRoot "src\config\schema.py"))) {
    Write-Fail "Not a HybridRAG V2 project root -- missing src\config\schema.py at $ProjectRoot"
    exit 1
}
Write-Ok "Project root: $ProjectRoot"
Set-Location $ProjectRoot

# ============================================================
# 3. Detect Python 3.12
# ============================================================
Write-Step "Detecting Python 3.12"
$pyVersion = $null
try { $pyVersion = & py -3.12 --version 2>&1 } catch { }

if ($pyVersion -match "Python 3\.12") {
    Write-Ok "Found: $pyVersion"
} else {
    Write-Fail "Python 3.12 not found via 'py -3.12'. Install Python 3.12 from python.org."
    exit 1
}

# ============================================================
# 4. Create .venv
# ============================================================
Write-Step "Creating virtual environment"
$VenvDir    = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip    = Join-Path $VenvDir "Scripts\pip.exe"

if (Test-Path $VenvPython) {
    Write-Ok ".venv already exists"
} else {
    $ok = Invoke-WithRetry -Label "py -3.12 -m venv .venv" -Action {
        & py -3.12 -m venv "$VenvDir"
    }
    if ($ok) { Write-Ok ".venv created" } else { Write-Fail "Could not create .venv"; exit 1 }
}

# Activate (for this process only)
$env:VIRTUAL_ENV = $VenvDir
$env:PATH = (Join-Path $VenvDir "Scripts") + ";" + $env:PATH
$PipIni = Join-Path $VenvDir "pip.ini"
$ProxyInfo = Get-WorkstationProxyInfo
if ($ProxyInfo.ProxyDetected) {
    if (-not $env:HTTP_PROXY) { $env:HTTP_PROXY = $ProxyInfo.ProxyUrl }
    if (-not $env:HTTPS_PROXY) { $env:HTTPS_PROXY = $ProxyInfo.ProxyUrl }
    $env:http_proxy = $env:HTTP_PROXY
    $env:https_proxy = $env:HTTPS_PROXY
    Write-Ok "Using proxy for pip ($($ProxyInfo.Source)): $($ProxyInfo.ProxyUrl)"
} elseif (-not [string]::IsNullOrWhiteSpace($ProxyInfo.AutoConfigUrl)) {
    Write-Warn "Detected PAC proxy config: $($ProxyInfo.AutoConfigUrl)"
    Write-Info "pip may still need explicit HTTP_PROXY/HTTPS_PROXY values if package installs fail"
} else {
    Write-Info "No workstation proxy detected; pip will use direct internet"
}
Initialize-PipConfig -PipIniPath $PipIni -ProxyUrl $ProxyInfo.ProxyUrl
if (Test-PipConfigReadable -PythonExe $VenvPython) {
    Write-Ok "Created proxy-safe pip config: $PipIni"
} else {
    Write-Warn "pip.ini validation failed; rewriting once"
    Initialize-PipConfig -PipIniPath $PipIni -ProxyUrl $ProxyInfo.ProxyUrl
    if (Test-PipConfigReadable -PythonExe $VenvPython) {
        Write-Ok "pip.ini repaired: $PipIni"
    } else {
        Write-Fail "pip.ini validation failed -- pip cannot read $PipIni"
        exit 1
    }
}
$RequireCuda = Test-NvidiaGpuPresent
$RuntimeInfo = Get-PythonRuntimeInfo -PythonExe $VenvPython

# ============================================================
# 4.5 Assessment Summary
# ============================================================
Write-Step "Assessment summary"
$pipVersionOutput = & $VenvPython -m pip --version 2>&1
$torchSummary = & $VenvPython -c "import importlib.util; import sys; spec=importlib.util.find_spec('torch'); print('installed=' + str(spec is not None)); sys.exit(0)" 2>&1
$pipSystemCertsSummary = & $VenvPython -m pip show pip-system-certs 2>&1
if ($RuntimeInfo) {
    Write-Info "Repo Python: $($RuntimeInfo.python_version) ($($RuntimeInfo.python_tag), 64-bit=$($RuntimeInfo.is_64bit))"
}
Write-Info "Repo pip: $(($pipVersionOutput | Out-String).Trim())"
Write-Info "Repo pip.ini: $PipIni"
if ($ProxyInfo.ProxyDetected) {
    Write-Info "Proxy source: $($ProxyInfo.Source)"
    Write-Info "Proxy value:  $($ProxyInfo.ProxyUrl)"
} elseif (-not [string]::IsNullOrWhiteSpace($ProxyInfo.AutoConfigUrl)) {
    Write-Info "Proxy PAC:    $($ProxyInfo.AutoConfigUrl)"
} else {
    Write-Info "Proxy:        direct / not detected"
}
Write-Info "GPU present:   $RequireCuda"
Write-Info "torch in venv: $((($torchSummary | Out-String).Trim()) -replace '^installed=', '')"
if ($LASTEXITCODE -eq 0 -and $pipSystemCertsSummary -notmatch "Package\(s\) not found") {
    Write-Info "pip-system-certs: installed"
} else {
    Write-Info "pip-system-certs: missing"
}
Write-Info "Next phase will repair only missing or broken layers"
Wait-ForOperator -Message "Press any key to continue with workstation repair"

# ============================================================
# 5. Upgrade pip + pip-system-certs
# ============================================================
Write-Step "Upgrading pip and installing pip-system-certs"
$pipUpgradeOutput = & $VenvPython -m pip install --upgrade pip @TrustedHosts 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok "pip upgraded"
} else {
    Write-Warn "pip upgrade returned non-zero"
    Write-Info (($pipUpgradeOutput | Out-String).Trim())
}

$pipSystemCertsOutput = & $VenvPip install pip-system-certs @TrustedHosts 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok "pip-system-certs installed"
} else {
    Write-Warn "pip-system-certs failed (non-blocking)"
    Write-Info (($pipSystemCertsOutput | Out-String).Trim())
}

# ============================================================
# 6. Install torch CUDA (BEFORE requirements.txt)
# ============================================================
Write-Step "Installing torch"
if ($RequireCuda) {
    $ok = Invoke-WithRetry -Label "pip install torch==2.7.1 (cu128)" -Action {
        & $VenvPip install "torch==2.7.1" --index-url https://download.pytorch.org/whl/cu128 --force-reinstall --no-deps @TrustedHosts --quiet 2>&1 | Out-Null
    }
    if ($ok) {
        Write-Ok "torch CUDA installed (2.7.1 cu128)"
    } else {
        Write-Fail "torch CUDA install failed after 3 attempts"
        Write-TorchInstallGuidance -RepoName "HybridRAG V2" -RuntimeInfo $RuntimeInfo -CudaExpected
        exit 1
    }
} else {
    Write-Warn "No NVIDIA GPU detected -- installing CPU torch fallback"
    $ok = Invoke-WithRetry -Label "pip install torch==2.7.1 (CPU)" -Action {
        & $VenvPip install "torch==2.7.1" @TrustedHosts --quiet 2>&1 | Out-Null
    }
    if ($ok) {
        Write-Ok "torch CPU fallback installed"
    } else {
        Write-Fail "torch CPU fallback install failed after 3 attempts"
        Write-TorchInstallGuidance -RepoName "HybridRAG V2" -RuntimeInfo $RuntimeInfo
        exit 1
    }
}

# ============================================================
# 7. Install requirements.txt (with retry + drill-down)
# ============================================================
Write-Step "Installing requirements.txt"
$reqFile = Join-Path $ProjectRoot "requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Fail "requirements.txt not found at $reqFile"
    exit 1
}

$ok = Invoke-WithRetry -Label "pip install -r requirements.txt" -Action {
    & $VenvPip install -r $reqFile @TrustedHosts --quiet 2>&1 | Out-Null
}

if ($ok) {
    Write-Ok "All requirements installed"
} else {
    Write-Warn "Bulk install failed -- drilling down to per-package install"
    $lines = Get-Content $reqFile | Where-Object { $_ -match '^\s*[a-zA-Z]' -and $_ -notmatch '^\s*#' }
    $drillFails = @()
    foreach ($line in $lines) {
        $pkg = ($line -split '#')[0].Trim()
        if ([string]::IsNullOrWhiteSpace($pkg)) { continue }
        # Skip torch (already installed from CUDA index)
        if ($pkg -match '^torch(\s|$|=|>|<)') { continue }
        Write-Info "  Installing: $pkg"
        & $VenvPip install $pkg @TrustedHosts --quiet 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "  Failed: $pkg"
            $drillFails += $pkg
        }
    }
    if ($drillFails.Count -gt 0) {
        Write-Fail "Drill-down failures: $($drillFails -join ', ')"
        # Fast-fail on critical-package install failures. The canonical
        # import verification runs in Section 9 (scripts\verify_install.py)
        # and is the single source of truth; this gate is belt-and-suspenders
        # for the case where pip returns non-zero before Section 9 runs.
        # Keep aligned with scripts\verify_install.py::CRITICAL_IMPORTS.
        $criticalBlock = @(
            "torch", "numpy", "pyarrow", "lancedb",
            "sentence-transformers", "sentence_transformers",
            "gliner", "openai", "fastapi", "lxml"
        )
        $criticalHits = @()
        foreach ($f in $drillFails) {
            $name = (($f -split '[=<>!~\s]')[0]).ToLower()
            if ($criticalBlock -contains $name) { $criticalHits += $f }
        }
        if ($criticalHits.Count -gt 0) {
            Write-Fail "Critical package install failures: $($criticalHits -join ', ')"
            Write-Info "These are required for HybridRAG V2 to run. Aborting install."
            Write-Info "Diagnose with: .venv\Scripts\python.exe scripts\verify_install.py"
            exit 1
        }
    } else {
        Write-Ok "All packages installed via drill-down"
    }
}

# ============================================================
# 8. Verify CUDA torch
# ============================================================
Write-Step "Verifying CUDA torch"
$verifyPy = Join-Path $env:TEMP "v2_verify_cuda.py"
$verifyCode = @'
import torch
cuda = torch.cuda.is_available()
count = torch.cuda.device_count()
ver = torch.__version__
print(f"torch {ver}, CUDA={cuda}, devices={count}")
if not cuda:
    raise SystemExit(1)
'@
[System.IO.File]::WriteAllText($verifyPy, $verifyCode, [System.Text.UTF8Encoding]::new($false))
$cudaCheck = & $VenvPython $verifyPy 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok $cudaCheck
} elseif (-not $RequireCuda) {
    Write-Warn "torch CUDA not available: $cudaCheck"
    Write-Info "CPU-only fallback is acceptable on machines without NVIDIA GPUs"
} else {
    Write-Fail "torch CUDA not available: $cudaCheck"
    exit 1
}
Remove-TempFileQuietly -Path $verifyPy

# ============================================================
# 9. Verify critical imports (delegated to scripts\verify_install.py)
# ============================================================
# This section deliberately does NOT maintain its own hand-rolled import
# list. scripts\verify_install.py::CRITICAL_IMPORTS is the single source
# of truth -- adding a parallel list here would silently drift out of sync
# (which is exactly the bug that silently skipped gliner on the walk-away
# workstation run on 2026-04-12). Keep it delegated.
Write-Step "Verifying critical imports (scripts\verify_install.py)"
$verifyScript = Join-Path $ProjectRoot "scripts\verify_install.py"
if (-not (Test-Path $verifyScript)) {
    Write-Fail "verify_install.py not found at $verifyScript"
    exit 1
}

$verifyOutput = & $VenvPython $verifyScript 2>&1
$verifyExit = $LASTEXITCODE
$verifyText = ($verifyOutput | Out-String).TrimEnd()
if ($verifyText) { Write-Host $verifyText }

if ($verifyExit -eq 0) {
    Write-Ok "All critical imports verified via scripts\verify_install.py"
} else {
    Write-Warn "verify_install.py reported failures -- attempting one-pass recovery"
    & $VenvPip install -r $reqFile @TrustedHosts 2>&1 | Out-Null

    # Torch CUDA integrity re-check after recovery-path pip install.
    # verify_install.py only checks that torch IMPORTS; it does NOT verify
    # torch.cuda.is_available() or the +cu128 lane (see
    # scripts\verify_install.py:79 / CRITICAL_IMPORTS). The recovery
    # `pip install -r requirements.txt` can pull a CPU-only or older torch
    # wheel transitively (gliner / sentence-transformers / huggingface-hub)
    # and silently clobber the cu128 build that Section 6 installed. Detect
    # that here BEFORE re-running verify_install.py so auto-repair fires on
    # the exact failure mode CoPilot+ QA flagged on commit 0987126.
    if ($RequireCuda) {
        & $VenvPython -c "import sys, torch; sys.exit(0 if (torch.cuda.is_available() and '+cu128' in torch.__version__) else 1)" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Recovery pip install dropped CUDA torch -- auto-repairing cu128 lane"
            $cudaRepair = Invoke-WithRetry -Label "torch cu128 recovery auto-repair" -Action {
                & $VenvPip install "torch==2.7.1" --index-url https://download.pytorch.org/whl/cu128 --force-reinstall --no-deps @TrustedHosts --quiet 2>&1 | Out-Null
            }
            if (-not $cudaRepair) {
                Write-Fail "torch cu128 auto-repair failed after 3 attempts"
                Write-TorchInstallGuidance -RepoName "HybridRAG V2" -RuntimeInfo $RuntimeInfo -CudaExpected
                exit 1
            }
            & $VenvPython -c "import sys, torch; sys.exit(0 if (torch.cuda.is_available() and '+cu128' in torch.__version__) else 1)" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Fail "torch still not cu128 / CUDA-capable after recovery auto-repair"
                Write-Info "Diagnose with: .venv\Scripts\python.exe -c ""import torch; print(torch.__version__, torch.cuda.is_available())"""
                exit 1
            }
            Write-Ok "torch cu128 lane restored after recovery-path auto-repair"
        } else {
            Write-Ok "torch cu128 lane preserved through recovery pip install"
        }
    }

    $verifyOutput2 = & $VenvPython $verifyScript 2>&1
    $verifyExit2 = $LASTEXITCODE
    $verifyText2 = ($verifyOutput2 | Out-String).TrimEnd()
    if ($verifyText2) { Write-Host $verifyText2 }
    if ($verifyExit2 -eq 0) {
        Write-Ok "All critical imports verified after recovery"
    } else {
        Write-Fail "Critical imports still broken after recovery pass"
        Write-Info "Diagnose with: .venv\Scripts\python.exe scripts\verify_install.py"
        exit 1
    }
}

# ============================================================
# 10. Check Ollama
# ============================================================
Write-Step "Checking Ollama service"
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:11434/api/version" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    Write-Ok "Ollama running: $($resp.Content)"
} catch {
    Write-Warn "Ollama not reachable at localhost:11434 -- start with 'ollama serve' if needed"
}

# ============================================================
# 11. Check phi4 model
# ============================================================
Write-Step "Checking phi4 model"
try {
    $models = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    if ($models.Content -match "phi4") {
        Write-Ok "phi4 model found"
    } else {
        Write-Warn "phi4 not found -- pull with: ollama pull phi4:14b-q4_K_M"
    }
} catch {
    Write-Warn "Could not query Ollama models (service may be down)"
}

# ============================================================
# 12. Environment summary
# ============================================================
Write-Step "Setting environment variables"
$env:CUDA_VISIBLE_DEVICES = "0"
$env:PYTHONUTF8 = "1"
Write-Ok "CUDA_VISIBLE_DEVICES=0, PYTHONUTF8=1, NO_PROXY=localhost,127.0.0.1"
Write-Info "Project root: $ProjectRoot"
Write-Info "pip.ini: $PipIni"
Write-Info "Python: $VenvPython"

# ============================================================
# 13. Verify config loads
# ============================================================
Write-Step "Verifying config/config.yaml loads"
$cfgPy = Join-Path $env:TEMP "v2_verify_config.py"
$cfgCode = @'
import sys
sys.path.insert(0, ".")
from src.config.schema import load_config
cfg = load_config()
print("Config loaded OK")
'@
[System.IO.File]::WriteAllText($cfgPy, $cfgCode, [System.Text.UTF8Encoding]::new($false))
$configCheck = & $VenvPython $cfgPy 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok $configCheck
} else {
    Write-Fail "Config load failed: $configCheck"
}
Remove-TempFileQuietly -Path $cfgPy

# ============================================================
# 14. Verify LanceDB store initializes
# ============================================================
Write-Step "Verifying LanceDB store"
$lancePy = Join-Path $env:TEMP "v2_verify_lance.py"
$lanceCode = @'
import lancedb, tempfile, os
db = lancedb.connect(os.path.join(tempfile.gettempdir(), "hybridrag_test_lancedb"))
print("LanceDB OK")
'@
[System.IO.File]::WriteAllText($lancePy, $lanceCode, [System.Text.UTF8Encoding]::new($false))
$lanceCheck = & $VenvPython $lancePy 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok $lanceCheck
} else {
    Write-Fail "LanceDB init failed: $lanceCheck"
}
Remove-TempFileQuietly -Path $lancePy

# ============================================================
# 15. Check API key
# ============================================================
Write-Step "Checking API keys"
$hasKey = $false
if ($env:OPENAI_API_KEY) {
    Write-Ok "OPENAI_API_KEY is set (length=$($env:OPENAI_API_KEY.Length))"
    $hasKey = $true
}
if ($env:AZURE_OPENAI_API_KEY) {
    Write-Ok "AZURE_OPENAI_API_KEY is set (length=$($env:AZURE_OPENAI_API_KEY.Length))"
    $hasKey = $true
}
if (-not $hasKey) {
    Write-Warn "No OPENAI_API_KEY or AZURE_OPENAI_API_KEY found -- set before running pipeline"
}

# ============================================================
# 16. Embedding smoke test
# ============================================================
Write-Step "Running embedding smoke test"
$smokePy = Join-Path $env:TEMP "hybridrag_smoke_test.py"
$smokeCode = @'
import torch
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True, device="cuda")
emb = model.encode(["search_document: HybridRAG V2 smoke test"])
assert emb.shape[1] == 768, f"Expected dim 768, got {emb.shape[1]}"
print(f"Embedding OK: device=cuda, dim={emb.shape[1]}, dtype={emb.dtype}")
'@
[System.IO.File]::WriteAllText($smokePy, $smokeCode, [System.Text.UTF8Encoding]::new($false))
$smokeResult = & $VenvPython $smokePy 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok $smokeResult
} else {
    Write-Fail "Embedding smoke test failed: $smokeResult"
}
Remove-TempFileQuietly -Path $smokePy

# ============================================================
# 17. Run validate_setup.py
# ============================================================
Write-Step "Running validate_setup.py"
$validateScript = Join-Path $ProjectRoot "scripts\validate_setup.py"
if (Test-Path $validateScript) {
    $optionalValidateFails = @("Tesseract OCR", "Poppler (pdftoppm)", "API key")
    $validateResult = & $VenvPython -W ignore::DeprecationWarning $validateScript --json 2>&1
    $validateText = ($validateResult | Out-String).Trim()
    $jsonStart = $validateText.IndexOf("{")
    $jsonEnd = $validateText.LastIndexOf("}")

    if ($jsonStart -ge 0 -and $jsonEnd -ge $jsonStart) {
        try {
            $jsonText = $validateText.Substring($jsonStart, $jsonEnd - $jsonStart + 1)
            $validateJson = $jsonText | ConvertFrom-Json -Depth 6
            $blockingFails = @($validateJson.checks | Where-Object {
                $_.level -eq "FAIL" -and $_.label -notin $optionalValidateFails
            })
            $nonBlockingFails = @($validateJson.checks | Where-Object {
                $_.level -eq "FAIL" -and $_.label -in $optionalValidateFails
            })

            if ($blockingFails.Count -eq 0) {
                if ($nonBlockingFails.Count -gt 0) {
                    Write-Warn ("validate_setup.py found non-blocking external prerequisites: {0}" -f (($nonBlockingFails | ForEach-Object { $_.label }) -join ", "))
                } else {
                    Write-Ok "validate_setup.py passed"
                }
            } else {
                Write-Fail ("validate_setup.py found blocking issues: {0}" -f (($blockingFails | ForEach-Object { $_.label }) -join ", "))
            }
            Write-Info $validateText
        } catch {
            Write-Fail "validate_setup.py JSON parse failed"
            Write-Info $validateText
        }
    } elseif ($LASTEXITCODE -eq 0) {
        Write-Ok "validate_setup.py passed"
        Write-Info $validateText
    } else {
        Write-Fail "validate_setup.py failed"
        Write-Info $validateText
    }
} else {
    Write-Warn "validate_setup.py not found at $validateScript -- skipping"
}

# ============================================================
# 18. Final summary
# ============================================================
$Stopwatch.Stop()
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  HybridRAG V2 Workstation Setup Complete -- $(Format-Elapsed)" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  PASS: $global:PassCount" -ForegroundColor Green
if ($global:WarnCount -gt 0) { Write-Host "  WARN: $global:WarnCount" -ForegroundColor Yellow }
if ($global:FailCount -gt 0) { Write-Host "  FAIL: $global:FailCount" -ForegroundColor Red }
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($global:FailCount -gt 0) {
    Write-Host "`n  Setup completed with failures. Review output above." -ForegroundColor Red
    Wait-ForOperator -Message "Press any key to exit"
    exit 1
} else {
    Write-Host "`n  Environment ready. Activate with:" -ForegroundColor Green
    Write-Host '    .venv\Scripts\activate' -ForegroundColor White
    Wait-ForOperator -Message "Press any key to exit"
    exit 0
}
