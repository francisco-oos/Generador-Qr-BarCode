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


def test_visual_template_preview_without_persisting():
    with TestClient(app) as client:
        draft = {
            "id": "qa_visual_draft",
            "name": "QA visual draft",
            "version": "1.0",
            "category": "qa",
            "width_mm": 40,
            "height_mm": 20,
            "quality_profile": "rugged_field_v1",
            "calibration_required": True,
            "expected_fields": ["serial"],
            "input_rules": [],
            "elements": [
                {"kind":"code128","x_mm":1,"y_mm":1,"source":"serial","width_mm":38,"height_mm":9,"align":"center","font_size_mm":4,"error_correction":"M","stroke_mm":0.25},
                {"kind":"text","x_mm":1,"y_mm":18,"source":"serial","width_mm":38,"font_size_mm":3.5,"align":"center","error_correction":"M","stroke_mm":0.25},
            ],
            "metadata": {"primary_identity_field":"serial"},
        }
        r = client.post("/api/templates/preview", json={"template": draft, "data":{"serial":"ABC123"}, "capture_mode":"manual", "output":"svg"})
        assert r.status_code == 200
        body = r.json()
        assert "<svg" in body["svg"]
        assert "ABC123" in body["svg"]
        # Preview is ephemeral; it must not appear in the persisted catalog.
        c = client.get("/api/catalog").json()
        assert not any(x["id"] == "qa_visual_draft" for x in c["templates"])


def test_headerless_single_column_csv_keeps_first_serial_and_explicit_modes():
    data = b"Q00525499\nQ00525500\nQ00525501\n"
    with TestClient(app) as client:
        auto = client.post("/api/csv/inspect?header_mode=auto", files={"file": ("serials.txt", data, "text/plain")})
        assert auto.status_code == 200
        assert auto.json()["headers"] == ["value"]
        assert [r["value"] for r in auto.json()["rows"]] == ["Q00525499","Q00525500","Q00525501"]
        yes = client.post("/api/csv/inspect?header_mode=yes", files={"file": ("serials.csv", b"serial\nA1\nA2\n", "text/csv")})
        assert yes.status_code == 200
        assert yes.json()["headers"] == ["serial"]
        assert len(yes.json()["rows"]) == 2


def test_bulk_svg_export_1000_records_uses_same_template():
    import io
    import zipfile
    rows = [{"manufacturer_id": f"Q00{525499+i:06d}"} for i in range(1000)]
    with TestClient(app) as client:
        r = client.post("/api/bulk/svg-export", json={
            "template_id":"inova_quantum_code128_v1",
            "rows": rows,
            "filename_field":"manufacturer_id",
        })
        assert r.status_code == 200
        assert r.headers["x-record-count"] == "1000"
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            svg_names = [n for n in z.namelist() if n.startswith("svg/") and n.endswith(".svg")]
            assert len(svg_names) == 1000
            assert "svg/Q00525499.svg" in svg_names
            assert "manifest/manifest.csv" in z.namelist()
            first = z.read("svg/Q00525499.svg").decode("utf-8")
            assert "Q00525499" in first
