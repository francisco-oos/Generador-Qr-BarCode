from xml.etree import ElementTree as ET

from app.config_loader import load_jigs, load_machines, load_quality_profiles, load_scanners, load_templates
from app.exporters import svg_to_png
from app.template_engine import render_template


def sample_data():
    return {
        "manufacturer_id": "Q00525499",
        "operational_id": "Q00525499",
        "serial": "4281847",
        "asset_id": "PHONE-000037",
        "economic_number": "TEL-0037",
    }


def test_catalog_integrity():
    templates = load_templates()
    qualities = load_quality_profiles()
    machines = load_machines()
    jigs = load_jigs()
    scanners = load_scanners()
    assert len(templates) >= 5
    assert "sculpfun_s9_pro_10w" in machines
    assert "zebra_symbol_ls2208" in scanners
    for template in templates.values():
        assert template.quality_profile in qualities
    for jig in jigs.values():
        assert jig.machine_profile_id in machines
        assert jig.template_id in templates


def test_all_templates_render_valid_svg_and_png():
    for template in load_templates().values():
        q = load_quality_profiles()[template.quality_profile]
        result = render_template(template, q, sample_data())
        ET.fromstring(result.svg)
        png = svg_to_png(result.svg, result.width_mm, result.height_mm, 300)
        assert png.startswith(b"\x89PNG")
        assert len(png) > 100


def test_inova_template_has_no_layout_warning_for_operational_id():
    t = load_templates()["inova_quantum_code128_v1"]
    q = load_quality_profiles()[t.quality_profile]
    result = render_template(t, q, {"manufacturer_id": "Q00525499"})
    assert result.warnings == []
    assert "Q00525499" in result.svg
