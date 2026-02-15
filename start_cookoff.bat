@echo off
REM FactoryLM Cosmos Cookoff - Quick Start
REM Double-click this file or run from command line

cd /d "%~dp0"

REM Set API key if not already set (get from Doppler or set manually)
if "%NVIDIA_COSMOS_API_KEY%"=="" (
    echo [!] NVIDIA_COSMOS_API_KEY not set. Run: set NVIDIA_COSMOS_API_KEY=your-key-here
    echo     Or configure via Doppler. Falling back to stub responses.
)

echo.
echo ============================================================
echo FACTORYLM COSMOS COOKOFF
echo ============================================================
echo.
echo Options:
echo   1. Full stack (Docker + Bridge + Live test)
echo   2. Live test only (no Docker)
echo   3. Check status
echo   4. Exit
echo.
set /p choice="Select option (1-4): "

if "%choice%"=="1" python start_cookoff.py
if "%choice%"=="2" python start_cookoff.py --live-only
if "%choice%"=="3" python start_cookoff.py --check
if "%choice%"=="4" exit

pause
