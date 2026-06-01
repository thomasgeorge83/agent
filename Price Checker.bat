@echo off
rem Double-click launcher for the Amazon Price Checker GUI.
rem Uses the project's existing .venv (created during setup) and pythonw.exe
rem so no console window appears. Does NOT recreate the venv.

setlocal
cd /d "%~dp0"

set "PYW=.venv\Scripts\pythonw.exe"
set "PY=.venv\Scripts\python.exe"

if not exist "%PYW%" (
  echo Could not find the project virtual environment at .venv\
  echo Set it up once, then try again:
  echo     py -3.12 -m venv .venv
  echo     .venv\Scripts\python -m pip install -r requirements.txt
  echo     .venv\Scripts\python -m playwright install chromium
  echo.
  pause
  exit /b 1
)

start "" "%PYW%" "gui.py"
endlocal
