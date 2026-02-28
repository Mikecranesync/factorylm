@echo off
setlocal

echo === Building GitHub Scraper for Windows ===
echo.

REM ── Resolve monorepo root (two levels up from _BUILDS/github-scraper/) ──
set "MONOREPO=%~dp0..\.."
pushd "%MONOREPO%"
set "MONOREPO=%CD%"
popd

echo Monorepo root: %MONOREPO%

REM ── Check source files exist ──
if not exist "%MONOREPO%\apps\github-scraper\app.py" (
    echo ERROR: apps\github-scraper\app.py not found.  Are you on the right branch?
    exit /b 1
)

REM ── Install dependencies ──
echo.
echo [1/3] Installing dependencies...
pip install -r "%~dp0requirements.txt"
pip install pyinstaller

REM ── Build ──
echo.
echo [2/3] Running PyInstaller...
python -m PyInstaller ^
    --name "GitHub-Scraper" ^
    --onefile ^
    --windowed ^
    --collect-all nicegui ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --exclude-module pymodbus ^
    --exclude-module snap7 ^
    --add-data "%MONOREPO%\apps\github-scraper;github_scraper" ^
    "%~dp0main.py"

REM ── Done ──
echo.
if exist dist\GitHub-Scraper.exe (
    echo [3/3] SUCCESS!  Output: dist\GitHub-Scraper.exe
    echo       Size:
    for %%A in (dist\GitHub-Scraper.exe) do echo       %%~zA bytes
) else (
    echo [3/3] FAILED — check the PyInstaller output above.
    exit /b 1
)

endlocal
