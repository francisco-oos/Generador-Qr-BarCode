from app.config_loader import load_quality_profiles, load_scanners, load_templates


def test_steren_com597_profile_and_current_templates_have_margin():
    scanners = load_scanners()
    scanner = scanners["steren_com_597"]
    assert scanner.supports_qr is True
    assert scanner.supports_datamatrix is True
    assert "Code 128" in scanner.symbologies
    assert scanner.minimum_print_contrast_percent == 30

    templates = load_templates()
    qualities = load_quality_profiles()

    inova = templates["inova_quantum_code128_v1"]
    q_inova = qualities[inova.quality_profile]
    # Current rugged Code128 X-dimension: 0.33 mm ~= 13 mil.
    # COM-597 supports Code128; keep this deliberately well above very fine linear marks.
    assert q_inova.code128_module_mm >= 0.30

    phone = templates["phone_qr_economic_v1"]
    qr = next(el for el in phone.elements if el.kind == "qr")
    module_mm = qr.module_mm or qualities[phone.quality_profile].qr_module_mm
    documented_qr_min_mm = 8.7 * 0.0254
    assert module_mm >= documented_qr_min_mm * 1.5
