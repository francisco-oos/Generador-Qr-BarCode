#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3,12): raise SystemExit("Se requiere Python 3.12 o posterior")
PY
if [ ! -d .venv ]; then "$PYTHON_BIN" -m venv .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m compileall -q app scripts
echo "Instalación completada. Ejecute ./run_linux.sh"
