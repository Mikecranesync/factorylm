<#
.SYNOPSIS
    Remote management for the PLC laptop (LAPTOP-0KA3C70H) at Tailscale IP 100.72.2.99.

.DESCRIPTION
    Provides subcommands to check status, sync code, install dependencies,
    start/stop services, and tail logs on the PLC laptop over SSH.

    Both machines are Windows. The remote shell is PowerShell.
    SSH is key-based (no password prompt).

.PARAMETER Command
    The subcommand to run. One of:
        status, sync, deps, start-matrix, start-bridge, start-watcher,
        start-all, stop-all, logs, check-factoryio

.EXAMPLE
    .\scripts\plc_remote.ps1 status
    .\scripts\plc_remote.ps1 sync
    .\scripts\plc_remote.ps1 start-all
    .\scripts\plc_remote.ps1 logs
#>

param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet(
        "status", "sync", "deps",
        "start-matrix", "start-bridge", "start-watcher", "start-all",
        "stop-all", "logs", "check-factoryio"
    )]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Extra
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
$SSH_TARGET  = "hharp@100.72.2.99"
$REPO_PATH   = "C:\Users\hharp\Desktop\factorylm-monorepo"
$LOG_DIR     = "$REPO_PATH\logs"
$GIT_EXE     = "C:\Users\hharp\AppData\Local\GitHubDesktop\app-3.5.4\resources\app\git\cmd\git.exe"
$PYTHON_EXE  = "python"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Invoke-Remote {
    param([string]$RemoteCmd)
    Write-Host ">>> ssh $SSH_TARGET" -ForegroundColor DarkGray
    Write-Host ">>> $RemoteCmd" -ForegroundColor DarkGray
    ssh $SSH_TARGET $RemoteCmd
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Remote command failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    }
}

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
switch ($Command) {

    "status" {
        Write-Header "PLC Laptop Status (100.72.2.99)"

        Write-Host "`n--- SSH connectivity ---" -ForegroundColor Yellow
        Invoke-Remote "hostname"

        Write-Host "`n--- Python version ---" -ForegroundColor Yellow
        Invoke-Remote "$PYTHON_EXE --version"

        Write-Host "`n--- Installed pip packages ---" -ForegroundColor Yellow
        Invoke-Remote "$PYTHON_EXE -m pip list --format=columns 2>`$null | Select-String -Pattern 'fastapi|uvicorn|pymodbus|httpx|pyyaml|PyYAML' -CaseSensitive:`$false"

        Write-Host "`n--- Repo branch ---" -ForegroundColor Yellow
        Invoke-Remote "Set-Location '$REPO_PATH'; & '$GIT_EXE' branch --show-current"

        Write-Host "`n--- Running Python processes ---" -ForegroundColor Yellow
        Invoke-Remote "Get-Process python*, uvicorn* -ErrorAction SilentlyContinue | Format-Table Id, ProcessName, StartTime -AutoSize"

        Write-Host "`n--- Factory I/O process ---" -ForegroundColor Yellow
        Invoke-Remote "Get-Process 'Factory I/O*' -ErrorAction SilentlyContinue | Format-Table Id, ProcessName, StartTime -AutoSize"
    }

    "sync" {
        Write-Header "Git Pull on PLC Laptop"
        Invoke-Remote "Set-Location '$REPO_PATH'; & '$GIT_EXE' pull --ff-only"
        Write-Host "`nSync complete." -ForegroundColor Green
    }

    "deps" {
        Write-Header "Installing Missing Dependencies"
        Invoke-Remote "$PYTHON_EXE -m pip install httpx pyyaml --quiet"
        Write-Host ""
        Write-Host "Verifying installed packages:" -ForegroundColor Yellow
        Invoke-Remote "$PYTHON_EXE -m pip list --format=columns 2>`$null | Select-String -Pattern 'httpx|pyyaml|PyYAML' -CaseSensitive:`$false"
        Write-Host "`nDependencies installed." -ForegroundColor Green
    }

    "start-matrix" {
        Write-Header "Starting Matrix API on PLC Laptop"
        Invoke-Remote "New-Item -ItemType Directory -Path '$LOG_DIR' -Force | Out-Null; Start-Process -FilePath '$PYTHON_EXE' -ArgumentList '-m uvicorn services.matrix.app:app --host 0.0.0.0 --port 8000' -WorkingDirectory '$REPO_PATH' -RedirectStandardOutput '$LOG_DIR\matrix-stdout.log' -RedirectStandardError '$LOG_DIR\matrix-stderr.log' -WindowStyle Hidden"
        Write-Host "Matrix API started (port 8000). Logs: $LOG_DIR\matrix-*.log" -ForegroundColor Green
    }

    "start-bridge" {
        Write-Header "Starting Factory I/O Bridge on PLC Laptop"
        $bridgeArgs = if ($Extra) { $Extra } else { "--sim --interval 500" }
        Invoke-Remote "New-Item -ItemType Directory -Path '$LOG_DIR' -Force | Out-Null; Start-Process -FilePath '$PYTHON_EXE' -ArgumentList 'sim/factoryio_bridge.py $bridgeArgs' -WorkingDirectory '$REPO_PATH' -RedirectStandardOutput '$LOG_DIR\bridge-stdout.log' -RedirectStandardError '$LOG_DIR\bridge-stderr.log' -WindowStyle Hidden"
        Write-Host "Bridge started ($bridgeArgs). Logs: $LOG_DIR\bridge-*.log" -ForegroundColor Green
    }

    "start-watcher" {
        Write-Header "Starting Cosmos Watcher on PLC Laptop"
        Invoke-Remote "New-Item -ItemType Directory -Path '$LOG_DIR' -Force | Out-Null; Start-Process -FilePath '$PYTHON_EXE' -ArgumentList 'cosmos/watcher.py --matrix-url http://localhost:8000 --interval 5' -WorkingDirectory '$REPO_PATH' -RedirectStandardOutput '$LOG_DIR\watcher-stdout.log' -RedirectStandardError '$LOG_DIR\watcher-stderr.log' -WindowStyle Hidden"
        Write-Host "Cosmos watcher started (5s interval). Logs: $LOG_DIR\watcher-*.log" -ForegroundColor Green
    }

    "start-all" {
        Write-Header "Starting All Services on PLC Laptop"

        # Ensure log directory exists
        Invoke-Remote "New-Item -ItemType Directory -Path '$LOG_DIR' -Force | Out-Null"

        # 1. Matrix API
        Write-Host "`n[1/3] Matrix API..." -ForegroundColor Yellow
        Invoke-Remote "Start-Process -FilePath '$PYTHON_EXE' -ArgumentList '-m uvicorn services.matrix.app:app --host 0.0.0.0 --port 8000' -WorkingDirectory '$REPO_PATH' -RedirectStandardOutput '$LOG_DIR\matrix-stdout.log' -RedirectStandardError '$LOG_DIR\matrix-stderr.log' -WindowStyle Hidden"

        # Brief pause to let Matrix bind port 8000
        Start-Sleep -Seconds 3

        # 2. Factory I/O Bridge
        Write-Host "[2/3] Factory I/O Bridge (sim mode)..." -ForegroundColor Yellow
        $bridgeArgs = if ($Extra) { $Extra } else { "--sim --interval 500" }
        Invoke-Remote "Start-Process -FilePath '$PYTHON_EXE' -ArgumentList 'sim/factoryio_bridge.py $bridgeArgs' -WorkingDirectory '$REPO_PATH' -RedirectStandardOutput '$LOG_DIR\bridge-stdout.log' -RedirectStandardError '$LOG_DIR\bridge-stderr.log' -WindowStyle Hidden"

        # 3. Cosmos Watcher
        Write-Host "[3/3] Cosmos Watcher..." -ForegroundColor Yellow
        Invoke-Remote "Start-Process -FilePath '$PYTHON_EXE' -ArgumentList 'cosmos/watcher.py --matrix-url http://localhost:8000 --interval 5' -WorkingDirectory '$REPO_PATH' -RedirectStandardOutput '$LOG_DIR\watcher-stdout.log' -RedirectStandardError '$LOG_DIR\watcher-stderr.log' -WindowStyle Hidden"

        Write-Host "`nAll 3 services started." -ForegroundColor Green
        Write-Host "  Matrix API:    http://100.72.2.99:8000"
        Write-Host "  Bridge:        sim mode ($bridgeArgs)"
        Write-Host "  Cosmos watcher: 5s interval"
        Write-Host "  Logs:          $LOG_DIR\"
    }

    "stop-all" {
        Write-Header "Stopping All Python Services on PLC Laptop"
        Invoke-Remote "Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Write-Host 'All Python processes stopped.'"
        Write-Host "Done." -ForegroundColor Green
    }

    "logs" {
        Write-Header "Recent Logs from PLC Laptop"
        $logFile = if ($Extra) { $Extra } else { "matrix" }

        switch ($logFile) {
            "matrix"  { $pattern = "matrix-stderr.log" }
            "bridge"  { $pattern = "bridge-stderr.log" }
            "watcher" { $pattern = "watcher-stderr.log" }
            default   { $pattern = "$logFile" }
        }

        Write-Host "Showing last 40 lines of ${pattern}:" -ForegroundColor Yellow
        $remoteLogPath = "$LOG_DIR\$pattern"
        Invoke-Remote "if (Test-Path '$remoteLogPath') { Get-Content '$remoteLogPath' -Tail 40 } else { Write-Host 'Log file not found: $remoteLogPath' -ForegroundColor Red }"
    }

    "check-factoryio" {
        Write-Header "Factory I/O Process Check"
        Invoke-Remote "
            `$fio = Get-Process 'Factory I/O*' -ErrorAction SilentlyContinue
            if (`$fio) {
                Write-Host 'Factory I/O is RUNNING' -ForegroundColor Green
                `$fio | Format-Table Id, ProcessName, StartTime -AutoSize
            } else {
                Write-Host 'Factory I/O is NOT running' -ForegroundColor Red
            }
        "
    }
}
