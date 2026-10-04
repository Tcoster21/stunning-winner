@echo off
rem Double-click this to open the Genre Retagger on Windows.
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && (set "PY=py -3" & set "PYW=pyw -3")
if not defined PY where python >nul 2>nul && (set "PY=python" & set "PYW=pythonw")
if not defined PY (
  echo Python 3 is not installed. Download it from https://www.python.org/downloads/
  echo During setup, tick "Add python.exe to PATH".
  pause
  exit /b 1
)

%PY% -c "import mutagen" >nul 2>nul
if errorlevel 1 (
  echo First run: installing mutagen, this only happens once...
  %PY% -m pip install --user -q mutagen
  if errorlevel 1 (
    echo Could not install mutagen. Check your internet connection and try again.
    pause
    exit /b 1
  )
)

start "" %PYW% retag_gui.py
