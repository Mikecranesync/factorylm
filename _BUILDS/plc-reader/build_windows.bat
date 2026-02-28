@echo off
setlocal

echo === Building PLC Reader for Windows ===
echo.

REM ── Resolve monorepo root (two levels up from _BUILDS/plc-reader/) ──
set "MONOREPO=%~dp0..\.."
pushd "%MONOREPO%"
set "MONOREPO=%CD%"
popd

echo Monorepo root: %MONOREPO%

REM ── Check source files exist ──
if not exist "%MONOREPO%\apps\plc-reader\app.py" (
    echo ERROR: apps\plc-reader\app.py not found.  Are you on the right branch?
    exit /b 1
)
if not exist "%MONOREPO%\packages\factorylm-cli\src\factorylm\plc\__init__.py" (
    echo ERROR: packages\factorylm-cli\src\factorylm\plc\ not found.
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
    --name "PLC-Reader" ^
    --onefile ^
    --windowed ^
    --collect-all nicegui ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --add-data "%MONOREPO%\apps\plc-reader;plc_reader" ^
    --add-data "%MONOREPO%\packages\factorylm-cli\src;plc_lib" ^
    "%~dp0main.py"

REM ── Done ──
echo.
if exist dist\PLC-Reader.exe (
    echo [3/3] SUCCESS!  Output: dist\PLC-Reader.exe
    echo       Size:
    for %%A in (dist\PLC-Reader.exe) do echo       %%~zA bytes
) else (
    echo [3/3] FAILED — check the PyInstaller output above.
    exit /b 1
)

endlocal
