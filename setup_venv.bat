@echo off
setlocal

cd /d "%~dp0"

py -m venv .venv
if errorlevel 1 (
  echo Failed to create venv.
  pause
  exit /b 1
)

call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip.
  pause
  exit /b 1
)

call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install requirements.
  pause
  exit /b 1
)

echo.
echo OK. Virtual environment is ready.
echo Next: run launcher.bat
echo.
pause
endlocal
