#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "Ejecute ./install_macos.sh primero." >&2; exit 1; fi
source .venv/bin/activate
(sleep 1; open http://127.0.0.1:8787 >/dev/null 2>&1 || true) &
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
