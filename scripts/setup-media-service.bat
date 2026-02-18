@echo off
REM Quick setup for Media Offload Agent service
REM Run as Administrator

echo ========================================
echo FactoryLM Media Offload Agent Setup
echo ========================================
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Please run as Administrator
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Check Python
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python not found in PATH
    pause
    exit /b 1
)

echo Python found.

REM Check rclone
rclone --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] rclone not found. Installing via winget...
    winget install Rclone.Rclone
)

echo rclone found.

REM Create log directory
if not exist "%USERPROFILE%\.openclaw\logs" (
    mkdir "%USERPROFILE%\.openclaw\logs"
)

REM Run PowerShell setup script
echo.
echo Setting up scheduled task...
powershell -ExecutionPolicy Bypass -File "%~dp0setup-media-offload-task.ps1" -IntervalMinutes 5

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Configure rclone for Google Drive: rclone config
echo 2. Test sync manually: python services/media/media_offload_agent.py --once
echo 3. Check task status: schtasks /query /tn FactoryLM-MediaOffloadAgent
echo.
pause
