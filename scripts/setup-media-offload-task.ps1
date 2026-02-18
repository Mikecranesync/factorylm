# Setup Media Offload Agent as Windows Scheduled Task
# Run as Administrator

param(
    [switch]$Remove,
    [int]$IntervalMinutes = 5,
    [string]$PythonPath = "python"
)

$TaskName = "FactoryLM-MediaOffloadAgent"
$TaskDescription = "Syncs media from local folders to Google Drive every $IntervalMinutes minutes"
$ScriptPath = "$env:USERPROFILE\OneDrive\Desktop\FactoryLM\services\media\media_offload_agent.py"
$LogPath = "$env:USERPROFILE\.openclaw\logs"

# Ensure log directory exists
if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
}

if ($Remove) {
    Write-Host "Removing scheduled task: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] Task removed."
    exit 0
}

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Task '$TaskName' already exists. Removing and recreating..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create action - run once then agent polls internally
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --once 2>&1 >> `"$LogPath\media-offload.log`""

# Create trigger - run every N minutes
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 365)

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Create principal (run as current user)
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description $TaskDescription `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal

Write-Host ""
Write-Host "[OK] Scheduled task created: $TaskName"
Write-Host "     Interval: Every $IntervalMinutes minutes"
Write-Host "     Log file: $LogPath\media-offload.log"
Write-Host ""
Write-Host "To check status:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "To run manually:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "To view logs:"
Write-Host "  Get-Content '$LogPath\media-offload.log' -Tail 50"
Write-Host ""
Write-Host "To remove:"
Write-Host "  .\setup-media-offload-task.ps1 -Remove"
