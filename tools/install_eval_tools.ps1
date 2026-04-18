#Requires -Version 5.1
<#
.SYNOPSIS
    Proxy-hardened installer for HybridRAG V2 evaluation tools (RAGAS + rapidfuzz).

.DESCRIPTION
    Installs the RAGAS evaluation stack into the HybridRAG V2 .venv with full
    corporate proxy support:
      - Auto-exports CA cert bundle from Windows cert store (X509Store .NET API)
      - Auto-detects proxy from env vars, Windows Registry, or netsh WinHTTP
      - Generates pip.ini with proxy, cert, trusted-host, timeout, retries
      - Pre-flight checks (Python, .venv, CUDA)
      - Post-install verification (import test for each package)
      - HF_HUB_OFFLINE=1 to skip HuggingFace proxy retries
      - Install manifest output

    Adapted from the proven IQT proxy pattern (Apply_IQT_Proxy_Policy.ps1).

.PARAMETER NoPause
    Skip all operator pause points for walk-away/automated runs.

.PARAMETER DryRun
    Show what would be installed without actually installing.

.EXAMPLE
    .\install_eval_tools.ps1
    .\install_eval_tools.ps1 -NoPause
    .\install_eval_tools.ps1 -DryRun
#>
param(
    [switch]$NoPause,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
try {
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue
} catch {}

# ── Globals ──────────────────────────────────────────────────────────────
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvRoot = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$VenvPip = Join-Path $VenvRoot "Scripts\pip.exe"
$RequirementsFile = Join-Path $RepoRoot "requirements_eval_gui.txt"
$CaBundlePath = Join-Path $VenvRoot "ca-bundle.pem"
$PipConfigPath = Join-Path $VenvRoot "pip.ini"
$ManifestPath = Join-Path $RepoRoot "docs\EVAL_TOOLS_INSTALL_MANIFEST.txt"

$TrustedHosts = @("pypi.org", "pypi.python.org", "files.pythonhosted.org")
$PipTimeout = 120
$PipRetries = 5

# Packages to verify after install (import name, display name)
$VerifyPackages = @(
    @{ Import = "ragas"; Name = "ragas" },
    @{ Import = "rapidfuzz"; Name = "rapidfuzz" },
    @{ Import = "datasets"; Name = "datasets" },
    @{ Import = "langchain_core"; Name = "langchain-core" },
    @{ Import = "tiktoken"; Name = "tiktoken" },
    @{ Import = "instructor"; Name = "instructor" },
    @{ Import = "openai"; Name = "openai" }
)

# ── Helpers ──────────────────────────────────────────────────────────────

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "   [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "   [WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "   [FAIL] $Message" -ForegroundColor Red
}

function Pause-IfInteractive {
    if (-not $NoPause -and -not $env:HYBRIDRAG_NO_PAUSE) {
        Write-Host ""
        Write-Host "   Press any key to continue..." -ForegroundColor DarkGray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
}

# ── CA Cert Export (X509Store .NET API) ──────────────────────────────────

function Export-CaCertBundle {
    param([string]$OutputPath)

    if (Test-Path $OutputPath) {
        Write-Ok "CA bundle already exists: $OutputPath"
        return $OutputPath
    }

    try {
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'LocalMachine')
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
        $certs = $store.Certificates

        if ($certs.Count -eq 0) {
            $store.Close()
            Write-Warn "No CA certs found in LocalMachine Root store"
            return $null
        }

        $pemLines = @()
        $exported = 0
        foreach ($cert in $certs) {
            try {
                $b64 = [Convert]::ToBase64String($cert.RawData, [System.Base64FormattingOptions]::InsertLineBreaks)
                $pemLines += "-----BEGIN CERTIFICATE-----"
                $pemLines += $b64
                $pemLines += "-----END CERTIFICATE-----"
                $pemLines += ""
                $exported++
            } catch { continue }
        }
        $store.Close()

        if ($pemLines.Count -gt 0) {
            $parent = Split-Path -Parent $OutputPath
            if ($parent -and -not (Test-Path $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            $utf8 = New-Object System.Text.UTF8Encoding($false)
            [System.IO.File]::WriteAllText($OutputPath, ($pemLines -join "`n"), $utf8)
            Write-Ok "Exported $exported CA certs to: $OutputPath"
            return $OutputPath
        }
    } catch {
        Write-Warn "CA cert export failed: $_"
    }

    return $null
}

# ── Proxy Auto-Detection ────────────────────────────────────────────────

function Get-ProxyFromRegistry {
    $settingsPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    $settings = Get-ItemProperty -Path $settingsPath -ErrorAction SilentlyContinue
    if (-not $settings) { return $null }

    $proxyEnable = 0
    try { $proxyEnable = [int]$settings.ProxyEnable } catch {}

    if ($proxyEnable -ne 1) { return $null }

    $proxyServer = [string]$settings.ProxyServer
    if ([string]::IsNullOrWhiteSpace($proxyServer)) { return $null }

    if ($proxyServer -notmatch "^[a-z][a-z0-9+.-]*://") {
        $proxyServer = "http://$proxyServer"
    }
    return $proxyServer
}

function Get-ProxyFromWinHttp {
    $netsh = Get-Command netsh.exe -ErrorAction SilentlyContinue
    if (-not $netsh) { return $null }

    try {
        $output = & $netsh.Source winhttp show proxy 2>$null
    } catch { return $null }

    if ($LASTEXITCODE -ne 0 -or -not $output) { return $null }
    $joined = ($output -join "`n")
    if ($joined -match "Direct access") { return $null }

    foreach ($line in $output) {
        if ($line -match "Proxy Server\(s\)\s*:\s*(.+)$") {
            $proxy = $Matches[1].Trim()
            if ($proxy -notmatch "^[a-z][a-z0-9+.-]*://") {
                $proxy = "http://$proxy"
            }
            return $proxy
        }
    }
    return $null
}

function Get-AutoProxy {
    # Priority: env vars > Registry > WinHTTP
    if ($env:HTTPS_PROXY) { return @{ Proxy = $env:HTTPS_PROXY; Source = "HTTPS_PROXY env" } }
    if ($env:https_proxy) { return @{ Proxy = $env:https_proxy; Source = "https_proxy env" } }
    if ($env:HTTP_PROXY)  { return @{ Proxy = $env:HTTP_PROXY;  Source = "HTTP_PROXY env"  } }
    if ($env:http_proxy)  { return @{ Proxy = $env:http_proxy;  Source = "http_proxy env"  } }

    $regProxy = Get-ProxyFromRegistry
    if ($regProxy) { return @{ Proxy = $regProxy; Source = "Windows Registry" } }

    $winProxy = Get-ProxyFromWinHttp
    if ($winProxy) { return @{ Proxy = $winProxy; Source = "netsh WinHTTP" } }

    return @{ Proxy = $null; Source = "none detected" }
}

# ── pip.ini Generation ──────────────────────────────────────────────────

function Write-PipConfig {
    param(
        [string]$ConfigPath,
        [string]$Proxy,
        [string]$CertPath
    )

    $lines = @(
        "[global]",
        "disable-pip-version-check = true",
        "timeout = $PipTimeout",
        "retries = $PipRetries"
    )

    if ($Proxy) {
        $lines += "proxy = $Proxy"
    }
    if ($CertPath -and (Test-Path $CertPath)) {
        $lines += "cert = $CertPath"
    }
    if ($TrustedHosts.Count -gt 0) {
        $lines += "trusted-host ="
        foreach ($host_ in $TrustedHosts) {
            $lines += "    $host_"
        }
    }

    $content = ($lines -join "`r`n") + "`r`n"
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($ConfigPath, $content, $utf8)
}

# ── Pre-Flight Checks ──────────────────────────────────────────────────

function Test-PreFlight {
    $ok = $true

    Write-Step "Pre-Flight Checks"

    # Python
    if (Test-Path $VenvPython) {
        $pyVer = & $VenvPython --version 2>&1
        Write-Ok "Python: $pyVer"
    } else {
        Write-Fail "Python not found at: $VenvPython"
        Write-Host "   Run INSTALL_WORKSTATION.bat first to create the .venv."
        $ok = $false
    }

    # .venv
    if (Test-Path $VenvRoot) {
        Write-Ok ".venv exists: $VenvRoot"
    } else {
        Write-Fail ".venv not found: $VenvRoot"
        $ok = $false
    }

    # pip
    if (Test-Path $VenvPip) {
        Write-Ok "pip found: $VenvPip"
    } else {
        Write-Fail "pip not found: $VenvPip"
        $ok = $false
    }

    # Requirements file
    if (Test-Path $RequirementsFile) {
        Write-Ok "Requirements file: $RequirementsFile"
    } else {
        Write-Fail "Requirements file not found: $RequirementsFile"
        $ok = $false
    }

    # CUDA check (informational, not blocking)
    # Note: GPU model name sanitized in output per compliance rules
    try {
        $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
        if ($nvidiaSmi) {
            $gpuCount = & nvidia-smi --query-gpu=count --format=csv,noheader 2>$null
            $gpuMem = & nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>$null
            if ($gpuMem) {
                Write-Ok "CUDA GPU detected: $($gpuMem.Trim())"
            }
        } else {
            Write-Warn "nvidia-smi not found (CUDA not required for eval tools)"
        }
    } catch {
        Write-Warn "Could not check CUDA"
    }

    # Check if RAGAS already installed
    try {
        $ragasCheck = & $VenvPython -c "import ragas; print(ragas.__version__)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ragasCheck) {
            Write-Ok "RAGAS already installed: v$($ragasCheck.Trim())"
            Write-Host "   Re-installing will update to pinned versions." -ForegroundColor DarkGray
        }
    } catch {}

    return $ok
}

# ── Install ─────────────────────────────────────────────────────────────

function Install-EvalTools {
    Write-Step "Installing Eval Tools"

    # Set offline env vars to skip HuggingFace/Transformers proxy retries during install
    $env:HF_HUB_OFFLINE = "1"
    $env:TRANSFORMERS_OFFLINE = "1"
    $env:HF_DATASETS_OFFLINE = "1"
    Write-Ok "HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, HF_DATASETS_OFFLINE=1"

    if ($DryRun) {
        Write-Warn "DRY RUN -- would install from: $RequirementsFile"
        Get-Content $RequirementsFile | Where-Object { $_ -match "^[a-zA-Z]" } | ForEach-Object {
            Write-Host "   Would install: $_" -ForegroundColor DarkGray
        }
        return $true
    }

    Write-Host "   Installing from: $RequirementsFile" -ForegroundColor DarkGray
    Write-Host "   This may take several minutes behind a proxy..." -ForegroundColor DarkGray
    Write-Host ""

    # Primary: try --use-feature=truststore (pip 23.3+, uses Windows CryptoAPI directly)
    # Fallback: standard pip with CA bundle + trusted-host from pip.ini
    $pipVer = & $VenvPip --version 2>$null
    $useTruststore = $false
    if ($pipVer -match "pip (\d+)\.(\d+)") {
        $pipMajor = [int]$Matches[1]
        $pipMinor = [int]$Matches[2]
        if ($pipMajor -gt 23 -or ($pipMajor -eq 23 -and $pipMinor -ge 3)) {
            $useTruststore = $true
        }
    }

    if ($useTruststore) {
        Write-Ok "pip >= 23.3 detected -- using truststore (Windows CryptoAPI)"
        & $VenvPip install --use-feature=truststore -r $RequirementsFile 2>&1 | ForEach-Object {
            if ($_ -match "Successfully installed") { Write-Ok $_ }
            elseif ($_ -match "ERROR|error|FAIL") { Write-Fail $_ }
            elseif ($_ -match "already satisfied") {}
            else { Write-Host "   $_" -ForegroundColor DarkGray }
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Truststore install failed -- falling back to CA bundle + trusted-host"
            $useTruststore = $false
        }
    }

    if (-not $useTruststore) {
        Write-Host "   Using CA bundle + trusted-host fallback" -ForegroundColor DarkGray
        & $VenvPip install -r $RequirementsFile 2>&1 | ForEach-Object {
            if ($_ -match "Successfully installed") {
                Write-Ok $_
            } elseif ($_ -match "ERROR|error|FAIL") {
                Write-Fail $_
            } elseif ($_ -match "already satisfied") {
                # Suppress noisy "already satisfied" lines
            } else {
                Write-Host "   $_" -ForegroundColor DarkGray
            }
        }
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "pip install failed with exit code $LASTEXITCODE"
        return $false
    }

    Write-Ok "pip install completed"
    return $true
}

# ── Post-Install Verification ───────────────────────────────────────────

function Test-PostInstall {
    Write-Step "Post-Install Verification"
    $allOk = $true
    $manifest = @()
    $manifest += "HybridRAG V2 Eval Tools Install Manifest"
    $manifest += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $manifest += "Machine: $env:COMPUTERNAME"
    $manifest += ""

    foreach ($pkg in $VerifyPackages) {
        try {
            $ver = & $VenvPython -c "import $($pkg.Import); print($($pkg.Import).__version__)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver) {
                Write-Ok "$($pkg.Name) v$($ver.Trim())"
                $manifest += "$($pkg.Name)==$($ver.Trim())  [OK]"
            } else {
                Write-Fail "$($pkg.Name) -- import failed"
                $manifest += "$($pkg.Name)  [FAIL - import error]"
                $allOk = $false
            }
        } catch {
            Write-Fail "$($pkg.Name) -- $_"
            $manifest += "$($pkg.Name)  [FAIL - $_]"
            $allOk = $false
        }
    }

    # Write manifest
    $manifest += ""
    $manifest += "Proxy: $($proxyInfo.Proxy) (source: $($proxyInfo.Source))"
    $manifest += "CA Bundle: $(if (Test-Path $CaBundlePath) { $CaBundlePath } else { 'not created' })"
    $manifest += "pip.ini: $(if (Test-Path $PipConfigPath) { $PipConfigPath } else { 'not created' })"

    try {
        $manifestDir = Split-Path -Parent $ManifestPath
        if (-not (Test-Path $manifestDir)) {
            New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
        }
        $manifest -join "`r`n" | Set-Content -Path $ManifestPath -Encoding UTF8
        Write-Ok "Manifest written: $ManifestPath"
    } catch {
        Write-Warn "Could not write manifest: $_"
    }

    return $allOk
}

# ── Main ────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "========================================================================"
Write-Host "  HybridRAG V2 -- Eval Tools Install (RAGAS + rapidfuzz)"
Write-Host "========================================================================"
Write-Host "  Repo:   $RepoRoot"
Write-Host "  .venv:  $VenvRoot"
Write-Host ""

# 1. Pre-flight
$preFlightOk = Test-PreFlight
if (-not $preFlightOk) {
    Write-Fail "Pre-flight checks failed. Fix issues above and re-run."
    Pause-IfInteractive
    exit 1
}
Pause-IfInteractive

# 2. CA cert export
Write-Step "CA Certificate Export"
$caBundle = Export-CaCertBundle -OutputPath $CaBundlePath
if ($caBundle) {
    $env:PIP_CERT = $caBundle
    $env:SSL_CERT_FILE = $caBundle
    $env:REQUESTS_CA_BUNDLE = $caBundle
    Write-Ok "Certificate env vars set"
} else {
    Write-Warn "No CA bundle -- relying on trusted-host only"
}

# 3. Proxy detection
Write-Step "Proxy Detection"
$proxyInfo = Get-AutoProxy
if ($proxyInfo.Proxy) {
    Write-Ok "Proxy: $($proxyInfo.Proxy) (source: $($proxyInfo.Source))"
    $env:HTTP_PROXY = $proxyInfo.Proxy
    $env:HTTPS_PROXY = $proxyInfo.Proxy
} else {
    Write-Ok "No proxy detected -- direct connection"
}

# 4. pip.ini generation
Write-Step "pip.ini Configuration"
Write-PipConfig -ConfigPath $PipConfigPath -Proxy $proxyInfo.Proxy -CertPath $caBundle
Write-Ok "pip.ini written: $PipConfigPath"
if ($proxyInfo.Proxy) {
    Write-Host "   proxy = $($proxyInfo.Proxy)" -ForegroundColor DarkGray
}
if ($caBundle) {
    Write-Host "   cert = $caBundle" -ForegroundColor DarkGray
}
Write-Host "   trusted-host = $($TrustedHosts -join ', ')" -ForegroundColor DarkGray
Pause-IfInteractive

# 5. Install
$installOk = Install-EvalTools
if (-not $installOk) {
    Write-Fail "Installation failed. Check errors above."
    Pause-IfInteractive
    exit 2
}
Pause-IfInteractive

# 6. Post-install verification
$verifyOk = Test-PostInstall
if ($verifyOk) {
    Write-Host ""
    Write-Host "========================================================================"
    Write-Host "  SUCCESS -- All eval tools installed and verified"
    Write-Host "========================================================================"
    Write-Host ""
    Write-Host "  Next steps:"
    Write-Host "    1. Launch QA Workbench -- RAGAS tab should work"
    Write-Host "    2. Launch Eval GUI -- RAGAS tab should work"
    Write-Host "    3. Run: .venv\Scripts\python.exe -c `"import ragas; print(ragas.__version__)`""
    Write-Host ""
} else {
    Write-Fail "Some packages failed verification. Check manifest: $ManifestPath"
}

Pause-IfInteractive
exit $(if ($verifyOk) { 0 } else { 3 })
