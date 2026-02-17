# Media Offload Script for Windows
# ================================
# Syncs media from local folders to Google Drive
# Run manually or via Task Scheduler
#
# Prerequisites:
#   - rclone installed and configured with 'gdrive' remote
#   - Google Drive folder: factorylm-archives/media/

$ErrorActionPreference = "Stop"

# Configuration
$GDRIVE_REMOTE = "gdrive:factorylm-archives/media"
$LOG_FILE = "$env:USERPROFILE\.openclaw\logs\media-offload.log"

# Source folders to sync
$SOURCES = @{
    "travel-laptop" = @(
        "$env:USERPROFILE\Desktop\Captures"
        "$env:USERPROFILE\Downloads\Screenshots"
        "$env:USERPROFILE\Pictures\Screenshots"
        "$env:USERPROFILE\Videos\Captures"
    )
    "telegram" = @(
        "$env:USERPROFILE\.openclaw\media-inbox\telegram"
    )
}

# Ensure log directory exists
$logDir = Split-Path $LOG_FILE -Parent
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logLine = "[$timestamp] $Message"
    Add-Content -Path $LOG_FILE -Value $logLine
    Write-Host $logLine
}

function Sync-Folder {
    param(
        [string]$Source,
        [string]$DeviceName
    )

    if (-not (Test-Path $Source)) {
        Write-Log "Skipping (not found): $Source"
        return 0
    }

    $fileCount = (Get-ChildItem -Path $Source -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($fileCount -eq 0) {
        Write-Log "Skipping (empty): $Source"
        return 0
    }

    $dest = "$GDRIVE_REMOTE/$DeviceName/"
    Write-Log "Syncing $fileCount files from $Source to $dest"

    try {
        $result = & rclone copy $Source $dest --progress --log-level INFO 2>&1
        Write-Log "Sync complete: $Source"
        return $fileCount
    }
    catch {
        Write-Log "ERROR syncing $Source : $_"
        return 0
    }
}

# Main
Write-Log "=========================================="
Write-Log "Media Offload Started"
Write-Log "=========================================="

$totalSynced = 0

foreach ($device in $SOURCES.Keys) {
    Write-Log "Processing device: $device"
    foreach ($folder in $SOURCES[$device]) {
        $synced = Sync-Folder -Source $folder -DeviceName $device
        $totalSynced += $synced
    }
}

Write-Log "=========================================="
Write-Log "Media Offload Complete: $totalSynced files processed"
Write-Log "=========================================="
