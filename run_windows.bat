@echo off
setlocal
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Marking Studio no esta instalado. Ejecute install_windows.bat primero.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
start "" http://127.0.0.1:8787
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
endlocal
