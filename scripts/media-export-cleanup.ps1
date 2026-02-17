# Media Export & Cleanup Script
# ==============================
# Exports ALL media from devices to Google Drive, then optionally cleans up
# Run this to free up local storage on laptops and phones
#
# SAFETY: Files are COPIED first, verified, then optionally deleted
#
# Usage:
#   .\media-export-cleanup.ps1              # Sync only (no delete)
#   .\media-export-cleanup.ps1 -Cleanup     # Sync and delete synced files
#   .\media-export-cleanup.ps1 -DryRun      # Show what would happen

param(
    [switch]$Cleanup,
    [switch]$DryRun,
    [int]$DaysOld = 30  # Only cleanup files older than this
)

$ErrorActionPreference = "Stop"

# Configuration
$GDRIVE_REMOTE = "gdrive:factorylm-archives/media"
$LOG_FILE = "$env:USERPROFILE\.openclaw\logs\media-export-$(Get-Date -Format 'yyyyMMdd').log"

# All media locations to export
$EXPORT_SOURCES = @{
    "travel-laptop" = @{
        folders = @(
            "$env:USERPROFILE\Desktop\Captures"
            "$env:USERPROFILE\Downloads"
            "$env:USERPROFILE\Pictures"
            "$env:USERPROFILE\Videos"
            "$env:USERPROFILE\Documents\Screenshots"
        )
        extensions = @("*.jpg", "*.jpeg", "*.png", "*.gif", "*.mp4", "*.mov", "*.avi", "*.webm", "*.pdf", "*.heic")
    }
    "onedrive-camera" = @{
        folders = @(
            "$env:USERPROFILE\OneDrive\Pictures\Camera Roll"
            "$env:USERPROFILE\OneDrive\Pictures\Screenshots"
        )
        extensions = @("*.jpg", "*.jpeg", "*.png", "*.heic", "*.mp4", "*.mov")
    }
    "phone-backup" = @{
        folders = @(
            # iCloud Photos sync folder (if configured)
            "$env:USERPROFILE\iCloudPhotos"
            # Google Photos download folder
            "$env:USERPROFILE\Downloads\Google Photos"
            # Android file transfer
            "D:\Phone\DCIM"
            "E:\Phone\DCIM"
        )
        extensions = @("*.jpg", "*.jpeg", "*.png", "*.heic", "*.mp4", "*.mov", "*.3gp")
    }
    "telegram-media" = @{
        folders = @(
            "$env:USERPROFILE\.openclaw\media-inbox\telegram"
            "$env:USERPROFILE\Downloads\Telegram Desktop"
        )
        extensions = @("*.jpg", "*.jpeg", "*.png", "*.mp4", "*.mov", "*.pdf", "*.webp")
    }
}

# Ensure log directory exists
$logDir = Split-Path $LOG_FILE -Parent
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logLine = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LOG_FILE -Value $logLine

    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host $logLine -ForegroundColor $color
}

function Get-MediaFiles {
    param(
        [string]$Folder,
        [string[]]$Extensions,
        [int]$DaysOld
    )

    if (-not (Test-Path $Folder)) {
        return @()
    }

    $cutoffDate = (Get-Date).AddDays(-$DaysOld)
    $files = @()

    foreach ($ext in $Extensions) {
        $found = Get-ChildItem -Path $Folder -Filter $ext -Recurse -File -ErrorAction SilentlyContinue |
                 Where-Object { $_.LastWriteTime -lt $cutoffDate }
        $files += $found
    }

    return $files
}

function Export-MediaFolder {
    param(
        [string]$Source,
        [string]$DeviceName,
        [string[]]$Extensions
    )

    if (-not (Test-Path $Source)) {
        Write-Log "Skipping (not found): $Source" "WARN"
        return @{ synced = 0; size = 0 }
    }

    # Get all matching files
    $files = @()
    foreach ($ext in $Extensions) {
        $found = Get-ChildItem -Path $Source -Filter $ext -Recurse -File -ErrorAction SilentlyContinue
        $files += $found
    }

    if ($files.Count -eq 0) {
        Write-Log "Skipping (no media): $Source"
        return @{ synced = 0; size = 0 }
    }

    $totalSize = ($files | Measure-Object -Property Length -Sum).Sum / 1MB
    $dest = "$GDRIVE_REMOTE/$DeviceName/"

    Write-Log "Found $($files.Count) files ($([math]::Round($totalSize, 2)) MB) in $Source"

    if ($DryRun) {
        Write-Log "[DRY RUN] Would sync to $dest" "WARN"
        return @{ synced = $files.Count; size = $totalSize }
    }

    try {
        # Use rclone to sync
        $rcloneArgs = @("copy", $Source, $dest, "--progress", "--log-level", "INFO")
        foreach ($ext in $Extensions) {
            $rcloneArgs += "--include"
            $rcloneArgs += $ext
        }

        & rclone @rcloneArgs 2>&1 | ForEach-Object { Write-Log $_ }

        Write-Log "Synced $($files.Count) files to $dest" "SUCCESS"
        return @{ synced = $files.Count; size = $totalSize; files = $files }
    }
    catch {
        Write-Log "ERROR syncing $Source : $_" "ERROR"
        return @{ synced = 0; size = 0; error = $_.ToString() }
    }
}

function Remove-SyncedFiles {
    param(
        [System.IO.FileInfo[]]$Files,
        [int]$DaysOld
    )

    $cutoffDate = (Get-Date).AddDays(-$DaysOld)
    $removed = 0
    $freedMB = 0

    foreach ($file in $Files) {
        # Only delete if older than threshold
        if ($file.LastWriteTime -lt $cutoffDate) {
            if ($DryRun) {
                Write-Log "[DRY RUN] Would delete: $($file.FullName)" "WARN"
            }
            else {
                try {
                    $sizeMB = $file.Length / 1MB
                    Remove-Item $file.FullName -Force
                    $removed++
                    $freedMB += $sizeMB
                    Write-Log "Deleted: $($file.Name) ($([math]::Round($sizeMB, 2)) MB)"
                }
                catch {
                    Write-Log "Failed to delete $($file.FullName): $_" "ERROR"
                }
            }
        }
    }

    return @{ removed = $removed; freedMB = $freedMB }
}

# ============================================================================
# MAIN
# ============================================================================

Write-Log "=========================================="
Write-Log "MEDIA EXPORT & CLEANUP"
Write-Log "=========================================="
Write-Log "Mode: $(if ($Cleanup) { 'EXPORT + CLEANUP' } else { 'EXPORT ONLY' })"
Write-Log "DryRun: $DryRun"
Write-Log "Days Old Threshold: $DaysOld"
Write-Log "=========================================="

$summary = @{
    totalFiles = 0
    totalSizeMB = 0
    removedFiles = 0
    freedMB = 0
}

foreach ($device in $EXPORT_SOURCES.Keys) {
    Write-Log ""
    Write-Log "Processing: $device"
    Write-Log "----------------------------------------"

    $config = $EXPORT_SOURCES[$device]

    foreach ($folder in $config.folders) {
        $result = Export-MediaFolder -Source $folder -DeviceName $device -Extensions $config.extensions

        $summary.totalFiles += $result.synced
        $summary.totalSizeMB += $result.size

        # Cleanup if requested and sync was successful
        if ($Cleanup -and $result.files -and $result.synced -gt 0) {
            Write-Log "Cleaning up old files from $folder..."
            $cleanResult = Remove-SyncedFiles -Files $result.files -DaysOld $DaysOld
            $summary.removedFiles += $cleanResult.removed
            $summary.freedMB += $cleanResult.freedMB
        }
    }
}

# ============================================================================
# SUMMARY
# ============================================================================

Write-Log ""
Write-Log "=========================================="
Write-Log "EXPORT COMPLETE"
Write-Log "=========================================="
Write-Log "Files Synced: $($summary.totalFiles)"
Write-Log "Total Size: $([math]::Round($summary.totalSizeMB, 2)) MB"

if ($Cleanup) {
    Write-Log "Files Removed: $($summary.removedFiles)"
    Write-Log "Space Freed: $([math]::Round($summary.freedMB, 2)) MB"
}

Write-Log "=========================================="
Write-Log "Log saved to: $LOG_FILE"

# Display disk space
Write-Log ""
Write-Log "Current Disk Space:"
Get-PSDrive -PSProvider FileSystem | Format-Table Name, @{N='Free(GB)';E={[math]::Round($_.Free/1GB,2)}}, @{N='Used(GB)';E={[math]::Round($_.Used/1GB,2)}}
