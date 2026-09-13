from __future__ import annotations

import base64
import io
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config_loader import load_quality_profiles
from app.image_element import prepare_image_element
from app.main import app
from app.models import ElementSpec, MarkingMode, TemplateSpec
from app.template_engine import render_template


def _data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _png_uri() -> str:
    im = Image.new("RGB", (24, 16), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((2, 2, 10, 13), fill="black")
    d.ellipse((13, 3, 21, 12), fill="black")
    out = io.BytesIO(); im.save(out, "PNG")
    return _data_uri(out.getvalue(), "image/png")


def _jpg_uri() -> str:
    im = Image.new("L", (32, 20))
    for x in range(im.width):
        for y in range(im.height):
            im.putpixel((x, y), int(255 * x / max(1, im.width - 1)))
    out = io.BytesIO(); im.convert("RGB").save(out, "JPEG", quality=90)
    return _data_uri(out.getvalue(), "image/jpeg")


def _svg_uri(extra: str = "") -> str:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10">
      <rect id="unsafe-id" x="1" y="1" width="8" height="8" fill="#f00"/>
      <path d="M 11 1 L 19 5 L 11 9 z" fill="#00f"/>{extra}
    </svg>'''
    return _data_uri(svg.encode(), "image/svg+xml")


def _template_with_image(image_uri: str, *, processing: str = "auto") -> tuple[TemplateSpec, object]:
    q = load_quality_profiles()["rugged_field_v1"]
    t = TemplateSpec(
        id="qa_image", name="QA image", category="qa", width_mm=45, height_mm=25,
        quality_profile=q.id, expected_fields=[],
        elements=[ElementSpec(
            kind="image", name="logo_mark", label="Logo", x_mm=3, y_mm=4,
            width_mm=18, height_mm=12, image_data_uri=image_uri,
            image_processing=processing, image_dpi=254,
        )],
    )
    return t, q


def test_image_element_requires_embedded_supported_data_uri_and_size():
    with pytest.raises(Exception, match="image_data_uri"):
        ElementSpec(kind="image", x_mm=1, y_mm=1, width_mm=10, height_mm=10)
    with pytest.raises(Exception, match="data URI"):
        ElementSpec(kind="image", x_mm=1, y_mm=1, width_mm=10, height_mm=10, image_data_uri="https://example.test/logo.png")
    ok = ElementSpec(kind="image", x_mm=1, y_mm=1, width_mm=10, height_mm=10, image_data_uri=_png_uri())
    assert ok.image_processing == "auto"




def test_image_model_rejects_unsupported_mime_and_incompatible_processing_modes():
    gif = _data_uri(b"GIF89a", "image/gif")
    with pytest.raises(Exception, match="PNG, JPEG or SVG"):
        ElementSpec(kind="image", x_mm=1, y_mm=1, width_mm=10, height_mm=10, image_data_uri=gif)
    with pytest.raises(Exception, match="cannot use vector processing"):
        ElementSpec(kind="image", x_mm=1, y_mm=1, width_mm=10, height_mm=10, image_data_uri=_png_uri(), image_processing="vector")
    with pytest.raises(Exception, match="auto/vector processing only"):
        ElementSpec(kind="image", x_mm=1, y_mm=1, width_mm=10, height_mm=10, image_data_uri=_svg_uri(), image_processing="threshold")

def test_png_threshold_becomes_vector_geometry_with_semantic_id_and_no_external_href():
    t, q = _template_with_image(_png_uri(), processing="threshold")
    mark = render_template(t, q, {})
    root = ET.fromstring(mark.svg)
    ids = [n.attrib["id"] for n in root.iter() if "id" in n.attrib]
    assert "logo_mark" in ids
    assert "layer_geometry" in ids
    assert "<path" in mark.svg
    assert "href=" not in mark.svg
    assert any("geometría binaria" in w for w in mark.warnings)
    assert any("PENDIENTE DE ACEPTACIÓN" in w for w in mark.warnings)


def test_jpeg_floyd_steinberg_renders_as_bounded_vector_geometry():
    t, q = _template_with_image(_jpg_uri(), processing="floyd_steinberg")
    t.elements[0].image_dpi = 200
    mark = render_template(t, q, {})
    ET.fromstring(mark.svg)
    assert "Floyd-Steinberg" in " ".join(mark.warnings)
    assert len(mark.svg) < 2_000_000


def test_svg_upload_is_sanitized_and_normalized_to_black_vector():
    prepared = prepare_image_element(
        data_uri=_svg_uri(), x_mm=2, y_mm=3, width_mm=20, height_mm=10,
        processing="vector", preserve_aspect=True,
    )
    assert "unsafe-id" not in prepared.svg
    assert "#f00" not in prepared.svg and "#00f" not in prepared.svg
    assert "#000" in prepared.svg
    assert "href" not in prepared.svg
    ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{prepared.svg}</svg>')


def test_svg_upload_rejects_script_foreign_or_external_content():
    bad = _data_uri(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/svg+xml")
    with pytest.raises(ValueError, match="no permitido"):
        prepare_image_element(data_uri=bad, x_mm=0, y_mm=0, width_mm=10, height_mm=10, processing="vector")
    bad_href = _data_uri(b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://x/a.png"/></svg>', "image/svg+xml")
    with pytest.raises(ValueError, match="no permitido"):
        prepare_image_element(data_uri=bad_href, x_mm=0, y_mm=0, width_mm=10, height_mm=10, processing="vector")


def test_image_overlap_with_code_quiet_zone_is_reported_not_silently_accepted():
    q = load_quality_profiles()["rugged_field_v1"]
    t = TemplateSpec(
        id="qa_image_code", name="QA image/code", category="qa", width_mm=65, height_mm=30,
        quality_profile=q.id, expected_fields=["serial"],
        elements=[
            ElementSpec(kind="code128", name="barcode_serial", x_mm=2, y_mm=2, source="serial", module_mm=.33, height_mm=9),
            ElementSpec(kind="image", name="logo", x_mm=4, y_mm=3, width_mm=12, height_mm=8, image_data_uri=_png_uri(), image_processing="threshold"),
        ],
    )
    mark = render_template(t, q, {"serial": "Q00525499"})
    assert any("invade el área/quiet zone" in w for w in mark.warnings)


def test_negative_codes_keeps_image_positive_but_negative_all_rejects_untruthful_merge():
    t, q = _template_with_image(_png_uri(), processing="threshold")
    t.elements.append(ElementSpec(kind="qr", name="qr_asset", x_mm=24, y_mm=4, source="asset", module_mm=.35))
    t.expected_fields = ["asset"]
    codes = render_template(
        t, q, {"asset": "TEL-0037"},
        marking_mode_override=MarkingMode(polarity="negative", polarity_scope="codes", negative_field="islands"),
    )
    assert 'id="logo_mark"' in codes.svg and 'id="qr_asset"' in codes.svg
    with pytest.raises(ValueError, match="elementos image"):
        render_template(
            t, q, {"asset": "TEL-0037"},
            marking_mode_override=MarkingMode(polarity="negative", polarity_scope="all", negative_field="islands"),
        )




def test_unsaved_template_preview_api_accepts_image_and_returns_real_svg():
    t, _ = _template_with_image(_png_uri(), processing="threshold")
    with TestClient(app) as client:
        response = client.post("/api/templates/preview", json={"template": t.model_dump(), "data": {}, "output": "svg"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert 'id="logo_mark"' in body["svg"]
    assert "href=" not in body["svg"]
    assert any("PENDIENTE DE ACEPTACIÓN" in w for w in body["warnings"])

def test_frontend_exposes_image_tool_and_safe_processing_controls():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/static/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    for token in ("addImageElementBtn", "designerImageInput", "propImageProcessing", "propImageThreshold", "propImageDpi", "replaceImageBtn"):
        assert token in html
    assert "addOrReplaceDesignerImage" in js
    assert "3*1024*1024" in js
