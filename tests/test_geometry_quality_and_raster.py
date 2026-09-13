"""Geometry, symbol-quality and rasterization contracts introduced in v0.7.0.

WHY: Las tres cosas que se prueban aqui comparten una propiedad incomoda: fallan
produciendo un archivo perfectamente valido.  Un ``id`` repetido sigue siendo XML
bien formado, una quiet zone insuficiente sigue decodificando en pantalla y una
rotacion mal centrada sigue generando un SVG que abre sin errores.  Solo una
prueba explicita las detecta antes de que lleguen al material fisico.
"""

from __future__ import annotations

import collections
import re
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from app.batch_engine import render_batch
from app.config_loader import load_jigs, load_machines, load_quality_profiles, load_templates
from app.models import BatchAssignment, ElementSpec, TemplateSpec
from app.raster_probe import (
    decode_symbols,
    flatten_on_white,
    ink_density,
    rasterize_independent,
    rasterize_production,
)
from app.svg_document import rotation_transform
from app.template_engine import render_template

QUALITY_ID = "rugged_field_v1"


def _quality():
    return load_quality_profiles()[QUALITY_ID]


def _template(elements, width=40.0, height=40.0, fields=("a",)):
    return TemplateSpec(
        id="geom_probe", name="probe", category="generic",
        width_mm=width, height_mm=height, quality_profile=QUALITY_ID,
        expected_fields=list(fields), elements=elements,
    )


def _all_ids(svg: str) -> list[str]:
    return re.findall(r'id="([^"]+)"', svg)


# ------------------------------------------------------------------- ROTACION

@pytest.mark.parametrize("rotation", [0, 90, 180, 270, 45])
def test_rotated_codes_remain_decodable_at_every_supported_angle(rotation):
    t = _template([ElementSpec(
        kind="qr", source="a", name="qr_activo",
        x_mm=5, y_mm=5, module_mm=0.6, rotation_deg=rotation,
    )])
    mark = render_template(t, _quality(), {"a": "TEL-0037"})
    image = rasterize_production(mark.svg, t.width_mm, t.height_mm, dpi=600)
    decoded = decode_symbols(image)
    if decoded is None:
        pytest.skip("libzbar no disponible en este host")
    assert ("QRCODE", "TEL-0037") in decoded


def test_zero_rotation_emits_no_transform_attribute():
    # Un transform neutro haria que un editor externo mostrase el objeto como
    # "transformado" sin estarlo, y ensucia la comparacion entre versiones.
    t = _template([ElementSpec(kind="qr", source="a", name="qr_a", x_mm=2, y_mm=2, module_mm=0.6)])
    assert "transform=" not in render_template(t, _quality(), {"a": "X1"}).svg


def test_rotation_transform_uses_the_element_centre():
    assert rotation_transform(0, 10, 10) == ""
    assert rotation_transform(90, 10, 20) == "rotate(90.0000 10.0000 20.0000)"
    # -90 y 270 describen el mismo giro y deben producir el mismo archivo.
    assert rotation_transform(-90, 5, 5) == rotation_transform(270, 5, 5)


def test_rotation_is_normalised_by_the_model():
    assert ElementSpec(kind="rect", x_mm=0, y_mm=0, rotation_deg=-90).rotation_deg == 270.0
    assert ElementSpec(kind="rect", x_mm=0, y_mm=0, rotation_deg=360).rotation_deg == 0.0


def test_rotated_element_stays_inside_the_canvas_ink_wise():
    # Rotar 90 grados alrededor del centro no debe expulsar la geometria del lienzo.
    t = _template([ElementSpec(
        kind="code128", source="a", name="barcode_a",
        x_mm=5, y_mm=12, width_mm=28, height_mm=8, module_mm=0.35, rotation_deg=90,
    )], width=40, height=40)
    mark = render_template(t, _quality(), {"a": "AB123"})
    density = ink_density(rasterize_production(mark.svg, 40, 40, dpi=300))
    assert 0.0 < density < 0.5, f"densidad inesperada: {density}"


def test_rotation_survives_inside_a_batch_document():
    templates = load_templates()
    base = templates["inova_quantum_code128_v1"]
    rotated = base.model_copy(deep=True)
    for el in rotated.elements:
        el.rotation_deg = 180.0
    jig = load_jigs()["inova_tray_3x4_estimate"]
    machine = load_machines()[jig.machine_profile_id]
    rows = [{"manufacturer_id": "Q00525499"}, {"manufacturer_id": "Q00525500"}]
    assignments = [BatchAssignment(slot_index=i, row_index=i, physical_id=r["manufacturer_id"])
                   for i, r in enumerate(rows)]
    result = render_batch(machine, jig, rotated, _quality_for(rotated), rows, assignments, True)
    assert result.svg.count("rotate(180.0000") >= 2
    ET.fromstring(result.svg)


def _quality_for(template):
    return load_quality_profiles()[template.quality_profile]


# ----------------------------------------------------------------- QUIET ZONE

def test_element_quiet_zone_overrides_the_profile_and_changes_geometry():
    wide = _template([ElementSpec(kind="qr", source="a", name="q", x_mm=1, y_mm=1, module_mm=0.6, quiet_modules=8)])
    narrow = _template([ElementSpec(kind="qr", source="a", name="q", x_mm=1, y_mm=1, module_mm=0.6, quiet_modules=1)])
    wide_svg = render_template(wide, _quality(), {"a": "X"}).svg
    narrow_svg = render_template(narrow, _quality(), {"a": "X"}).svg
    # Mas quiet zone significa mas modulos totales, luego mas recorrido de path.
    assert len(wide_svg) != len(narrow_svg)


def test_reducing_quiet_zone_warns_but_never_blocks():
    t = _template([ElementSpec(kind="qr", source="a", name="q", x_mm=1, y_mm=1, module_mm=0.6, quiet_modules=1)])
    mark = render_template(t, _quality(), {"a": "TEL-0037"})
    assert any("quiet zone" in w.lower() for w in mark.warnings)
    # El riesgo se informa; el experto sigue pudiendo exportar.
    assert mark.svg.strip().startswith("<svg")


def test_quiet_zone_equal_to_profile_produces_no_warning():
    q = _quality()
    t = _template([ElementSpec(kind="qr", source="a", name="q", x_mm=1, y_mm=1,
                               module_mm=q.qr_module_mm, quiet_modules=q.qr_quiet_modules)])
    mark = render_template(t, q, {"a": "TEL-0037"})
    assert not any("quiet zone" in w.lower() for w in mark.warnings)


def test_explicit_zero_quiet_zone_is_kept_and_flagged():
    # ``0`` es una decision del usuario y no debe confundirse con "heredar el perfil".
    el = ElementSpec(kind="code128", source="a", name="b", x_mm=1, y_mm=1, quiet_modules=0)
    assert el.quiet_modules == 0
    t = _template([el], width=80, height=30)
    mark = render_template(t, _quality(), {"a": "AB123"})
    assert any("quiet zone" in w.lower() for w in mark.warnings)


def test_preflight_evaluates_the_element_quiet_zone_not_the_profile():
    from app.code_quality import assess_template_codes

    t = _template([ElementSpec(kind="qr", source="a", name="q", x_mm=1, y_mm=1, module_mm=0.6, quiet_modules=1)])
    report = assess_template_codes(t, _quality(), {"a": "TEL-0037"}, scanner=None, digital_stress=False)
    item = report["results"][0]
    assert item["quiet_modules"] == 1, "el preflight evaluó el perfil en lugar del elemento"
    assert any("quiet zone" in c["message"].lower() for c in item["checks"])
    # Una quiet zone por debajo de la referencia degrada la clasificación: el riesgo
    # queda visible en el resultado, no sólo enterrado en un mensaje.
    assert item["classification"] in {"FRAGIL", "NO_LEGIBLE"}


# ------------------------------------------------------------- IDS UNICOS

def test_single_mark_ids_are_semantic_and_unique():
    t = _template([
        ElementSpec(kind="code128", source="a", name="barcode_serial", x_mm=2, y_mm=2, height_mm=8, module_mm=0.35),
        ElementSpec(kind="text", source="a", name="text_serial", x_mm=2, y_mm=18, font_size_mm=3),
    ], width=60, height=25)
    svg = render_template(t, _quality(), {"a": "Q00525499"}).svg
    ids = _all_ids(svg)
    assert "barcode_serial" in ids and "text_serial" in ids
    assert not [k for k, v in collections.Counter(ids).items() if v > 1]


def test_batch_namespaces_every_mark_so_no_id_repeats_anywhere():
    """WHY: Este es el defecto concreto encontrado en la linea base: ``id="mark"``,
    ``id="clip"`` y ``id="group"`` se repetian doce veces en un lote de doce."""
    templates = load_templates()
    t = templates["inova_quantum_code128_v1"]
    jig = load_jigs()["inova_tray_3x4_estimate"]
    machine = load_machines()[jig.machine_profile_id]
    rows = [{"manufacturer_id": f"Q00{525499 + i:06d}"} for i in range(12)]
    assignments = [BatchAssignment(slot_index=i, row_index=i, physical_id=rows[i]["manufacturer_id"])
                   for i in range(12)]
    result = render_batch(machine, jig, t, _quality_for(t), rows, assignments, True)

    ids = _all_ids(result.svg)
    duplicates = {k: v for k, v in collections.Counter(ids).items() if v > 1}
    assert not duplicates, f"identificadores repetidos en el lote: {duplicates}"

    # El espacio de nombres por marca debe ser visible y ordenado.
    assert "mark_0001" in ids and "mark_0012" in ids
    assert any(i.startswith("mark_0001__") for i in ids)
    # Y ninguno de los identificadores genericos del defecto original sobrevive.
    for legacy in ("clip", "group"):
        assert legacy not in ids


def test_every_generated_document_is_well_formed_xml_with_unique_ids():
    templates = load_templates()
    qualities = load_quality_profiles()
    for t in templates.values():
        data = dict(t.metadata.get("example_data") or {})
        for f in t.expected_fields:
            data.setdefault(f, f"TEST-{f.upper()}")
        for mode in ("production", "editable"):
            svg = render_template(t, qualities[t.quality_profile], data, mode=mode).svg
            ET.fromstring(svg)
            ids = _all_ids(svg)
            assert not [k for k, v in collections.Counter(ids).items() if v > 1], f"{t.id}/{mode}"


# --------------------------------------------------- COMPOSICION ALFA (PRE fix)

def test_flatten_on_white_is_what_prevents_the_documented_false_positive():
    """WHY: Reproduce exactamente el error de medicion de la linea base.

    Una imagen RGBA totalmente transparente convertida con ``convert("L")`` da
    densidad de tinta 1.0 (negro).  Compuesta sobre blanco da 0.0.  Esa diferencia
    fue la que llevo a concluir, incorrectamente, que un renderizador fallaba.
    """
    transparent = Image.new("RGBA", (40, 40), (0, 0, 0, 0))

    naive = transparent.convert("L")
    naive_dark = sum(naive.histogram()[:128]) / (40 * 40)
    assert naive_dark == 1.0, "el modo incorrecto debe seguir dando el falso positivo"

    assert ink_density(transparent) == 0.0
    assert flatten_on_white(transparent).getpixel((0, 0)) == 255


def test_independent_renderer_agrees_with_the_production_renderer():
    """WHY: Comprobacion cruzada real, ya con la medicion corregida."""
    t = _template([ElementSpec(kind="code128", source="a", name="barcode_a",
                               x_mm=2, y_mm=2, height_mm=10, module_mm=0.35)], width=60, height=20)
    svg = render_template(t, _quality(), {"a": "Q00525499"}).svg

    production = rasterize_production(svg, 60, 20, dpi=600)
    assert 0.0 < ink_density(production) < 0.5

    independent = rasterize_independent(svg, dpi=600)
    if independent is None:
        pytest.skip("CairoSVG no disponible en este host: NO PROBADO, no PASS")
    density = ink_density(independent)
    assert 0.0 < density < 0.5, f"el renderizador independiente devolvio densidad {density}"

    decoded = decode_symbols(independent)
    if decoded is None:
        pytest.skip("libzbar no disponible en este host")
    assert ("CODE128", "Q00525499") in decoded


def test_no_test_measures_ink_density_on_raw_alpha():
    """WHY: Guardia de proceso. Prohibe reintroducir ``convert("L")`` sobre una imagen
    con alfa en la suite, que es la forma exacta en que aparecio el falso positivo."""
    from pathlib import Path

    tests_dir = Path(__file__).resolve().parent
    offenders = []
    for path in tests_dir.glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        if 'convert("L")' in text or "convert('L')" in text:
            if path.name != Path(__file__).name:
                offenders.append(path.name)
    assert not offenders, (
        f"Use app.raster_probe.flatten_on_white en lugar de convert('L'): {offenders}"
    )
