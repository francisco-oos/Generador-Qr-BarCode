@echo off
setlocal
cd /d %~dp0
echo [Marking Studio] Preparando entorno local...
set PY_CMD=
py -3.13 -c "import sys" >nul 2>&1 && set PY_CMD=py -3.13
if not defined PY_CMD py -3.12 -c "import sys" >nul 2>&1 && set PY_CMD=py -3.12
if not defined PY_CMD python -c "import sys; assert sys.version_info >= (3,12)" >nul 2>&1 && set PY_CMD=python
if not defined PY_CMD goto :nopython
if not exist .venv (
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :fail
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
python -m compileall -q app scripts
if errorlevel 1 goto :fail
echo.
echo Instalacion completada. Ejecute run_windows.bat.
pause
exit /b 0
:nopython
echo ERROR: instale Python 3.12 o 3.13 (64-bit) y habilite el launcher py.
pause
exit /b 1
:fail
echo.
echo ERROR: no se pudo completar la instalacion.
pause
exit /b 1
