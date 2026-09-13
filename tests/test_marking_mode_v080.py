from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app import config_loader
from app.barcode_engine import code128_fragment, negative_background_fragment
from app.code_quality import assess_template_codes
from app.config_loader import load_quality_profiles, load_scanners, load_templates
from app.main import app
from app.models import ElementSpec, MarkingMode, TemplateSpec
from app.template_engine import render_template


# WHY: Canonicaliza sólo metadatos de ejecución; la geometría productiva positiva debe seguir siendo la de v0.7.1.
def _without_metadata(svg: str) -> str:
    return re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)


# WHY: Extrae IDs de todo el documento para detectar colisiones XML también en salidas negativas.
def _ids(svg: str) -> list[str]:
    root = ET.fromstring(svg)
    return [v for node in root.iter() if (v := node.attrib.get("id"))]


# WHY: La plantilla INOVA es un fixture real del proyecto y evita inventar otra geometría para probar el modo físico.
def _inova():
    template = load_templates()["inova_quantum_code128_v1"].model_copy(deep=True)
    quality = load_quality_profiles()[template.quality_profile]
    return template, quality


def test_default_positive_geometry_matches_v071_canonical_baseline():
    """New defaults must not alter v0.7.1 production geometry.

    The digest was measured from the authoritative v0.7.1 package after stripping
    only its metadata block.  Version metadata is expected to change; paths/layers
    and positions are not.
    """
    template, quality = _inova()
    rendered = render_template(template, quality, {"manufacturer_id": "Q00525499"})
    digest = hashlib.sha256(_without_metadata(rendered.svg).encode("utf-8")).hexdigest()
    assert digest == "6928b12872edc7b19b433ea92a3483de799db3e9c6946b04a6025046c0dc7084"
    assert rendered.marking_mode["polarity"] == "positive"
    assert rendered.estimated_ablation_mm2 is None


def test_negative_codes_islands_has_field_holes_metadata_and_unique_ids():
    template, quality = _inova()
    mode = MarkingMode(
        polarity="negative", polarity_scope="codes", negative_field="islands",
        field_margin_mm=0.8, kerf_compensation_mm=0,
    )
    rendered = render_template(template, quality, {"manufacturer_id": "Q00525499"}, marking_mode_override=mode)
    assert 'fill-rule="evenodd"' in rendered.svg
    assert 'polarity="negative"' in rendered.svg
    assert 'polarity_scope="codes"' in rendered.svg
    assert 'negative_field="islands"' in rendered.svg
    assert rendered.estimated_ablation_mm2 and rendered.estimated_ablation_mm2 > 0
    ids = _ids(rendered.svg)
    assert len(ids) == len(set(ids))
    assert "barcode_manufacturer_id" in ids
    # Only codes invert in this mode; human-readable text remains a normal text node.
    assert "<text" in rendered.svg


def test_field_margin_expands_only_negative_field_not_canonical_modules():
    base = code128_fragment("Q00525499", 0, 0, 0.33, 10.0, 10)
    zero = negative_background_fragment(base, 0, 0, field_margin_mm=0, kerf_compensation_mm=0)
    margin = negative_background_fragment(base, 0, 0, field_margin_mm=1.5, kerf_compensation_mm=0)
    assert margin.width_mm == pytest.approx(base.width_mm + 3.0)
    assert margin.height_mm == pytest.approx(base.height_mm + 3.0)
    # The source/canonical code geometry itself is immutable.
    assert base.rects == code128_fragment("Q00525499", 0, 0, 0.33, 10.0, 10).rects
    assert zero.svg != margin.svg


def test_kerf_zero_is_identity_and_positive_compensation_expands_protected_holes():
    base = code128_fragment("Q00525499", 0, 0, 0.33, 10.0, 10)
    legacy_equivalent = negative_background_fragment(base, 0, 0)
    zero = negative_background_fragment(base, 0, 0, kerf_compensation_mm=0)
    compensated = negative_background_fragment(base, 0, 0, kerf_compensation_mm=0.10, kerf_compensate_y=False)
    assert zero.svg == legacy_equivalent.svg
    assert compensated.svg != zero.svg
    # A 0.10 mm TOTAL recovery means 0.05 mm expansion on each side.
    first_x, first_y, first_w, first_h = base.rects[0]
    assert f"M {first_x - 0.05:.4f} {first_y:.4f}" in compensated.svg
    assert f"h {first_w + 0.10:.4f}" in compensated.svg


def test_negative_all_islands_converts_text_to_geometry_and_preserves_semantic_ids():
    template, quality = _inova()
    template.elements[0].rotation_deg = 90
    template.elements[1].rotation_deg = 90
    mode = MarkingMode(polarity="negative", polarity_scope="all", negative_field="islands", field_margin_mm=0.5)
    rendered = render_template(template, quality, {"manufacturer_id": "Q00525499"}, marking_mode_override=mode)
    ids = _ids(rendered.svg)
    assert "barcode_manufacturer_id" in ids
    assert "text_manufacturer_id" in ids
    assert len(ids) == len(set(ids))
    assert '<text' not in rendered.svg
    assert 'rotate(90.0000' in rendered.svg
    assert rendered.marking_mode["polarity_scope"] == "all"


def test_negative_all_template_is_fused_and_documents_structural_loss():
    template, quality = _inova()
    mode = MarkingMode(polarity="negative", polarity_scope="all", negative_field="template")
    rendered = render_template(template, quality, {"manufacturer_id": "Q00525499"}, marking_mode_override=mode)
    ids = _ids(rendered.svg)
    assert "negative_template_field" in ids
    assert "barcode_manufacturer_id" not in ids
    assert "text_manufacturer_id" not in ids
    assert 'fill-rule="evenodd"' in rendered.svg
    assert any("fusion" in w.lower() or "fusionó" in w.lower() for w in rendered.warnings)
    assert rendered.estimated_ablation_ratio == pytest.approx(1.0)


def test_negative_codes_template_is_explicit_two_stage_artifact_and_uneditable_all_is_rejected():
    template, quality = _inova()
    two_stage = render_template(
        template, quality, {"manufacturer_id": "Q00525499"},
        marking_mode_override=MarkingMode(polarity="negative", polarity_scope="codes", negative_field="template"),
    )
    assert 'requires_secondary_operation="true"' in two_stage.svg
    assert 'id="negative_template_field"' in two_stage.svg
    assert 'id="text_manufacturer_id"' in two_stage.svg
    assert 'id="barcode_manufacturer_id"' not in two_stage.svg
    assert any("DOS ETAPAS" in w for w in two_stage.warnings)
    with pytest.raises(ValueError, match="No es compatible con el maestro editable"):
        render_template(
            template, quality, {"manufacturer_id": "Q00525499"}, mode="editable",
            marking_mode_override=MarkingMode(polarity="negative", polarity_scope="all", negative_field="islands"),
        )
    rotated = template.model_copy(deep=True)
    rotated.elements[0].rotation_deg = 90
    with pytest.raises(ValueError, match="elementos rotados"):
        render_template(
            rotated, quality, {"manufacturer_id": "Q00525499"},
            marking_mode_override=MarkingMode(polarity="negative", polarity_scope="all", negative_field="template"),
        )


def test_preflight_always_uses_positive_canonical_geometry_for_negative_output():
    template, quality = _inova()
    scanner = load_scanners()["steren_com_597"]
    positive = assess_template_codes(
        template, quality, {"manufacturer_id": "Q00525499"}, scanner=scanner, digital_stress=False,
    )
    negative = assess_template_codes(
        template, quality, {"manufacturer_id": "Q00525499"}, scanner=scanner, digital_stress=False,
        marking_mode_override=MarkingMode(polarity="negative", polarity_scope="codes", negative_field="islands", field_margin_mm=4.0, kerf_compensation_mm=0.2),
    )
    assert negative["preflight_geometry"] == "positive_canonical"
    p, n = positive["results"][0], negative["results"][0]
    for key in ("value", "module_mm", "symbol_width_mm", "symbol_height_mm", "quiet_modules"):
        assert n[key] == p[key]
    assert n["polarity"] == "negative"
    assert n["physical_validation_required"] is True
    assert any("preflight positivo" in c["message"].lower() for c in n["checks"])


def test_template_version_bumps_only_when_physical_marking_fingerprint_changes(tmp_path, monkeypatch):
    # Capture the real fixture before redirecting CONFIG to the isolated temp tree.
    template, _ = _inova()
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True)
    monkeypatch.setattr(config_loader, "CONFIG", tmp_path)
    config_loader.load_templates.cache_clear()
    template.id = "qa_marking_mode_version"
    template.version = "2.3"
    (templates_dir / f"{template.id}.json").write_text(
        json.dumps(template.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    note_only = template.model_copy(deep=True)
    note_only.marking_mode.validated_on = "pieza descarte 2026-09-13"
    config_loader.save_template(note_only)
    assert note_only.version == "2.3"

    changed = note_only.model_copy(deep=True)
    changed.marking_mode.polarity = "negative"
    config_loader.save_template(changed)
    assert changed.version == "2.4"
    stored = json.loads((templates_dir / f"{template.id}.json").read_text(encoding="utf-8"))
    assert stored["version"] == "2.4"
    config_loader.load_templates.cache_clear()


def test_api_comparison_and_negative_bulk_filename_and_history_traceability():
    with TestClient(app) as client:
        template = next(t for t in client.get("/api/catalog").json()["templates"] if t["id"] == "inova_quantum_code128_v1")
        comparison = client.post("/api/marking/compare", json={
            "template": template,
            "data": {"manufacturer_id": "Q00525499"},
            "negative_mode": {"polarity":"negative","polarity_scope":"codes","negative_field":"islands","field_margin_mm":0.5,"kerf_compensation_mm":0},
        })
        assert comparison.status_code == 200, comparison.text
        c = comparison.json()
        assert 'polarity="positive"' in c["positive_svg"]
        assert 'polarity="negative"' in c["negative_svg"]

        response = client.post("/api/bulk/svg-export", json={
            "template_id": "inova_quantum_code128_v1",
            "rows": [{"manufacturer_id":"Q00525499"}],
            "filename_pattern": "{manufacturer_id}",
            "marking_mode_override": {"polarity":"negative","polarity_scope":"codes","negative_field":"islands","field_margin_mm":0.5,"kerf_compensation_mm":0},
        })
        assert response.status_code == 200, response.text
        job_id = response.headers["x-job-id"]
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = set(zf.namelist())
            assert "svg/Q00525499_NEGATIVE.svg" in names
            metadata = json.loads(zf.read("manifest/job.json"))
            assert metadata["marking_mode"]["polarity"] == "negative"
            assert metadata["marking_mode"]["negative_field"] == "islands"
            notice = zf.read("README_FIRST.txt").decode("utf-8")
            assert "_NEGATIVE.svg" in notice
            assert "ABLACION" in notice
        hist = client.get("/api/history?limit=1000").json()["items"]
        row = next(x for x in hist if x["job_id"] == job_id)
        assert row["job_metadata"]["marking_mode"]["polarity"] == "negative"


def test_batch_negative_zip_uses_unmistakable_names_and_manifest_mode():
    with TestClient(app) as client:
        payload = {
            "template_id":"inova_quantum_code128_v1",
            "jig_id":"inova_single_calibration",
            "rows":[{"manufacturer_id":"Q00525499"}],
            "assignments":[{"slot_index":0,"row_index":0,"physical_id":"Q00525499"}],
            "require_physical_confirmation":True,
            "output_dpi":300,
            "marking_mode_override":{"polarity":"negative","polarity_scope":"codes","negative_field":"islands","field_margin_mm":0,"kerf_compensation_mm":0},
        }
        response = client.post("/api/batch/export", json=payload)
        assert response.status_code == 200, response.text
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = set(zf.namelist())
            assert "engraving/batch_NEGATIVE.svg" in names
            assert "engraving/batch_NEGATIVE_300dpi.png" in names
            meta = json.loads(zf.read("manifest/job.json"))
            assert meta["marking_mode"]["polarity"] == "negative"
            notice = zf.read("README_FIRST.txt").decode("utf-8")
            assert "NEGATIVO/INVERTIDO" in notice
            assert "ABLACION" in notice


def test_validated_shop_material_preset_keeps_full_marking_and_scanner_evidence():
    with TestClient(app) as client:
        response = client.post("/api/materials/shop-preset", json={
            "name":"QA relief marker validation",
            "machine_profile_id":"sculpfun_s9_pro_10w",
            "material":"QA plastic coupon",
            "surface_or_model":"flat discard sample",
            "operation":"engrave",
            "speed_mm_min":3000,
            "power_percent":25,
            "passes":1,
            "laser_mode":"M4",
            "validated_on_exact_machine_surface":True,
            "notes":"software persistence test only",
            "marking_mode":{"polarity":"negative","polarity_scope":"codes","negative_field":"islands","field_margin_mm":0.8,"kerf_compensation_mm":0.0,"validated_on":"QA coupon"},
            "scanner_profile_id":"steren_com_597",
            "scan_validation":"pass",
            "scan_attempts":5,
            "scan_successes":5,
        })
        assert response.status_code == 200, response.text
        stored_id = response.json()["stored"]["material_preset_ids"][0]
        captures = client.get("/api/machine/captures?limit=200").json()["material_presets"]
        preset = next(p for p in captures if p["id"] == stored_id)
        settings = preset["settings"]
        assert settings["marking_mode"]["polarity"] == "negative"
        assert settings["marking_mode"]["field_margin_mm"] == pytest.approx(0.8)
        assert settings["scanner_profile_id"] == "steren_com_597"
        assert settings["scan_validation"] == "pass"
        assert settings["scan_attempts"] == settings["scan_successes"] == 5


def test_marking_mode_model_defaults_are_backwards_compatible():
    mode = MarkingMode()
    assert mode.model_dump() == {
        "polarity":"positive",
        "polarity_scope":"codes",
        "negative_field":"islands",
        "field_margin_mm":0.0,
        "kerf_compensation_mm":0.0,
        "validated_on":"",
    }


def test_shop_material_scan_evidence_rejects_impossible_counts():
    from app.models import ShopMaterialPresetRequest
    base = dict(
        name="QA", machine_profile_id="sculpfun_s9_pro_10w", material="coupon",
        speed_mm_min=1000, power_percent=10, scan_validation="pass",
        scan_attempts=5, scan_successes=4,
    )
    with pytest.raises(Exception, match="all recorded attempts"):
        ShopMaterialPresetRequest(**base)
    base["scan_successes"] = 6
    with pytest.raises(Exception, match="cannot exceed"):
        ShopMaterialPresetRequest(**base)


def test_characterization_coupon_has_four_unique_panels_and_rasterizes():
    from app.exporters import svg_to_png
    from app.marking_coupon import render_marking_coupon
    template, quality = _inova()
    coupon = render_marking_coupon(
        template, quality, {"manufacturer_id":"Q00525499"},
        negative_base=MarkingMode(polarity="negative", field_margin_mm=0.5, kerf_compensation_mm=0),
    )
    root = ET.fromstring(coupon["svg"])
    ids = [node.attrib["id"] for node in root.iter() if "id" in node.attrib]
    assert len(ids) == len(set(ids))
    assert [p["panel"] for p in coupon["panels"]] == ["A", "B", "C", "D"]
    assert all(p["polarity"] == "negative" for p in coupon["panels"])
    assert [(p["polarity_scope"], p["negative_field"]) for p in coupon["panels"]] == [
        ("codes", "islands"), ("codes", "template"), ("all", "islands"), ("all", "template")
    ]
    png = svg_to_png(coupon["svg"], coupon["width_mm"], coupon["height_mm"], dpi=300)
    assert png.startswith(b"\x89PNG") and len(png) > 1000


def test_coupon_api_returns_same_identity_in_four_physical_strategies():
    with TestClient(app) as client:
        template = next(t for t in client.get("/api/catalog").json()["templates"] if t["id"] == "inova_quantum_code128_v1")
        response = client.post("/api/marking/coupon", json={
            "template":template,
            "data":{"manufacturer_id":"Q00525499"},
            "negative_mode":{"polarity":"negative","field_margin_mm":0.5,"kerf_compensation_mm":0},
        })
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["panels"]) == 4
        assert body["svg"].count("Q00525499") >= 1  # title metadata from the same identity remains visible in panel geometry
        assert "pieza de descarte" in body["note"]


def test_negative_field_warns_when_margin_exits_template_and_rejects_absurd_kerf():
    template, quality = _inova()
    wide_margin = render_template(
        template, quality, {"manufacturer_id":"Q00525499"},
        marking_mode_override=MarkingMode(polarity="negative", polarity_scope="codes", negative_field="islands", field_margin_mm=10),
    )
    assert any("sale de los límites" in w for w in wide_margin.warnings)
    with pytest.raises(ValueError, match="kerf_compensation_mm demasiado grande"):
        render_template(
            template, quality, {"manufacturer_id":"Q00525499"},
            marking_mode_override=MarkingMode(polarity="negative", polarity_scope="codes", negative_field="islands", field_margin_mm=0, kerf_compensation_mm=10),
        )


def test_preflight_rejects_negative_geometry_if_it_ever_leaks_into_quality_path(monkeypatch):
    import app.code_quality as cq
    template, quality = _inova()
    original = cq._fragment_for_element

    def negative_fragment(el, profile, value):
        from dataclasses import replace
        positive = original(el, profile, value)
        return replace(positive, svg='<path d="M 0 0 h 1 v 1 h -1 z" fill="#000" fill-rule="evenodd"/>')

    monkeypatch.setattr(cq, "_fragment_for_element", negative_fragment)
    with pytest.raises(ValueError, match="invariante de preflight violado"):
        cq.assess_template_codes(template, quality, {"manufacturer_id":"Q00525499"}, digital_stress=False)


@pytest.mark.parametrize("scope,field", [("codes","islands"),("codes","template"),("all","islands"),("all","template")])
def test_negative_batch_ids_remain_unique_for_supported_modes(scope, field):
    from app.batch_engine import render_batch
    from app.config_loader import load_jigs, load_machines
    from app.models import BatchAssignment
    template, quality = _inova()
    jig = load_jigs()["inova_tray_3x4_estimate"]
    machine = load_machines()[jig.machine_profile_id]
    rows = [{"manufacturer_id": f"Q00{525499+i:06d}"} for i in range(3)]
    assignments = [BatchAssignment(slot_index=i, row_index=i, physical_id=rows[i]["manufacturer_id"]) for i in range(3)]
    batch = render_batch(
        machine, jig, template, quality, rows, assignments,
        marking_mode_override=MarkingMode(polarity="negative", polarity_scope=scope, negative_field=field),
    )
    ids = _ids(batch.svg)
    assert len(ids) == len(set(ids))
    assert all(f"mark_{i:04d}" in ids for i in range(1, 4))


def test_saved_negative_template_mode_applies_without_job_override():
    template, quality = _inova()
    template.marking_mode = MarkingMode(polarity="negative", polarity_scope="codes", negative_field="islands", field_margin_mm=0.4)
    mark = render_template(template, quality, {"manufacturer_id":"Q00525499"})
    assert mark.marking_mode["polarity"] == "negative"
    assert 'fill-rule="evenodd"' in mark.svg


def test_negative_all_converts_text_line_and_rect_to_filled_geometry():
    quality = load_quality_profiles()["rugged_field_v1"]
    template = TemplateSpec(
        id="qa_all_geometry", name="QA all geometry", category="qa", width_mm=60, height_mm=30,
        quality_profile=quality.id, expected_fields=["serial"],
        elements=[
            ElementSpec(kind="code128", name="barcode_serial", x_mm=3, y_mm=2, source="serial", height_mm=8, module_mm=0.33),
            ElementSpec(kind="text", name="text_serial", x_mm=3, y_mm=17, source="serial", width_mm=35, font_size_mm=3),
            ElementSpec(kind="rect", name="frame", x_mm=42, y_mm=3, width_mm=12, height_mm=8, stroke_mm=0.4),
            ElementSpec(kind="line", name="separator", x_mm=42, y_mm=15, width_mm=12, height_mm=3, stroke_mm=0.5),
        ],
    )
    mode = MarkingMode(polarity="negative", polarity_scope="all", negative_field="islands", field_margin_mm=0.5)
    mark = render_template(template, quality, {"serial":"ABC123"}, marking_mode_override=mode)
    assert '<text' not in mark.svg
    assert '<line' not in mark.svg
    assert '<rect' not in mark.svg
    for expected_id in ("barcode_serial", "text_serial", "frame", "separator"):
        assert f'id="{expected_id}"' in mark.svg
    assert mark.svg.count('fill-rule="evenodd"') >= 4


def test_kerf_union_prevents_evenodd_overlap_cancellation_for_2d_modules():
    from app.code_geometry import expand_and_union_rects
    # Two touching modules become overlapping after compensation. The helper
    # must return their geometric union, not two overlapping even-odd holes.
    rects = [(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5)]
    union = expand_and_union_rects(rects, 0.10, compensate_y=True)
    assert len(union) == 1
    x, y, w, h = union[0]
    assert x == pytest.approx(-0.05)
    assert y == pytest.approx(-0.05)
    assert w == pytest.approx(1.10)
    assert h == pytest.approx(0.60)


def test_qr_negative_with_small_measured_kerf_compensation_still_renders_valid_svg():
    templates = load_templates()
    template = templates["phone_qr_economic_v1"].model_copy(deep=True)
    quality = load_quality_profiles()[template.quality_profile]
    rendered = render_template(
        template, quality, {"economic_number": "TEL-0037"},
        marking_mode_override=MarkingMode(
            polarity="negative", polarity_scope="codes", negative_field="islands",
            field_margin_mm=0.5, kerf_compensation_mm=0.10,
        ),
    )
    ET.fromstring(rendered.svg)
    assert 'fill-rule="evenodd"' in rendered.svg
    assert rendered.marking_mode["kerf_compensation_mm"] == pytest.approx(0.10)


def test_comparison_can_return_pngs_from_the_same_positive_and_negative_svgs():
    import base64
    from PIL import Image
    with TestClient(app) as client:
        template = next(t for t in client.get("/api/catalog").json()["templates"] if t["id"] == "inova_quantum_code128_v1")
        response = client.post("/api/marking/compare", json={
            "template": template,
            "data": {"manufacturer_id": "Q00525499"},
            "include_png": True,
            "dpi": 300,
            "negative_mode": {"polarity":"negative","polarity_scope":"codes","negative_field":"islands","field_margin_mm":0.5,"kerf_compensation_mm":0},
        })
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["png_dpi"] == 300
        for key in ("positive_png_base64", "negative_png_base64"):
            raw = base64.b64decode(body[key])
            assert raw.startswith(b"\x89PNG")
            image = Image.open(io.BytesIO(raw))
            assert image.width > 20 and image.height > 20


def test_frontend_allows_codes_template_but_labels_two_stage_safety():
    # WHY: v0.8 final keeps the fourth experimental combination available, but
    # explicitly identifies it as a two-stage artifact instead of silently
    # pretending one pass can produce both relief and sunken positive content.
    root = Path(__file__).resolve().parents[1]
    js = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert "templateOpt.disabled=false" in js
    assert "Plantilla completa (sólo códigos = 2 etapas)" in html
    assert "_NEGATIVE_2PASS" in js
