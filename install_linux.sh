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
# pyzbar is optional at runtime but enables the in-app digital scan stress test.
# On Debian/Ubuntu its native zbar library may need to be installed once.
python - <<'PYZ'
try:
    from pyzbar.pyzbar import decode  # noqa: F401
    print("[Marking Studio] Verificador digital QR/barcode: disponible")
except Exception as exc:
    print("[Marking Studio] AVISO: verificador digital opcional no disponible:", exc)
    print("  Debian/Ubuntu: sudo apt install libzbar0")
PYZ
python -m compileall -q app scripts
echo "Instalación completada. Ejecute ./run_linux.sh"
