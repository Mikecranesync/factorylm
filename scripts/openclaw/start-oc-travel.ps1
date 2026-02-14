<#
.SYNOPSIS
    Start oc_travel agent on travel laptop
.DESCRIPTION
    Starts Jarvis Node and sets up environment for FactoryLM development agent
#>

param(
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Get-Item "$scriptDir\..\..").FullName
$ocDir = "$env:USERPROFILE\.openclaw"
$logDir = "$ocDir\logs"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Starting oc_travel (Travel Laptop Agent)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Ensure directories exist
New-Item -ItemType Directory -Path $ocDir -Force | Out-Null
New-Item -ItemType Directory -Path "$ocDir\workspace" -Force | Out-Null
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# Copy config if not present or update
$configSrc = "$scriptDir\oc_travel.json"
$configDst = "$ocDir\openclaw.json"
$identitySrc = "$scriptDir\IDENTITY_travel.md"
$identityDst = "$ocDir\IDENTITY.md"

if (Test-Path $configSrc) {
    Copy-Item $configSrc $configDst -Force
    Write-Host "[OK] Config: $configDst" -ForegroundColor Green
}

if (Test-Path $identitySrc) {
    Copy-Item $identitySrc $identityDst -Force
    Write-Host "[OK] Identity: $identityDst" -ForegroundColor Green
}

# Set environment
$env:OC_INSTANCE_ID = "oc_travel"
$env:OC_CONFIG = $configDst
$env:OC_IDENTITY = $identityDst
$env:MATRIX_URL = "http://100.72.2.99:8000"
$env:PLC_JARVIS_URL = "http://100.72.2.99:8765"

# Log startup
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path "$logDir\startup.log" -Value "$timestamp oc_travel starting"

# Check PLC laptop connectivity
Write-Host "`nChecking PLC laptop connectivity..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://100.72.2.99:8765/health" -TimeoutSec 5
    Write-Host "[OK] PLC laptop (100.72.2.99:8765) is online" -ForegroundColor Green
} catch {
    Write-Host "[!] PLC laptop not reachable - some features unavailable" -ForegroundColor Yellow
}

# Start Jarvis Node
$jarvisPath = "$repoRoot\remoteme-jarvis-node\jarvis_node.py"
if (Test-Path $jarvisPath) {
    Write-Host "`nStarting Jarvis Node on port 8765..." -ForegroundColor Yellow

    if ($Background) {
        $proc = Start-Process python -ArgumentList $jarvisPath `
            -WorkingDirectory "$repoRoot\remoteme-jarvis-node" `
            -RedirectStandardOutput "$logDir\jarvis-stdout.log" `
            -RedirectStandardError "$logDir\jarvis-stderr.log" `
            -PassThru -WindowStyle Hidden

        Write-Host "[OK] Jarvis Node started in background (PID: $($proc.Id))" -ForegroundColor Green
        Write-Host "    Logs: $logDir\jarvis-*.log" -ForegroundColor Gray

        # Save PID for stop script
        $proc.Id | Out-File "$ocDir\jarvis.pid"
    } else {
        Write-Host "[OK] Running Jarvis Node in foreground (Ctrl+C to stop)" -ForegroundColor Green
        Write-Host ""
        python $jarvisPath
    }
} else {
    Write-Host "[!] jarvis_node.py not found at $jarvisPath" -ForegroundColor Red
    exit 1
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  oc_travel is ready!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Endpoints:"
Write-Host "  Local:      http://localhost:8765" -ForegroundColor White
Write-Host "  Tailscale:  http://100.83.251.23:8765" -ForegroundColor White
Write-Host ""
Write-Host "Commands:"
Write-Host "  .\stop-oc-travel.ps1    - Stop the agent"
Write-Host "  curl localhost:8765/health"
Write-Host ""
