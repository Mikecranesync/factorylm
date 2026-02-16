# setup-local.ps1 — Configure Honeycomb OpenTelemetry for the local Windows openclaw instance
#
# Usage:
#   .\setup-local.ps1 -ApiKey "hcaik_xxxxxxxxxxxx"
#
# What it does:
#   1. Copies tracing.js to C:\Users\hharp\.openclaw\tracing.js
#   2. Installs OTel npm packages globally
#   3. Sets persistent user-level environment variables
#   4. Prints next steps
#
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiKey
)

$ErrorActionPreference = "Stop"

$ServiceName    = "openclaw-jarvis-local"
$InstanceName   = "jarvis-local"
$Endpoint       = "https://api.honeycomb.io:443"
$Protocol       = "http/protobuf"
$TracingDest    = "C:\Users\hharp\.openclaw\tracing.js"
$TracingSrc     = Join-Path $PSScriptRoot "tracing.js"

Write-Host ""
Write-Host "=== Honeycomb OTel Setup for jarvis-local (Windows) ===" -ForegroundColor Cyan
Write-Host "  Service name : $ServiceName"
Write-Host "  Tracing file : $TracingDest"
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Copy tracing.js
# ---------------------------------------------------------------------------
Write-Host "[1/3] Copying tracing.js -> $TracingDest" -ForegroundColor Yellow
$destDir = Split-Path $TracingDest -Parent
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
}
Copy-Item -Path $TracingSrc -Destination $TracingDest -Force
Write-Host "  Done" -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# Step 2: Install OTel npm packages globally
# ---------------------------------------------------------------------------
Write-Host "[2/3] Installing OpenTelemetry npm packages globally..." -ForegroundColor Yellow
& (Join-Path $PSScriptRoot "install-deps.ps1")
Write-Host ""

# ---------------------------------------------------------------------------
# Step 3: Set persistent user-level environment variables
# ---------------------------------------------------------------------------
Write-Host "[3/3] Setting user-level environment variables..." -ForegroundColor Yellow

$envVars = @{
    "HONEYCOMB_API_KEY"              = $ApiKey
    "OTEL_SERVICE_NAME"              = $ServiceName
    "OTEL_EXPORTER_OTLP_ENDPOINT"   = $Endpoint
    "OTEL_EXPORTER_OTLP_PROTOCOL"   = $Protocol
    "OTEL_EXPORTER_OTLP_HEADERS"    = "x-honeycomb-team=$ApiKey"
    "OTEL_INSTANCE_NAME"            = $InstanceName
    "OTEL_DEPLOYMENT_ENVIRONMENT"   = "local"
    "NODE_OPTIONS"                   = "-r $TracingDest"
}

foreach ($key in $envVars.Keys) {
    $val = $envVars[$key]
    [System.Environment]::SetEnvironmentVariable($key, $val, [System.EnvironmentVariableTarget]::User)
    # Also set in current session so verification works immediately
    Set-Item -Path "Env:\$key" -Value $val
    # Mask the API key in output
    $displayVal = $val
    if ($key -match "API_KEY|HEADERS" -and $val.Length -gt 16) {
        $displayVal = $val.Substring(0, 12) + "..." + $val.Substring($val.Length - 4)
    }
    Write-Host "  $key = $displayVal" -ForegroundColor DarkGray
}

Write-Host "  Done (persisted to User environment)" -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. RESTART your terminal / PowerShell session"
Write-Host "   (environment variables won't apply to already-running shells)"
Write-Host ""
Write-Host "2. Restart the openclaw gateway:"
Write-Host "   openclaw"
Write-Host ""
Write-Host "3. Look for the tracing init line in the console output:"
Write-Host "   [tracing] OpenTelemetry started -> $Endpoint"
Write-Host ""
Write-Host "4. Send a test message, then check Honeycomb:"
Write-Host "   https://ui.honeycomb.io -> Dataset: $ServiceName"
Write-Host ""
Write-Host "5. If no data appears after 2 min, check:" -ForegroundColor DarkYellow
Write-Host "   - API key is valid (starts with hcaik_)"
Write-Host "   - NODE_OPTIONS is set:  echo `$env:NODE_OPTIONS"
Write-Host "   - Network can reach api.honeycomb.io:443"
Write-Host ""
