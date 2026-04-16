<#
.SYNOPSIS
  Build a fully-offline gliner install bundle for proxy-hardened workstations.

.DESCRIPTION
  Runs on a machine with internet (primary workstation). Pip-downloads gliner==0.2.26 and its
  transitive dependencies into <OutputRoot>\gliner_offline\wheels, then snapshots
  the urchade/gliner_medium-v2.1 HuggingFace model into <OutputRoot>\gliner_offline\hf_home.
  Zips the whole thing to <OutputRoot>\gliner_offline.zip.

  The resulting zip can be copied to a proxy-hardened workstation and installed
  via INSTALL_GLINER_OFFLINE.bat - no pip network call, no HuggingFace network call.

.NOTES
  Must be run from C:\HybridRAG_V2 with the repo-local .venv populated.
  Target workstation must run the same Python minor version (3.12) as this builder.

.EXAMPLE
  cd C:\HybridRAG_V2
  .\tools\build_gliner_offline_bundle.ps1

.EXAMPLE
  .\tools\build_gliner_offline_bundle.ps1 -OutputRoot C:\scratch\gliner_test
#>
# NON-PROGRAMMER GUIDE
# Purpose: Builds the offline GLiNER bundle on a machine that does have internet access.
# How to follow: Run it on the staging machine, then copy the resulting bundle to the isolated workstation.
# Inputs: A prepared repo environment with the needed download tools.
# Outputs: A zip bundle for offline GLiNER installation.
#
param(
    [string]$OutputRoot = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot 'vendor'
}
$BundleRoot = Join-Path $OutputRoot 'gliner_offline'
$WheelDir   = Join-Path $BundleRoot 'wheels'
$HFHome     = Join-Path $BundleRoot 'hf_home'
$ZipPath    = Join-Path $OutputRoot 'gliner_offline.zip'
$Python     = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $Python)) {
    Write-Error ('Repo-local Python not found at ' + $Python + '. Install the venv first.')
    exit 2
}

Write-Host ('[1/5] Preparing bundle directories under ' + $BundleRoot)
if (Test-Path $BundleRoot) { Remove-Item -Recurse -Force $BundleRoot }
New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null
New-Item -ItemType Directory -Force -Path $HFHome   | Out-Null

# Two-pass download mirrors the documented 2-step install pattern:
#   Pass 1: gliner's runtime deps (NO gliner itself, so torch is NOT pulled).
#           None of these hard-require torch on transformers >=4.51.
#   Pass 2: gliner itself with --no-deps (torch must already exist on target).
#
# This keeps the bundle small (~400-500MB) and protects any pre-existing
# CUDA torch install on the target workstation from being overwritten.
$DepLayer = @(
    'huggingface_hub>=0.21.4',
    'onnxruntime',
    'sentencepiece',
    'tqdm',
    'transformers>=4.51.3,<5.2.0'
)

Write-Host ('[2a/5] pip download dep layer (no gliner, no torch) to ' + $WheelDir)
$pipDepArgs = @('-m', 'pip', 'download', '--dest', $WheelDir, '--no-cache-dir', '--only-binary=:all:') + $DepLayer
& $Python @pipDepArgs
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'dep layer download with --only-binary failed; retrying without wheel-only constraint.'
    $pipDepFallback = @('-m', 'pip', 'download', '--dest', $WheelDir, '--no-cache-dir') + $DepLayer
    & $Python @pipDepFallback
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'dep layer download failed. Check network + pypi access on this builder machine.'
        exit 3
    }
}

Write-Host ('[2b/5] pip download --no-deps gliner==0.2.26 to ' + $WheelDir)
$pipGlinerArgs = @('-m', 'pip', 'download', '--dest', $WheelDir, '--no-cache-dir', '--no-deps', '--only-binary=:all:', 'gliner==0.2.26')
& $Python @pipGlinerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'gliner no-deps download with --only-binary failed; retrying without wheel-only constraint.'
    $pipGlinerFallback = @('-m', 'pip', 'download', '--dest', $WheelDir, '--no-cache-dir', '--no-deps', 'gliner==0.2.26')
    & $Python @pipGlinerFallback
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'gliner download failed.'
        exit 3
    }
}

# Sanity check: the bundle MUST NOT contain a torch wheel. If it does, the
# 2-pass download is broken and we refuse to publish a torch-nuking bundle.
$torchWheels = Get-ChildItem $WheelDir -Filter 'torch-*.whl' -ErrorAction SilentlyContinue
if ($torchWheels) {
    Write-Error ('Refusing to build bundle: torch wheel present in ' + $WheelDir + '. This would overwrite the workstation CUDA torch install.')
    exit 3
}

Write-Host ('[3/5] Snapshotting urchade/gliner_medium-v2.1 into ' + $HFHome)
$env:HF_HOME = $HFHome
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$SnapshotHelper = Join-Path $PSScriptRoot '_snapshot_gliner_model.py'
if (-not (Test-Path $SnapshotHelper)) {
    Write-Error ('Snapshot helper missing: ' + $SnapshotHelper)
    exit 4
}
& $Python $SnapshotHelper
if ($LASTEXITCODE -ne 0) {
    Write-Error 'HuggingFace snapshot_download failed.'
    exit 4
}

Write-Host '[4/5] Writing bundle manifest'
$pythonVersionRaw = (& $Python -V) 2>&1 | Out-String
$pythonVersion = $pythonVersionRaw.Trim() -replace '^Python\s+', ''
$wheelCount = (Get-ChildItem $WheelDir -Filter *.whl).Count
$manifest = @{
    built_at       = (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz')
    builder_host   = $env:COMPUTERNAME
    python_version = $pythonVersion
    gliner_version = '0.2.26'
    model_repo     = 'urchade/gliner_medium-v2.1'
    wheel_count    = $wheelCount
}
$manifestPath = Join-Path $BundleRoot 'manifest.json'
$manifest | ConvertTo-Json | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host ('[5/5] Zipping bundle to ' + $ZipPath)
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
$zipSource = Join-Path $BundleRoot '*'
Compress-Archive -Path $zipSource -DestinationPath $ZipPath -CompressionLevel Optimal

$zipSizeMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
Write-Host ''
Write-Host '[PASS] gliner offline bundle built.'
Write-Host ('       Zip:    ' + $ZipPath + ' (' + $zipSizeMb + ' MB)')
Write-Host ('       Wheels: ' + $wheelCount)
Write-Host '       Model:  urchade/gliner_medium-v2.1'
Write-Host ''
Write-Host 'Copy the zip to the workstation, place it at C:\HybridRAG_V2\vendor\gliner_offline.zip,'
Write-Host 'then run INSTALL_GLINER_OFFLINE.bat from C:\HybridRAG_V2.'
