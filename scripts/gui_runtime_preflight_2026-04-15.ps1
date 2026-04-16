# NON-PROGRAMMER GUIDE
# Purpose: Prepares environment variables so the GUI launchers inherit safe runtime settings.
# How to follow: It is usually called by a launcher, but you can run it directly to inspect the resolved environment.
# Inputs: An optional project root and launcher name.
# Outputs: A printed or emitted set of environment values for GUI startup.
#
[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$LauncherName = "gui_launcher",
    [switch]$EmitCmd
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ProjectRoot {
    param([string]$RawProjectRoot)
    if ($RawProjectRoot) {
        return (Resolve-Path -LiteralPath $RawProjectRoot).Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Split-EnvList {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return @()
    }
    return @(
        $Value -split '[;,]' |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
    )
}

function Merge-NoProxy {
    param(
        [string]$UpperValue,
        [string]$LowerValue
    )
    $required = @("localhost", "127.0.0.1", "::1")
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $merged = New-Object System.Collections.Generic.List[string]

    foreach ($item in (Split-EnvList $UpperValue) + (Split-EnvList $LowerValue) + $required) {
        if ($seen.Add($item)) {
            [void]$merged.Add($item)
        }
    }
    return ($merged -join ",")
}

function Escape-CmdValue {
    param([string]$Value)
    $escaped = $Value
    $escaped = $escaped -replace '\^', '^^'
    $escaped = $escaped -replace '&', '^&'
    $escaped = $escaped -replace '\|', '^|'
    $escaped = $escaped -replace '<', '^<'
    $escaped = $escaped -replace '>', '^>'
    return $escaped
}

$resolvedProjectRoot = Resolve-ProjectRoot -RawProjectRoot $ProjectRoot
$noProxy = Merge-NoProxy -UpperValue $env:NO_PROXY -LowerValue $env:no_proxy
$httpProxy = if ($env:HTTP_PROXY) { $env:HTTP_PROXY } else { $env:http_proxy }
$httpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } else { $env:https_proxy }
$allProxy = if ($env:ALL_PROXY) { $env:ALL_PROXY } else { $env:all_proxy }
$proxyPresent = [int](
    -not [string]::IsNullOrWhiteSpace($httpProxy) -or
    -not [string]::IsNullOrWhiteSpace($httpsProxy) -or
    -not [string]::IsNullOrWhiteSpace($allProxy)
)
$certPresent = [int](
    -not [string]::IsNullOrWhiteSpace($env:REQUESTS_CA_BUNDLE) -or
    -not [string]::IsNullOrWhiteSpace($env:SSL_CERT_FILE) -or
    -not [string]::IsNullOrWhiteSpace($env:HTTPS_PROXY_CA)
)

$envPairs = @(
    @("PYTHONUTF8", "1"),
    @("PYTHONIOENCODING", "utf-8"),
    @("NO_PROXY", $noProxy),
    @("no_proxy", $noProxy),
    @("HTTP_PROXY", $httpProxy),
    @("http_proxy", $httpProxy),
    @("HTTPS_PROXY", $httpsProxy),
    @("https_proxy", $httpsProxy),
    @("ALL_PROXY", $allProxy),
    @("all_proxy", $allProxy),
    @("HF_HUB_DISABLE_TELEMETRY", "1"),
    @("HF_HUB_ENABLE_HF_TRANSFER", $(if ($env:HF_HUB_ENABLE_HF_TRANSFER) { $env:HF_HUB_ENABLE_HF_TRANSFER } else { "0" })),
    @("TRANSFORMERS_NO_ADVISORY_WARNINGS", $(if ($env:TRANSFORMERS_NO_ADVISORY_WARNINGS) { $env:TRANSFORMERS_NO_ADVISORY_WARNINGS } else { "1" })),
    @("HYBRIDRAG_PROJECT_ROOT", $resolvedProjectRoot),
    @("HYBRIDRAG_RUNTIME_PREFLIGHT", "gui_runtime_preflight_2026-04-15"),
    @("HYBRIDRAG_RUNTIME_PREFLIGHT_LAUNCHER", $LauncherName),
    @("HYBRIDRAG_RUNTIME_PROXY_PRESENT", [string]$proxyPresent),
    @("HYBRIDRAG_RUNTIME_CERT_ENV_PRESENT", [string]$certPresent),
    @("HYBRIDRAG_RUNTIME_LOOPBACK_BYPASS", $noProxy)
)

if ($EmitCmd) {
    foreach ($pair in $envPairs) {
        $key = [string]$pair[0]
        $value = if ($null -eq $pair[1]) { "" } else { [string]$pair[1] }
        Write-Output ('set "{0}={1}"' -f $key, (Escape-CmdValue $value))
    }
    exit 0
}

Write-Output "GUI Runtime Preflight"
Write-Output "Launcher: $LauncherName"
Write-Output "Project root: $resolvedProjectRoot"
Write-Output "UTF-8: PYTHONUTF8=1 PYTHONIOENCODING=utf-8"
Write-Output "Loopback bypass: $noProxy"
Write-Output "Inherited proxy present: $proxyPresent"
Write-Output "HTTP_PROXY: $httpProxy"
Write-Output "HTTPS_PROXY: $httpsProxy"
Write-Output "ALL_PROXY: $allProxy"
Write-Output "Cert env present: $certPresent"
Write-Output "REQUESTS_CA_BUNDLE: $($env:REQUESTS_CA_BUNDLE)"
Write-Output "SSL_CERT_FILE: $($env:SSL_CERT_FILE)"
Write-Output "HTTPS_PROXY_CA: $($env:HTTPS_PROXY_CA)"
