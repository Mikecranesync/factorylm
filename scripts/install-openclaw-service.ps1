#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs OpenClaw gateway as a Windows service via NSSM.
    RUN THIS AS ADMINISTRATOR: Right-click PowerShell → "Run as administrator"
.DESCRIPTION
    - Auto-starts on boot
    - Auto-restarts on crash (5s delay)
    - Rotates logs at 10MB
    - Runs as the current user
#>

$ErrorActionPreference = "Stop"

$nssmPath = "C:\Users\hharp\AppData\Local\Microsoft\WinGet\Packages\NSSM.NSSM_Microsoft.Winget.Source_8wekyb3d8bbwe\nssm-2.24-101-g897c7ad\win64\nssm.exe"
$openclawCmd = "C:\Users\hharp\AppData\Roaming\npm\openclaw.cmd"
$serviceName = "OpenClaw"
$logDir = "C:\Users\hharp\.openclaw\logs"

# Ensure log directory exists
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# Remove existing service if present
& $nssmPath remove $serviceName confirm 2>$null

# Install
& $nssmPath install $serviceName $openclawCmd gateway
if ($LASTEXITCODE -ne 0) { throw "Failed to install service" }

# Configure
& $nssmPath set $serviceName DisplayName "OpenClaw Gateway (Jarvis Local)"
& $nssmPath set $serviceName Description "OpenClaw Telegram bot gateway for @TravelLaptop_bot"
& $nssmPath set $serviceName AppDirectory "C:\Users\hharp"
& $nssmPath set $serviceName Start SERVICE_AUTO_START

# Logging with rotation
& $nssmPath set $serviceName AppStdout "$logDir\service-stdout.log"
& $nssmPath set $serviceName AppStderr "$logDir\service-stderr.log"
& $nssmPath set $serviceName AppRotateFiles 1
& $nssmPath set $serviceName AppRotateBytes 10485760

# Auto-restart on crash with 5s delay
& $nssmPath set $serviceName AppRestartDelay 5000
& $nssmPath set $serviceName AppExit Default Restart

# Run as current user (needed for env vars, Tailscale, etc.)
$cred = Get-Credential -UserName "$env:COMPUTERNAME\$env:USERNAME" -Message "Enter your Windows password for the OpenClaw service"
& $nssmPath set $serviceName ObjectName "$env:COMPUTERNAME\$env:USERNAME" $cred.GetNetworkCredential().Password

# Start it
& $nssmPath start $serviceName

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  OpenClaw service installed and started!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Commands:"
Write-Host "  nssm status OpenClaw    — check status"
Write-Host "  nssm restart OpenClaw   — restart"
Write-Host "  nssm stop OpenClaw      — stop"
Write-Host "  nssm remove OpenClaw    — uninstall"
Write-Host ""
Write-Host "Logs: $logDir"
