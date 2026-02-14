<#
.SYNOPSIS
    Stop oc_travel agent
.DESCRIPTION
    Stops Jarvis Node running for oc_travel
#>

$ErrorActionPreference = "SilentlyContinue"
$ocDir = "$env:USERPROFILE\.openclaw"
$logDir = "$ocDir\logs"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Stopping oc_travel" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Check for saved PID
$pidFile = "$ocDir\jarvis.pid"
if (Test-Path $pidFile) {
    $pid = Get-Content $pidFile
    Write-Host "Found PID file: $pid"

    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $pid -Force
        Write-Host "[OK] Stopped Jarvis Node (PID: $pid)" -ForegroundColor Green
    } else {
        Write-Host "[!] Process $pid not running" -ForegroundColor Yellow
    }

    Remove-Item $pidFile -Force
}

# Also kill any python processes running jarvis_node
$jarvisProcs = Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*jarvis_node*" }

foreach ($proc in $jarvisProcs) {
    Write-Host "Stopping Jarvis Node process: $($proc.Id)"
    Stop-Process -Id $proc.Id -Force
}

# Log shutdown
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path "$logDir\startup.log" -Value "$timestamp oc_travel stopped"

Write-Host ""
Write-Host "[OK] oc_travel stopped" -ForegroundColor Green
