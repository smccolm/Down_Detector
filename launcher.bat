@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Venv not found. Run setup_venv.bat first.
  pause
  exit /b 1
)

if not exist "Logs" (
  mkdir "Logs"
)

echo Starting Down Detector...
echo Open: http://127.0.0.1:7860
echo Close this window to stop the app.
echo.

call ".venv\Scripts\python.exe" app.py

endlocal
