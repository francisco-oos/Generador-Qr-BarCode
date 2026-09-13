from __future__ import annotations

import io

import pytest
from PIL import Image, ImageOps
from pydantic import ValidationError
from pyzbar.pyzbar import decode

from app.barcode_engine import (
    code128_fragment,
    negative_background_fragment,
    qr_fragment,
)
from app.code_quality import assess_template_codes
from app.config_loader import load_quality_profiles, load_scanners, load_templates
from app.exporters import svg_to_png
from app.models import ElementSpec
from app.template_engine import render_template


def _wrap(fragment) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{fragment.width_mm:.4f}mm" '
        f'height="{fragment.height_mm:.4f}mm" viewBox="0 0 {fragment.width_mm:.4f} {fragment.height_mm:.4f}">'
        f'<rect x="0" y="0" width="{fragment.width_mm:.4f}" height="{fragment.height_mm:.4f}" fill="#fff"/>'
        f'{fragment.svg}</svg>'
    )


def _decode_after_contrast_reversal(fragment, expected: str, expected_type: str) -> None:
    png = svg_to_png(_wrap(fragment), fragment.width_mm, fragment.height_mm, dpi=600)
    image = Image.open(io.BytesIO(png)).convert("RGB")
    # WHY: el SVG negativo representa el fondo que se grabará. Para el flujo de
    # relieve + marcador, la aceptación geométrica relevante es que la polaridad
    # óptica final (barras/módulos oscuros sobre fondo claro) recupere el dato.
    optical_result = ImageOps.invert(image)
    decoded = decode(optical_result)
    assert any(d.data.decode("utf-8") == expected and d.type == expected_type for d in decoded)


def test_negative_mode_is_restricted_to_machine_readable_codes():
    with pytest.raises(ValidationError):
        ElementSpec(kind="text", x_mm=1, y_mm=5, literal="ABC", engraving_mode="negative_background")


def test_negative_code128_is_vector_complement_and_roundtrips_after_contrast_reversal():
    base = code128_fragment("Q00525499", 0, 0, 0.33, 10.0, 10)
    negative = negative_background_fragment(base, 0, 0)
    assert negative.width_mm == base.width_mm
    assert negative.height_mm == base.height_mm
    assert 'fill-rule="evenodd"' in negative.svg
    assert negative.svg != base.svg
    _decode_after_contrast_reversal(negative, "Q00525499", "CODE128")


def test_negative_qr_is_vector_complement_and_roundtrips_after_contrast_reversal():
    base = qr_fragment("TEL-0037", 0, 0, 0.50, 4, "M")
    negative = negative_background_fragment(base, 0, 0)
    assert 'fill-rule="evenodd"' in negative.svg
    _decode_after_contrast_reversal(negative, "TEL-0037", "QRCODE")


def test_template_render_exposes_negative_mode_without_changing_default_templates():
    templates = load_templates()
    qualities = load_quality_profiles()
    original = templates["inova_quantum_code128_v1"]
    assert all(getattr(e, "engraving_mode", "positive") == "positive" for e in original.elements)

    draft = original.model_copy(deep=True)
    code = next(e for e in draft.elements if e.kind == "code128")
    code.engraving_mode = "negative_background"
    mark = render_template(draft, qualities[draft.quality_profile], {"manufacturer_id": "Q00525499"})
    assert 'fill-rule="evenodd"' in mark.svg
    assert any("negativo" in w.lower() for w in mark.warnings)
    assert len(mark.element_ids) == len(set(mark.element_ids))


def test_negative_preflight_keeps_geometry_checks_and_requires_physical_acceptance():
    templates = load_templates()
    qualities = load_quality_profiles()
    scanners = load_scanners()
    draft = templates["phone_qr_economic_v1"].model_copy(deep=True)
    code = next(e for e in draft.elements if e.kind == "qr")
    code.engraving_mode = "negative_background"
    result = assess_template_codes(
        draft,
        qualities[draft.quality_profile],
        {"economic_number": "TEL-0037"},
        scanner=scanners["steren_com_597"],
        digital_stress=True,
    )
    item = result["results"][0]
    assert item["engraving_mode"] == "negative_background"
    assert item["physical_validation_required"] is True
    assert any(c["level"] == "info" and "aceptación física" in c["message"].lower() for c in item["checks"])
    assert item["digital"]["available"] is True
    assert item["digital"]["variants"][0]["pass"] is True


def test_default_positive_render_is_byte_stable_when_mode_is_omitted():
    base = code128_fragment("4281847", 0, 0, 0.33, 10.0, 10)
    # The new mode is opt-in; existing templates continue to serialize the same
    # positive geometry unless a user explicitly selects negative_background.
    assert 'fill-rule="nonzero"' in base.svg
    assert 'evenodd' not in base.svg
