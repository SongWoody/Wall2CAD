@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install the editor environment first. See README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m contour_editor %*
if errorlevel 1 pause
