@echo off
title SWITCH HR Analytics
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed.
  echo Install Python 3.12 from python.org and tick "Add Python to PATH", then run this again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup: installing the required packages. This can take a few minutes...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

start "" cmd /c "timeout /t 4 >nul & start http://localhost:8501"
streamlit run app.py --server.headless true --browser.gatherUsageStats false
pause