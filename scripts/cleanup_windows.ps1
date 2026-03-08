# ================================================================
# PLC Laptop Windows Cleanup (Run as Administrator)
# Right-click PowerShell → Run as Administrator → paste this path
# ================================================================

Write-Host "=== PLC Laptop Windows Cleanup ===" -ForegroundColor Cyan
Write-Host ""

# Disable Windows Search indexing
Write-Host "[1/3] Disabling Windows Search..." -ForegroundColor Yellow
try {
    Stop-Service WSearch -Force -ErrorAction Stop
    Set-Service WSearch -StartupType Disabled
    Write-Host "  Done. WSearch stopped and disabled." -ForegroundColor Green
} catch {
    Write-Host "  Warning: $($_.Exception.Message)" -ForegroundColor Red
}

# Disable Cortana
Write-Host "[2/3] Disabling Cortana..." -ForegroundColor Yellow
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Search" /v AllowCortana /t REG_DWORD /d 0 /f | Out-Null
Write-Host "  Done." -ForegroundColor Green

# Disable telemetry
Write-Host "[3/3] Disabling telemetry..." -ForegroundColor Yellow
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection" /v AllowTelemetry /t REG_DWORD /d 0 /f | Out-Null
Write-Host "  Done." -ForegroundColor Green

Write-Host ""
Write-Host "=== Cleanup complete ===" -ForegroundColor Cyan

# Show memory after cleanup
$os = Get-CimInstance Win32_OperatingSystem
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
Write-Host "RAM: ${freeGB}GB free / ${totalGB}GB total" -ForegroundColor White
