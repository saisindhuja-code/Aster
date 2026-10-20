@echo off
REM Starts Aster with a visible console so you can see any error messages.
cd /d "%~dp0"
".venv\Scripts\python.exe" run_aster.py
pause
