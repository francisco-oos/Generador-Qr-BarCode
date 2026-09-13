from copy import deepcopy

from fastapi.testclient import TestClient

from app.config_loader import load_quality_profiles, load_scanners, load_templates
from app.code_quality import assess_template_codes
from app.main import app


def test_quality_preflight_decodes_inova_and_phone_with_real_values():
    templates = load_templates()
    qualities = load_quality_profiles()
    scanners = load_scanners()
    scanner = scanners["steren_com_597"]

    cases = [
        ("inova_quantum_code128_v1", {"manufacturer_id": "Q00525499"}, "Q00525499"),
        ("phone_qr_economic_v1", {"economic_number": "TEL-0037", "asset_id": "PHONE-000037"}, "PHONE-000037"),
    ]
    for template_id, data, expected in cases:
        t = templates[template_id]
        report = assess_template_codes(t, qualities[t.quality_profile], data, scanner=scanner)
        assert report["overall"] in {"ROBUSTO", "ACEPTABLE"}
        assert report["results"]
        result = report["results"][0]
        assert result["value"] == expected
        assert result["scanner"]["supported"] is True
        assert result["digital"]["available"] is True
        assert result["digital"]["variants"][0]["pass"] is True


def test_quality_preflight_flags_undersized_module():
    templates = load_templates()
    qualities = load_quality_profiles()
    t = deepcopy(templates["inova_quantum_code128_v1"])
    t.elements[0].module_mm = 0.12
    report = assess_template_codes(t, qualities[t.quality_profile], {"manufacturer_id": "Q00525499"}, digital_stress=False)
    result = report["results"][0]
    assert result["classification"] in {"FRAGIL", "NO_LEGIBLE"}
    assert any(c["level"] == "warn" and "módulo" in c["message"].lower() for c in result["checks"])


def test_quality_endpoint_accepts_unsaved_visual_template_and_scanner_profile():
    t = load_templates()["inova_quantum_code128_v1"].model_dump()
    with TestClient(app) as client:
        response = client.post("/api/quality/check", json={
            "template": t,
            "data": {"manufacturer_id": "Q00525499"},
            "capture_mode": "manual",
            "scanner_profile_id": "steren_com_597",
            "digital_stress": True,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["overall"] in {"ROBUSTO", "ACEPTABLE"}
        assert body["results"][0]["digital"]["variants"][0]["pass"] is True
        assert any("100%" in n for n in body["notes"])
