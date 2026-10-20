@echo off
REM ============================================================
REM  Aster - one-time setup (creates a private .venv in this folder)
REM  Nothing is installed system-wide. Safe to run again.
REM ============================================================
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" ( where python >nul 2>nul && set PY=python )
if "%PY%"=="" (
  echo Python was not found. Install Python 3.10+ from https://www.python.org/downloads/windows/
  echo and tick "Add python.exe to PATH" during setup. Then run this file again.
  pause
  exit /b 1
)
%PY% --version
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment .venv ...
  %PY% -m venv .venv || ( echo Could not create .venv & pause & exit /b 1 )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || ( echo Installing PySide6 failed - see docs\TROUBLESHOOTING.md & pause & exit /b 1 )
echo.
set /p OPT="Also install optional PDF/Word readers for the Study Room? (y/N): "
if /i "%OPT%"=="y" ".venv\Scripts\python.exe" -m pip install -r requirements-optional.txt
echo.
echo Running automated tests...
".venv\Scripts\python.exe" -m unittest discover -s tests
echo.
echo Checking Ollama...
where ollama >nul 2>nul && ( ollama list ) || echo Ollama not found on PATH - install it from https://ollama.com/download/windows
echo.
echo Setup finished. Start Aster with start_aster.bat
pause
