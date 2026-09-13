import json
from pathlib import Path

from app.licensing import StandaloneFileLicenseProvider

ROOT = Path(__file__).resolve().parent.parent


def test_packaged_license_is_valid():
    status = StandaloneFileLicenseProvider().status()
    assert status["valid"] is True
    assert status["payload"]["server_oficina_ready"] is True


def test_tampered_license_is_rejected(tmp_path: Path):
    source = json.loads((ROOT / "license/license.local.json").read_text(encoding="utf-8"))
    source["payload"]["organization"] = "tampered"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(source), encoding="utf-8")
    status = StandaloneFileLicenseProvider(bad, ROOT / "license/public_key.pem").status()
    assert status["valid"] is False
