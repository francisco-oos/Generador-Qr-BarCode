import io
import json
import zipfile
from fastapi.testclient import TestClient

from app.main import app

CLB = b'''<?xml version="1.0"?><MaterialLibrary><Material name="Existing INOVA"><Entry Thickness="2" Desc="Known good shop setting"><CutSetting type="Scan"><name Value="Visible mark"/><speed Value="3200"/><minPower Value="18"/><maxPower Value="32"/><interval Value="0.08"/><numPasses Value="1"/></CutSetting></Entry></Material></MaterialLibrary>'''


def test_machine_import_persists_material_preset_and_batch_references_it():
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/machine/import?machine_profile_id=sculpfun_s9_pro_10w",
            files={"file": ("shop-settings.clb", CLB, "application/octet-stream")},
        )
        assert uploaded.status_code == 200, uploaded.text
        body = uploaded.json()
        assert body["imported"] is True
        assert body["material_preset_count"] == 1
        preset_id = body["stored"]["material_preset_ids"][0]

        payload = {
            "template_id": "inova_quantum_code128_v1",
            "jig_id": "inova_single_calibration",
            "rows": [{"manufacturer_id": "Q00525499"}],
            "assignments": [{"slot_index": 0, "row_index": 0, "physical_id": "Q00525499"}],
            "require_physical_confirmation": True,
            "output_dpi": 300,
            "material_preset_id": preset_id,
        }
        exported = client.post("/api/batch/export", json=payload)
        assert exported.status_code == 200, exported.text
        with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
            meta = json.loads(z.read("manifest/job.json"))
        assert meta["material_preset"]["id"] == preset_id
        assert meta["material_preset"]["settings"]["speed"] == 3200
        assert "no envía" in meta["safety"]


def test_manual_render_applies_prefix_but_import_batch_does_not():
    with TestClient(app) as client:
        render = client.post("/api/render", json={
            "template_id": "inova_quantum_code128_v1",
            "data": {"manufacturer_id": "525499"},
            "capture_mode": "manual",
            "output": "svg",
        })
        assert render.status_code == 200
        assert render.json()["resolved"]["manufacturer_id"] == "Q00525499"
