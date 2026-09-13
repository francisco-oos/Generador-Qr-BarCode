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
python - <<'PYZ'
try:
    from pyzbar.pyzbar import decode  # noqa: F401
    print("[Marking Studio] Verificador digital QR/barcode: disponible")
except Exception as exc:
    print("[Marking Studio] AVISO: verificador digital opcional no disponible:", exc)
    print("  macOS con Homebrew: brew install zbar")
PYZ
python -m compileall -q app scripts
printf 'Instalación completada. Ejecute ./run_macos.sh\n'
