# NON-PROGRAMMER GUIDE
# Purpose: Runs the dated PowerShell workstation setup flow for this repo.
# How to follow: Read the top help block first, then run it from PowerShell with the needed flags.
# Inputs: This repo checkout and the workstation prerequisites described in the script.
# Outputs: A configured local workstation environment.
#
#Requires -Version 5.1
<#
.SYNOPSIS
    HybridRAG V2 -- Canonical workstation installer (detect-first).
.DESCRIPTION
    Installs venv, CUDA torch, requirements, and verifies the environment.
    Designed for workstation installs (Python 3.12, CUDA 12.8 lane when NVIDIA is present).
    Detect-first: every section checks what is already present before changing
    state, pauses at meaningful checkpoints, and never pops-and-disappears
    on failure.

.PARAMETER DryRun
    Report the full environment inventory and exit 0 without making any
    changes. Use this before committing to an install to see what is already
    present on the workstation. Alias: -DetectOnly.

.PARAMETER NoPause
    Bypass all operator pauses. Equivalent to setting HYBRIDRAG_NO_PAUSE=1.
    Intended for CI / unattended walk-away runs only -- interactive installs
    should leave the pauses in place so operators can see inventory before
    any state changes.

.NOTES
    Author: Jeremy Randall
    Date:   2026-04-12

    Single source of truth for critical dependency verification:
      scripts\verify_install.py (see CRITICAL_IMPORTS list)

    Any new critical runtime dependency goes in requirements.txt AND in
    scripts\verify_install.py::CRITICAL_IMPORTS. Do NOT add a parallel
    hand-rolled package list here -- Section 9 below delegates the entire
    import check to verify_install.py so the two paths cannot drift.
    Reference: commit 8a1361d introduced verify_install.py as the canonical
    install gate; 0987126 wired this script into it; 1225464 added the
    Section 9 recovery-path CUDA torch integrity guard; the Commit B
    operator UX polish below (DryRun, pre-flight inventory, Section 7.5
    bulk-install CUDA guard, HF_TOKEN, state buckets, skip-on-failure
    prompts) lands on the new dated filename after the 2026-04-06 pathname
    became externally blocked at the filesystem layer on 2026-04-12.
#>
[CmdletBinding()]
param(
    [Alias("DetectOnly")]
    [switch]$DryRun,
    [switch]$NoPause
)

if ($NoPause) { $env:HYBRIDRAG_NO_PAUSE = "1" }

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
    # Write the probe to a temp .py file instead of python -c with a multi-
    # line here-string. Windows argv quoting mangles embedded newlines and
    # Python sees the dict literal's inner lines out of context, raising
    # NameError. The pre-flight inventory table would then silently show
    # "Python (repo) <unknown>" on every run even on a healthy venv, which
    # masks the real install state. Temp-file pattern matches Section 8/13/
    # 14/16 below.
    $probePy = Join-Path $env:TEMP "v2_probe_python_runtime.py"
    $probeCode = @'
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
        [System.IO.File]::WriteAllText($probePy, $probeCode, [System.Text.UTF8Encoding]::new($false))
        $raw = & $PythonExe $probePy 2>$null
        Remove-TempFileQuietly -Path $probePy
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) { return $null }
        return ($raw | ConvertFrom-Json)
    } catch {
        Remove-TempFileQuietly -Path $probePy
        return $null
    }
}

function Get-PyLauncherRuntimeInfo {
    $probePy = Join-Path $env:TEMP "v2_probe_python_runtime_launcher.py"
    $probeCode = @'
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
        [System.IO.File]::WriteAllText($probePy, $probeCode, [System.Text.UTF8Encoding]::new($false))
        $raw = & py -3.12 $probePy 2>$null
        Remove-TempFileQuietly -Path $probePy
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) { return $null }
        return ($raw | ConvertFrom-Json)
    } catch {
        Remove-TempFileQuietly -Path $probePy
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

function Get-RequirementName {
    param([string]$Requirement)
    if ([string]::IsNullOrWhiteSpace($Requirement)) { return "" }
    $req = $Requirement.Trim()
    $req = ($req -split '\[')[0]
    return (($req -split '[=<>!~\s]')[0]).Trim().ToLower()
}

function Install-GlinerDrilldownFallback {
    param(
        [string]$PythonExe,
        [string]$GlinerRequirement,
        [string[]]$CommonArgs
    )
    $glinerDeps = @(
        "huggingface_hub>=0.21.4",
        "onnxruntime",
        "sentencepiece",
        "tqdm",
        "transformers>=4.51.3,<5.2.0"
    )

    Write-Warn "  GLiNER install failed -- retrying with explicit dependency bootstrap"
    foreach ($dep in $glinerDeps) {
        Write-Info "    GLiNER bootstrap dep: $dep"
        & $PythonExe -m pip install $dep @CommonArgs --quiet 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "    GLiNER bootstrap dep failed: $dep"
            return $false
        }
    }

    Write-Info "    Retrying GLiNER wheel install with --no-deps"
    & $PythonExe -m pip install --no-deps $GlinerRequirement @CommonArgs --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "    GLiNER --no-deps retry failed"
        return $false
    }

    Write-Ok "  GLiNER installed after dependency bootstrap"
    return $true
}

# ---------------------------------------------------------------------------
# Inventory helpers -- non-destructive detection only. Called from the
# pre-flight inventory (Section 4.5) BEFORE any install step runs, and
# populate $global:Inventory so the final summary can report a proper
# breakdown of what was already present vs. installed vs. repaired vs.
# skipped. Also supply Read-OperatorChoice so the hard-fail exit points
# in Sections 7, 7.5, and 9 can offer a skip-on-failure prompt instead
# of an unconditional exit 1.
# ---------------------------------------------------------------------------

$global:Inventory = [ordered]@{}
$global:StateLog = @{
    AlreadyPresent = [System.Collections.Generic.List[string]]::new()
    Installed      = [System.Collections.Generic.List[string]]::new()
    Repaired       = [System.Collections.Generic.List[string]]::new()
    Skipped        = [System.Collections.Generic.List[string]]::new()
}

function Add-StateLog {
    param(
        [ValidateSet("AlreadyPresent","Installed","Repaired","Skipped")]
        [string]$Bucket,
        [string]$Item
    )
    $global:StateLog[$Bucket].Add($Item) | Out-Null
}

function Read-OperatorChoice {
    param(
        [string]$Prompt,
        [string[]]$Options = @("R","S","E"),
        [string]$Default = "E"
    )
    if ($env:HYBRIDRAG_NO_PAUSE -eq "1") { return $Default }
    $upper = $Options | ForEach-Object { $_.ToUpper() }
    Write-Host ""
    Write-Host "  $Prompt" -ForegroundColor White
    Write-Host ("  Options: [" + ($upper -join "/") + "]  (default=$Default)") -ForegroundColor Gray
    try {
        $key = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        $char = $key.Character.ToString().ToUpper()
        if ($upper -contains $char) {
            Write-Host "  -> $char" -ForegroundColor Gray
            return $char
        }
    } catch { }
    Write-Host "  -> $Default (default)" -ForegroundColor Gray
    return $Default
}

function Get-DiskFreeGB {
    param([string]$Path)
    try {
        $item = Get-Item -LiteralPath $Path -ErrorAction Stop
        $drive = $item.PSDrive
        if (-not $drive) { return $null }
        $free = (Get-PSDrive -Name $drive.Name -ErrorAction Stop).Free
        if ($null -eq $free) { return $null }
        return [math]::Round($free / 1GB, 1)
    } catch {
        return $null
    }
}

function Get-WindowsInfo {
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    } catch {
        try {
            $os = Get-WmiObject Win32_OperatingSystem -ErrorAction Stop
        } catch {
            return $null
        }
    }
    return [pscustomobject]@{
        Caption      = $os.Caption
        Version      = $os.Version
        BuildNumber  = $os.BuildNumber
        Architecture = $os.OSArchitecture
    }
}

function Get-NvidiaDriverInfo {
    try {
        $raw = & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        return (($raw | Out-String).Trim() -split "`n" | ForEach-Object { $_.Trim() }) -join " | "
    } catch {
        return $null
    }
}

function Test-TorchCuda128 {
    param([string]$PythonExe)
    if (-not (Test-Path $PythonExe)) { return $null }
    # Write the probe to a temp .py file instead of using python -c with a
    # here-string. Multi-line -c arguments get their newlines mangled by the
    # Windows argv quoting layer and Python then sees the dict literal's
    # inner lines out of context, failing with a NameError. Temp-file
    # pattern matches Section 8/13/14/16 below.
    $probePy = Join-Path $env:TEMP "v2_probe_torch_cuda.py"
    $probeCode = @'
import json, sys
try:
    import torch
    info = {
        "installed": True,
        "version": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "is_cu128": "+cu128" in torch.__version__,
        "is_271": torch.__version__.startswith("2.7.1"),
    }
except ImportError:
    info = {"installed": False}
except Exception as e:
    info = {"installed": False, "error": str(e)}
print(json.dumps(info))
'@
    try {
        [System.IO.File]::WriteAllText($probePy, $probeCode, [System.Text.UTF8Encoding]::new($false))
        $raw = & $PythonExe $probePy 2>$null
        Remove-TempFileQuietly -Path $probePy
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) { return $null }
        return ($raw | ConvertFrom-Json)
    } catch {
        Remove-TempFileQuietly -Path $probePy
        return $null
    }
}

function Test-OllamaReachable {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:11434/api/version" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return $resp.Content.Trim()
    } catch {
        return $null
    }
}

function Test-Phi4Available {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return ($resp.Content -match "phi4")
    } catch {
        return $false
    }
}

function Get-HFTokenStatus {
    if ($env:HF_TOKEN) { return "env HF_TOKEN set (length=$($env:HF_TOKEN.Length))" }
    if ($env:HUGGINGFACE_HUB_TOKEN) { return "env HUGGINGFACE_HUB_TOKEN set (length=$($env:HUGGINGFACE_HUB_TOKEN.Length))" }
    try {
        $cred = & cmdkey /list 2>$null | Select-String -Pattern "huggingface" -SimpleMatch
        if ($cred) { return "Windows Credential Manager entry present" }
    } catch { }
    return "not found (anonymous HuggingFace downloads only)"
}

function Write-InventoryTable {
    param($Inv)
    Write-Host ""
    Write-Host "  Workstation inventory:" -ForegroundColor Cyan
    Write-Host ("  " + ("-" * 64)) -ForegroundColor DarkGray
    foreach ($key in $Inv.Keys) {
        $val = $Inv[$key]
        if ($null -eq $val) { $val = "<unknown>" }
        $padded = $key.PadRight(22)
        Write-Host "  $padded $val" -ForegroundColor Gray
    }
    Write-Host ("  " + ("-" * 64)) -ForegroundColor DarkGray
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
# 4. Prepare .venv
# ============================================================
Write-Step "Preparing virtual environment"
$VenvDir    = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip    = Join-Path $VenvDir "Scripts\pip.exe"
$PipIni     = Join-Path $VenvDir "pip.ini"
$ProxyInfo  = Get-WorkstationProxyInfo
$RequireCuda = Test-NvidiaGpuPresent
$RuntimeInfo = $null
$VenvWasCreated = $false

if (Test-Path $VenvPython) {
    Write-Ok ".venv already exists"
} else {
    if ($DryRun) {
        Write-Info ".venv not present; -DryRun will not create it."
    } else {
        $ok = Invoke-WithRetry -Label "py -3.12 -m venv .venv" -Action {
            & py -3.12 -m venv "$VenvDir"
        }
        if ($ok) {
            $VenvWasCreated = $true
            Write-Ok ".venv created"
        } else {
            Write-Fail "Could not create .venv"
            exit 1
        }
    }
}

if (Test-Path $VenvPython) {
    # Activate (for this process only)
    $env:VIRTUAL_ENV = $VenvDir
    $env:PATH = (Join-Path $VenvDir "Scripts") + ";" + $env:PATH
    $RuntimeInfo = Get-PythonRuntimeInfo -PythonExe $VenvPython

    if (-not $DryRun) {
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
    } else {
        if ($ProxyInfo.ProxyDetected) {
            Write-Info "Proxy detected ($($ProxyInfo.Source)): $($ProxyInfo.ProxyUrl)"
        } elseif (-not [string]::IsNullOrWhiteSpace($ProxyInfo.AutoConfigUrl)) {
            Write-Info "PAC proxy detected: $($ProxyInfo.AutoConfigUrl)"
        } else {
            Write-Info "No workstation proxy detected; pip would use direct internet"
        }
    }
} else {
    if ($ProxyInfo.ProxyDetected) {
        Write-Info "Proxy detected ($($ProxyInfo.Source)): $($ProxyInfo.ProxyUrl)"
    } elseif (-not [string]::IsNullOrWhiteSpace($ProxyInfo.AutoConfigUrl)) {
        Write-Info "PAC proxy detected: $($ProxyInfo.AutoConfigUrl)"
    } else {
        Write-Info "No workstation proxy detected; pip would use direct internet"
    }
    $RuntimeInfo = Get-PyLauncherRuntimeInfo
}

# ============================================================
# 4.5 Assessment Summary
# ============================================================
Write-Step "Pre-flight inventory (detect-first)"

$pipVersionStr = "venv absent"
$pipSystemCertsPresent = $false
$torchInfo = $null
if (Test-Path $VenvPython) {
    $pipVersionOutput = & $VenvPython -m pip --version 2>&1
    $pipVersionStr = (($pipVersionOutput | Out-String).Trim())
    $pipSystemCertsSummary = & $VenvPython -m pip show pip-system-certs 2>&1
    $pipSystemCertsPresent = ($LASTEXITCODE -eq 0 -and $pipSystemCertsSummary -notmatch "Package\(s\) not found")
    $torchInfo = Test-TorchCuda128 -PythonExe $VenvPython
}
$winInfo = Get-WindowsInfo
$diskFree = Get-DiskFreeGB -Path $ProjectRoot
$nvidiaInfo = Get-NvidiaDriverInfo
$ollamaVersion = Test-OllamaReachable
$phi4Present = Test-Phi4Available
$hfStatus = Get-HFTokenStatus

$global:Inventory = [ordered]@{
    "Windows"           = if ($winInfo) { "$($winInfo.Caption) $($winInfo.Version) ($($winInfo.Architecture))" } else { "<unknown>" }
    "Disk free"         = if ($null -ne $diskFree) { "$diskFree GB on drive of $ProjectRoot" } else { "<unknown>" }
    "Python (repo)"     = if ($RuntimeInfo) { "$($RuntimeInfo.python_version) $($RuntimeInfo.python_tag) 64-bit=$($RuntimeInfo.is_64bit)" } else { "<unknown>" }
    "venv"              = if (Test-Path $VenvPython) { "present at $VenvDir" } else { "absent" }
    "pip"               = if ($pipVersionStr) { $pipVersionStr } else { "<unknown>" }
    "pip-system-certs"  = if ($pipSystemCertsPresent) { "installed" } else { "missing" }
    "Proxy"             = if ($ProxyInfo.ProxyDetected) { "$($ProxyInfo.Source): $($ProxyInfo.ProxyUrl)" } elseif ($ProxyInfo.AutoConfigUrl) { "PAC: $($ProxyInfo.AutoConfigUrl)" } else { "direct / not detected" }
    "NVIDIA GPU"        = if ($nvidiaInfo) { $nvidiaInfo } else { "none detected" }
    "CUDA required"     = if ($RequireCuda) { "yes (NVIDIA present)" } else { "no (CPU fallback lane)" }
    "torch"             = if ($torchInfo -and $torchInfo.installed) { "$($torchInfo.version) cuda_available=$($torchInfo.cuda_available) is_cu128=$($torchInfo.is_cu128)" } elseif ($torchInfo) { "not installed" } else { "venv missing" }
    "Ollama service"    = if ($ollamaVersion) { $ollamaVersion } else { "not reachable at localhost:11434" }
    "phi4 model"        = if ($phi4Present) { "present" } else { "not pulled" }
    "HF token"          = $hfStatus
}

# Seed the StateLog "AlreadyPresent" bucket from the inventory so the
# final summary can distinguish what was already OK from what got
# installed or repaired by this run.
if ($pipSystemCertsPresent) { Add-StateLog -Bucket "AlreadyPresent" -Item "pip-system-certs" }
if ($torchInfo -and $torchInfo.installed -and $torchInfo.is_cu128 -and $torchInfo.cuda_available) {
    Add-StateLog -Bucket "AlreadyPresent" -Item "torch $($torchInfo.version) (cu128, CUDA available)"
}
if ($ollamaVersion) { Add-StateLog -Bucket "AlreadyPresent" -Item "Ollama service" }
if ($phi4Present)   { Add-StateLog -Bucket "AlreadyPresent" -Item "phi4 model" }

Write-InventoryTable -Inv $global:Inventory

# Low-disk advisory (not fatal)
if ($null -ne $diskFree -and $diskFree -lt 10) {
    Write-Warn "Less than 10 GB free on $ProjectRoot -- install may fail mid-way"
}

# -DryRun early exit: report inventory and exit cleanly with no state changes.
if ($DryRun) {
    Write-Host ""
    Write-Host "  -DryRun mode: inventory reported above, no install actions performed." -ForegroundColor Yellow
    Write-Host "  Re-run without -DryRun to install missing layers." -ForegroundColor Yellow
    $Stopwatch.Stop()
    Write-Host "  Elapsed: $(Format-Elapsed)" -ForegroundColor Gray
    Wait-ForOperator -Message "Press any key to exit"
    exit 0
}

Write-Info "Next phase will repair only missing or broken layers"
Wait-ForOperator -Message "Press any key to continue with workstation repair, Ctrl+C to abort"

# ============================================================
# 5. Upgrade pip + pip-system-certs
# ============================================================
Write-Step "Upgrading pip and installing pip-system-certs"
if ($VenvWasCreated) {
    Write-Info "Fresh venv detected -- upgrading pip before package installs."
    Write-Info "This step can sit quietly for a minute or two on slower links while pip negotiates certs/proxy access."
    Write-Info "Streaming pip output live so a slow install does not look like a hung installer."
    & $VenvPython -m pip install --upgrade pip @TrustedHosts
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "pip upgraded"
    } else {
        Write-Warn "pip upgrade returned non-zero"
    }
} else {
    Write-Ok "pip already present in existing venv -- skipping upgrade"
}

if ($pipSystemCertsPresent) {
    Write-Ok "pip-system-certs already installed -- skipping"
} else {
    Write-Info "Installing pip-system-certs into the venv."
    & $VenvPip install pip-system-certs @TrustedHosts
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "pip-system-certs installed"
    } else {
        Write-Warn "pip-system-certs failed (non-blocking)"
        Write-Info "pip output is shown above. Continuing because pip-system-certs is non-blocking here."
    }
}

# ============================================================
# 6. Install torch CUDA (BEFORE requirements.txt)
# ============================================================
Write-Step "Installing torch"
$torchHealthy = ($torchInfo -and $torchInfo.installed -and $torchInfo.is_271)
$torchHealthyForLane = $false
if ($torchHealthy) {
    if ($RequireCuda) {
        $torchHealthyForLane = ($torchInfo.is_cu128 -and $torchInfo.cuda_available)
    } else {
        $torchHealthyForLane = $true
    }
}

if ($torchHealthyForLane) {
    if ($RequireCuda) {
        Write-Ok "torch CUDA already healthy ($($torchInfo.version)) -- skipping install"
    } else {
        Write-Ok "torch already healthy ($($torchInfo.version)) -- skipping install"
    }
} elseif ($RequireCuda) {
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
$step7PipArgs = @("--disable-pip-version-check") + $TrustedHosts

$ok = Invoke-WithRetry -Label "pip install -r requirements.txt" -Action {
    & $VenvPython -m pip install -r $reqFile @step7PipArgs --quiet 2>&1 | Out-Null
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
        & $VenvPython -m pip install $pkg @step7PipArgs --quiet 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            $pkgName = Get-RequirementName -Requirement $pkg
            if ($pkgName -eq "gliner") {
                $glinerRecovered = Install-GlinerDrilldownFallback -PythonExe $VenvPython -GlinerRequirement $pkg -CommonArgs $step7PipArgs
                if (-not $glinerRecovered) {
                    Write-Fail "  Failed: $pkg"
                    $drillFails += $pkg
                }
            } else {
                Write-Fail "  Failed: $pkg"
                $drillFails += $pkg
            }
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
            Write-Info "These are required for HybridRAG V2 to run."
            Write-Info "Diagnose with: .venv\Scripts\python.exe scripts\verify_install.py"
            $choice = Read-OperatorChoice -Prompt "Critical package install failed. [R]etry drill-down once, [S]kip and let verify_install.py catch it later, [E]xit installer?" -Options @("R","S","E") -Default "E"
            if ($choice -eq "R") {
                Write-Info "Retrying drill-down for critical packages..."
                foreach ($pkg in $criticalHits) {
                    $pkgName = Get-RequirementName -Requirement $pkg
                    if ($pkgName -eq "gliner") {
                        $retryOk = Install-GlinerDrilldownFallback -PythonExe $VenvPython -GlinerRequirement $pkg -CommonArgs $step7PipArgs
                        if (-not $retryOk) {
                            Write-Info "Manual workaround:"
                            Write-Host "      .venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org huggingface_hub onnxruntime sentencepiece tqdm ""transformers>=4.51.3,<5.2.0""" -ForegroundColor Gray
                            Write-Host "      .venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-deps gliner==0.2.26" -ForegroundColor Gray
                        }
                    } else {
                        & $VenvPython -m pip install $pkg @step7PipArgs --quiet 2>&1 | Out-Null
                    }
                }
                # Fall through -- Section 9 verify_install.py will catch anything
                # still broken after the retry.
            } elseif ($choice -eq "S") {
                Write-Warn "SKIPPED BY OPERATOR: critical drill-down failure gate"
                Add-StateLog -Bucket "Skipped" -Item "drill-down critical package gate (by operator)"
            } else {
                Wait-ForOperator -Message "Press any key to exit"
                exit 1
            }
        }
    } else {
        Write-Ok "All packages installed via drill-down"
    }
}

# ============================================================
# 7.5 Torch integrity check (bulk-install clobber guard)
# ============================================================
# Complements the Section 9 recovery-path CUDA guard (commit 1225464) by
# catching the same gliner/sentence-transformers/huggingface-hub transitive
# clobber on the MAIN bulk install path. Without this, a clobber would
# bubble up to Section 8's hard exit with no auto-repair attempt. Here we
# detect and auto-repair so Section 8 just confirms the state.
if ($RequireCuda) {
    Write-Step "Verifying torch cu128 lane preserved through bulk requirements install"
    $torchPost = Test-TorchCuda128 -PythonExe $VenvPython
    if ($null -ne $torchPost -and $torchPost.installed -and $torchPost.is_cu128 -and $torchPost.cuda_available) {
        Write-Ok "torch integrity preserved: $($torchPost.version) cuda=$($torchPost.cuda_available)"
    } else {
        $reason = if ($null -eq $torchPost -or -not $torchPost.installed) { "torch not importable" }
                  elseif (-not $torchPost.is_cu128) { "torch version drifted: $($torchPost.version)" }
                  else { "CUDA not available on installed torch" }
        Write-Warn "torch integrity check failed -- $reason"
        Write-Info "Auto-repair: reinstalling torch==2.7.1 from the cu128 index"
        $repaired = Invoke-WithRetry -Label "torch cu128 auto-repair (bulk path)" -Action {
            & $VenvPip install "torch==2.7.1" --index-url https://download.pytorch.org/whl/cu128 --force-reinstall --no-deps @TrustedHosts --quiet 2>&1 | Out-Null
        }
        if (-not $repaired) {
            Write-Fail "torch cu128 auto-repair failed after 3 attempts"
            Write-TorchInstallGuidance -RepoName "HybridRAG V2" -RuntimeInfo $RuntimeInfo -CudaExpected
            $choice = Read-OperatorChoice -Prompt "torch cu128 auto-repair failed. [R]etry once, [S]kip torch integrity check and continue anyway, [E]xit installer?" -Options @("R","S","E") -Default "E"
            if ($choice -eq "R") {
                $repaired2 = Invoke-WithRetry -Label "torch cu128 auto-repair retry" -Action {
                    & $VenvPip install "torch==2.7.1" --index-url https://download.pytorch.org/whl/cu128 --force-reinstall --no-deps @TrustedHosts --quiet 2>&1 | Out-Null
                }
                if (-not $repaired2) {
                    Write-Fail "torch cu128 retry failed"
                    Wait-ForOperator -Message "Press any key to exit"
                    exit 1
                }
            } elseif ($choice -eq "S") {
                Write-Warn "SKIPPED BY OPERATOR: torch cu128 integrity check"
                Add-StateLog -Bucket "Skipped" -Item "torch cu128 bulk-install integrity (by operator)"
            } else {
                Wait-ForOperator -Message "Press any key to exit"
                exit 1
            }
        }
        $torchAfter = Test-TorchCuda128 -PythonExe $VenvPython
        if ($null -ne $torchAfter -and $torchAfter.is_cu128 -and $torchAfter.cuda_available) {
            Write-Ok "torch cu128 restored: $($torchAfter.version)"
            Add-StateLog -Bucket "Repaired" -Item "torch (bulk-install transitive clobber)"
        } elseif ($global:StateLog.Skipped -contains "torch cu128 bulk-install integrity (by operator)") {
            # Operator chose to skip; continue without verifying restored state.
        } else {
            Write-Fail "torch still not cu128 / CUDA-capable after auto-repair"
            Wait-ForOperator -Message "Press any key to exit"
            exit 1
        }
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
# 15. Check API keys + HF token
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

# HuggingFace token is not strictly required (public model downloads work
# anonymously), but rate limits are lower and some gated models require it.
# Report status so operators know whether to set one for this workstation.
$hfFinal = Get-HFTokenStatus
if ($hfFinal -match "^env |Credential Manager") {
    Write-Ok "HuggingFace token: $hfFinal"
} else {
    Write-Warn "HuggingFace token: $hfFinal"
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
Write-Host ("=" * 64) -ForegroundColor Cyan
Write-Host "  HybridRAG V2 Workstation Setup Complete -- $(Format-Elapsed)" -ForegroundColor Cyan
Write-Host ("=" * 64) -ForegroundColor Cyan
Write-Host "  PASS: $global:PassCount" -ForegroundColor Green
if ($global:WarnCount -gt 0) { Write-Host "  WARN: $global:WarnCount" -ForegroundColor Yellow }
if ($global:FailCount -gt 0) { Write-Host "  FAIL: $global:FailCount" -ForegroundColor Red }
Write-Host ("-" * 64) -ForegroundColor DarkGray

function Write-StateBucket {
    param([string]$Label, [System.Collections.Generic.List[string]]$Items, [string]$Color)
    if ($null -eq $Items -or $Items.Count -eq 0) { return }
    Write-Host "  ${Label}:" -ForegroundColor $Color
    foreach ($item in $Items) {
        Write-Host "    - $item" -ForegroundColor $Color
    }
}

Write-StateBucket -Label "Already present" -Items $global:StateLog.AlreadyPresent -Color "Gray"
Write-StateBucket -Label "Installed"       -Items $global:StateLog.Installed      -Color "Green"
Write-StateBucket -Label "Repaired"        -Items $global:StateLog.Repaired       -Color "Yellow"
Write-StateBucket -Label "Skipped"         -Items $global:StateLog.Skipped        -Color "DarkGray"

# Re-run verify_install.py one last time for the final reportable state.
# This is read-only -- the install phases above have already hard-failed
# on anything broken, so this is pure confirmation for the operator.
$finalVerifyOutput = & $VenvPython $verifyScript 2>&1
$finalVerifyExit = $LASTEXITCODE
$finalSummary = if ($finalVerifyExit -eq 0) { "verify_install.py: PASS" } else { "verify_install.py: FAIL (exit $finalVerifyExit)" }
Write-Host "  $finalSummary" -ForegroundColor $(if ($finalVerifyExit -eq 0) { "Green" } else { "Red" })

$finalOllama = Test-OllamaReachable
$finalPhi4 = Test-Phi4Available
Write-Host "  Ollama service: $(if ($finalOllama) { $finalOllama } else { 'not reachable' })" -ForegroundColor Gray
Write-Host "  phi4 model:     $(if ($finalPhi4) { 'present' } else { 'not pulled' })" -ForegroundColor Gray
Write-Host ("=" * 64) -ForegroundColor Cyan

if ($global:FailCount -gt 0 -or $finalVerifyExit -ne 0) {
    Write-Host "`n  Setup completed with failures. Review output above." -ForegroundColor Red
    Wait-ForOperator -Message "Press any key to exit"
    exit 1
} else {
    Write-Host "`n  Environment ready. Activate with:" -ForegroundColor Green
    Write-Host '    .venv\Scripts\activate' -ForegroundColor White
    Wait-ForOperator -Message "Press any key to exit"
    exit 0
}
