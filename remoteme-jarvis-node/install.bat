@echo off
echo === Jarvis Node Installer (Windows) ===
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install fastapi uvicorn psutil mss

REM Generate token if not set
if "%JARVIS_TOKEN%"=="" (
    echo.
    echo WARNING: JARVIS_TOKEN not set. Generating one...
    for /f %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set JARVIS_TOKEN=%%i
    echo Your token: %JARVIS_TOKEN%
    echo.
    echo SET THIS on all machines that need to talk to this node:
    echo   set JARVIS_TOKEN=%JARVIS_TOKEN%
    echo.
    echo To persist, add to System Environment Variables.
    echo.
)

REM Get Tailscale IP
echo Detecting Tailscale IP...
for /f "tokens=*" %%i in ('tailscale ip -4 2^>nul') do set TAILSCALE_IP=%%i
if "%TAILSCALE_IP%"=="" (
    echo WARNING: Tailscale not detected. Binding to 0.0.0.0 (UNSAFE on public networks)
    set TAILSCALE_IP=0.0.0.0
) else (
    echo Tailscale IP: %TAILSCALE_IP%
)

echo.
echo Starting Jarvis Node on %TAILSCALE_IP%:8765...
echo Press Ctrl+C to stop.
echo.
python -m uvicorn jarvis_node:app --host %TAILSCALE_IP% --port 8765
