<#
.SYNOPSIS
    Start oc_plc agent on PLC laptop
.DESCRIPTION
    Starts all FactoryLM services for factory floor operation:
    - Matrix API (port 8000)
    - Demo UI (port 8080)
    - Jarvis Node (port 8765)
    - Optionally Factory I/O
#>

param(
    [switch]$Background,
    [switch]$WithFactoryIO
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Get-Item "$scriptDir\..\..").FullName
$ocDir = "$env:USERPROFILE\.openclaw"
$logDir = "$ocDir\logs"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Starting oc_plc (PLC Laptop Agent)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Ensure directories exist
New-Item -ItemType Directory -Path $ocDir -Force | Out-Null
New-Item -ItemType Directory -Path "$ocDir\workspace" -Force | Out-Null
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# Copy config if not present
$configSrc = "$scriptDir\oc_plc.json"
$configDst = "$ocDir\openclaw.json"
$identitySrc = "$scriptDir\IDENTITY_plc.md"
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
$env:OC_INSTANCE_ID = "oc_plc"
$env:OC_CONFIG = $configDst
$env:PLC_HOST = "localhost"
$env:PLC_PORT = "502"
$env:MATRIX_URL = "http://localhost:8000"

# Log startup
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path "$logDir\startup.log" -Value "$timestamp oc_plc starting"

# Array to track PIDs
$pids = @()

# Start Factory I/O (optional)
if ($WithFactoryIO) {
    Write-Host "`nStarting Factory I/O..." -ForegroundColor Yellow
    $factoryIOPath = "C:\Program Files (x86)\Real Games\Factory IO\Factory IO.exe"
    if (Test-Path $factoryIOPath) {
        $proc = Start-Process $factoryIOPath -PassThru
        $pids += $proc.Id
        Write-Host "[OK] Factory I/O started (PID: $($proc.Id))" -ForegroundColor Green
        Start-Sleep -Seconds 3  # Give it time to start Modbus server
    } else {
        Write-Host "[!] Factory I/O not found" -ForegroundColor Yellow
    }
}

# Check Modbus connectivity
Write-Host "`nChecking Modbus TCP (port 502)..." -ForegroundColor Yellow
$tcpTest = Test-NetConnection -ComputerName localhost -Port 502 -WarningAction SilentlyContinue
if ($tcpTest.TcpTestSucceeded) {
    Write-Host "[OK] Modbus TCP is listening" -ForegroundColor Green
} else {
    Write-Host "[!] Modbus TCP not available - start Factory I/O or connect real PLC" -ForegroundColor Yellow
}

# Start Matrix API
Write-Host "`nStarting Matrix API (port 8000)..." -ForegroundColor Yellow
$matrixPath = "$repoRoot\services\matrix\app.py"
if (Test-Path $matrixPath) {
    if ($Background) {
        $proc = Start-Process python -ArgumentList $matrixPath `
            -WorkingDirectory "$repoRoot\services\matrix" `
            -RedirectStandardOutput "$logDir\matrix-stdout.log" `
            -RedirectStandardError "$logDir\matrix-stderr.log" `
            -PassThru -WindowStyle Hidden
        $pids += $proc.Id
        Write-Host "[OK] Matrix API started (PID: $($proc.Id))" -ForegroundColor Green
    } else {
        Start-Process python -ArgumentList $matrixPath `
            -WorkingDirectory "$repoRoot\services\matrix"
    }
    Start-Sleep -Seconds 2
}

# Start Demo UI
Write-Host "`nStarting Demo UI (port 8080)..." -ForegroundColor Yellow
$demoPath = "$repoRoot\services\matrix\demo_ui.py"
if (Test-Path $demoPath) {
    if ($Background) {
        $proc = Start-Process python -ArgumentList $demoPath `
            -WorkingDirectory "$repoRoot\services\matrix" `
            -RedirectStandardOutput "$logDir\demo-stdout.log" `
            -RedirectStandardError "$logDir\demo-stderr.log" `
            -PassThru -WindowStyle Hidden
        $pids += $proc.Id
        Write-Host "[OK] Demo UI started (PID: $($proc.Id))" -ForegroundColor Green
    } else {
        Start-Process python -ArgumentList $demoPath `
            -WorkingDirectory "$repoRoot\services\matrix"
    }
    Start-Sleep -Seconds 2
}

# Start Jarvis Node
Write-Host "`nStarting Jarvis Node (port 8765)..." -ForegroundColor Yellow
$jarvisPath = "$repoRoot\remoteme-jarvis-node\jarvis_node.py"
if (Test-Path $jarvisPath) {
    if ($Background) {
        $proc = Start-Process python -ArgumentList $jarvisPath `
            -WorkingDirectory "$repoRoot\remoteme-jarvis-node" `
            -RedirectStandardOutput "$logDir\jarvis-stdout.log" `
            -RedirectStandardError "$logDir\jarvis-stderr.log" `
            -PassThru -WindowStyle Hidden
        $pids += $proc.Id
        Write-Host "[OK] Jarvis Node started (PID: $($proc.Id))" -ForegroundColor Green
    } else {
        Start-Process python -ArgumentList $jarvisPath `
            -WorkingDirectory "$repoRoot\remoteme-jarvis-node"
    }
}

# Save PIDs for stop script
$pids | Out-File "$ocDir\services.pid"

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  oc_plc is ready!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:"
Write-Host "  Matrix API:  http://localhost:8000" -ForegroundColor White
Write-Host "  Demo UI:     http://localhost:8080" -ForegroundColor White
Write-Host "  Jarvis Node: http://localhost:8765" -ForegroundColor White
Write-Host "  Modbus TCP:  localhost:502" -ForegroundColor White
Write-Host ""
Write-Host "Tailscale (remote):"
Write-Host "  Matrix API:  http://100.72.2.99:8000" -ForegroundColor White
Write-Host "  Demo UI:     http://100.72.2.99:8080" -ForegroundColor White
Write-Host "  Jarvis Node: http://100.72.2.99:8765" -ForegroundColor White
Write-Host ""
Write-Host "Commands:"
Write-Host "  .\stop-oc-plc.ps1    - Stop all services"
Write-Host ""
