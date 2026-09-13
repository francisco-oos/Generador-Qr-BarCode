from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_health_and_catalog():
    with TestClient(app) as client:
        h = client.get("/api/health")
        assert h.status_code == 200
        assert h.json()["license_valid"] is True
        c = client.get("/api/catalog")
        assert c.status_code == 200
        body = c.json()
        assert len(body["templates"]) >= 5
        assert len(body["scanners"]) >= 2


def test_render_endpoint():
    with TestClient(app) as client:
        r = client.post("/api/render", json={
            "template_id":"inova_quantum_code128_v1",
            "data":{"manufacturer_id":"Q00525499"},
            "output":"svg"
        })
        assert r.status_code == 200
        assert "<svg" in r.json()["svg"]


def test_series_generation_supports_1000_plus():
    with TestClient(app) as client:
        r = client.post("/api/series/generate", json={
            "field":"manufacturer_id",
            "prefix":"Q00",
            "start":525499,
            "count":1200,
            "width":6,
            "suffix":"",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1200
        assert body["first"] == "Q00525499"
        assert body["last"] == "Q00526698"
        assert len(body["rows"]) == 1200



def test_batch_export_zip_and_verify():
    import io
    import zipfile
    with TestClient(app) as client:
        payload = {
            "template_id":"inova_quantum_code128_v1",
            "jig_id":"inova_single_calibration",
            "rows":[{"manufacturer_id":"Q00525499"}],
            "assignments":[{"slot_index":0,"row_index":0,"physical_id":"Q00525499"}],
            "require_physical_confirmation":True,
            "output_dpi":300,
        }
        r = client.post("/api/batch/export", json=payload)
        assert r.status_code == 200
        assert r.headers.get("x-job-id")
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            names=set(z.namelist())
            assert "engraving/batch.svg" in names
            assert "engraving/batch_300dpi.png" in names
            assert "manifest/manifest.csv" in names
            assert "manifest/job.json" in names
        v = client.post("/api/scan/verify", json={
            "expected":"Q00525499",
            "scanned":"Q00525499",
            "normalize":False,
        })
        assert v.status_code == 200
        assert v.json()["matched"] is True
        assert v.json()["history_update"]["updated"] is True



def test_material_reference_api_and_phone_lookup():
    with TestClient(app) as client:
        materials = client.get("/api/materials/reference", params={"category": "plastic"})
        assert materials.status_code == 200
        body = materials.json()
        assert any(x["id"] == "pvc_vinyl" for x in body["materials"])

        phone = client.get("/api/materials/phone", params={"brand": "CUBOT", "model": "KingKong 9"})
        assert phone.status_code == 200
        assert phone.json()["matches"][0]["id"] == "cubot_kingkong_9"


def test_calibration_and_shop_preset_endpoints():
    with TestClient(app) as client:
        cal = client.get("/api/calibration/jig/inova_tray_3x4_estimate")
        assert cal.status_code == 200
        body = cal.json()
        assert len(body["reference_points"]) == 3
        assert "CALIBRATION ONLY" in body["svg"]
        ev = client.post("/api/calibration/evaluate", json={
            "jig_id":"inova_tray_3x4_estimate",
            "measured": body["reference_points"],
        })
        assert ev.status_code == 200
        assert ev.json()["within_guidance"] is True

        save = client.post("/api/materials/shop-preset", json={
            "name":"S9 Pro INOVA visible test",
            "machine_profile_id":"sculpfun_s9_pro_10w",
            "material":"INOVA yellow housing",
            "surface_or_model":"Quantum housing",
            "operation":"engrave",
            "speed_mm_min":3200,
            "power_percent":32,
            "passes":1,
            "interval_mm":0.08,
            "focus_reference_mm":50,
            "laser_mode":"M4",
            "validated_on_exact_machine_surface":True,
            "notes":"Existing shop baseline",
        })
        assert save.status_code == 200
        assert save.json()["status"] == "validated"
        caps = client.get("/api/machine/captures").json()
        assert any(p["material"] == "INOVA yellow housing" for p in caps["material_presets"])


def test_csv_upload_inspect_1200_real_sample():
    """Exercise the HTTP multipart upload path, not only the CSV parser directly."""
    sample = ROOT / "samples" / "input" / "inova_1200.csv"
    with TestClient(app) as client, sample.open("rb") as fh:
        response = client.post("/api/csv/inspect", files={"file": (sample.name, fh, "text/csv")})
        assert response.status_code == 200
        body = response.json()
        assert len(body["rows"]) == 1200
        assert "manufacturer_id" in body["headers"]
