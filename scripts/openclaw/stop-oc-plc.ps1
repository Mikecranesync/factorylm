<#
.SYNOPSIS
    Stop oc_plc agent
.DESCRIPTION
    Stops all FactoryLM services on PLC laptop
#>

$ErrorActionPreference = "SilentlyContinue"
$ocDir = "$env:USERPROFILE\.openclaw"
$logDir = "$ocDir\logs"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Stopping oc_plc" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Check for saved PIDs
$pidFile = "$ocDir\services.pid"
if (Test-Path $pidFile) {
    $pids = Get-Content $pidFile
    foreach ($pid in $pids) {
        if ($pid -match '^\d+$') {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Stop-Process -Id $pid -Force
                Write-Host "[OK] Stopped process (PID: $pid)" -ForegroundColor Green
            }
        }
    }
    Remove-Item $pidFile -Force
}

# Also kill known Python services
$services = @("app.py", "demo_ui.py", "jarvis_node.py", "factoryio_bridge.py")
foreach ($svc in $services) {
    $procs = Get-Process python -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$svc*" }

    foreach ($proc in $procs) {
        Write-Host "Stopping $svc (PID: $($proc.Id))"
        Stop-Process -Id $proc.Id -Force
    }
}

# Log shutdown
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path "$logDir\startup.log" -Value "$timestamp oc_plc stopped"

Write-Host ""
Write-Host "[OK] oc_plc stopped" -ForegroundColor Green
Write-Host ""
Write-Host "Note: Factory I/O must be stopped manually if running"
