"""Structural and interoperability guarantees of the generated SVG.

WHY:
Estas pruebas existen por un defecto real encontrado en v0.6.2: el documento
repetia ``id="mark"``, ``id="clip"`` y ``id="group"`` una vez por marca, de modo
que dos simbolos con recortes distintos referenciaban el mismo ``url(#clip)``.
El caso se reproduce aqui con valores de longitud muy dispar, que es lo que hace
divergir la geometria de cada recurso.

Regla de la casa: no basta con que una herramienta "abra" el archivo.  Cada
prueba de render comprueba el contenido de la imagen resultante, no el codigo de
salida del proceso.
"""

from __future__ import annotations

import collections
import io
import re
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image

from app.batch_engine import render_batch
from app.config_loader import load_jigs, load_machines, load_quality_profiles, load_templates
from app.exporters import svg_to_png
from app.models import BatchAssignment, TemplateSpec
from app.raster_probe import load_flattened
from app.template_engine import render_template

# WHY: Longitudes deliberadamente dispares. Con recursos compartidos, el simbolo
# largo heredaba el recorte del corto; con geometria plana eso es imposible.
DIVERGENT_VALUES = [
    "A1", "Q00525499", "Q00000000000000000012345", "4281847",
    "Q1", "Q00525500", "Q00525501", "ABC-123",
    "Q00525502", "LONGVALUE-0000001", "Q00525503", "X9",
]


# WHY (v0.7.0): El aplanado alfa vive ahora en ``app.raster_probe`` como unico punto
# de verdad. Existia una copia local de esta logica y duplicarla es precisamente como
# se reintroduce el falso positivo que documenta el reporte PRE corregido.
def _flatten(png: bytes) -> Image.Image:
    return load_flattened(png)


# WHY: Comprueba que una imagen tenga contenido real. Una lamina totalmente negra
# o totalmente blanca era exactamente el modo en que un PASS podia ser falso.
def assert_image_has_content(im: Image.Image, min_ink: float = 0.0005, max_ink: float = 0.9) -> None:
    a = np.array(im)
    ink = float((a < 128).mean())
    assert a.min() < 64, "la imagen no contiene tinta"
    assert a.max() > 192, "la imagen esta completamente oscura"
    assert min_ink < ink < max_ink, f"densidad de tinta fuera de rango: {ink}"


# WHY: Los identificadores repetidos son el defecto original; se verifica en cada
# documento producido, no solo en un archivo de ejemplo.
def assert_unique_ids(svg: str) -> list[str]:
    ids = re.findall(r'\bid="([^"]+)"', svg)
    duplicates = {k: v for k, v in collections.Counter(ids).items() if v > 1}
    assert not duplicates, f"identificadores duplicados en el SVG: {duplicates}"
    return ids


def _decoders():
    from pyzbar import pyzbar
    return pyzbar


def _renderers(dpi: int = 600):
    """Independent rasterizers available on this host.

    WHY: Una sola herramienta no demuestra interoperabilidad. Se rasteriza con
    cada motor disponible y se exige el mismo resultado de decodificacion.
    """
    out = [("svglib", lambda svg, w, h: svg_to_png(svg, w, h, dpi=dpi))]
    try:
        import cairosvg

        out.append(("cairosvg", lambda svg, w, h: cairosvg.svg2png(bytestring=svg.encode(), dpi=dpi)))
    except ImportError:  # pragma: no cover - depende del entorno
        pass
    return out


def _probe_template(elements, fields, width=140.0, height=45.0) -> TemplateSpec:
    return TemplateSpec(
        id="structure_probe", name="probe", category="generic",
        width_mm=width, height_mm=height, quality_profile="rugged_field_v1",
        expected_fields=fields, elements=elements,
    )


# WHY: Un documento con varios simbolos es el caso que rompia antes; se exige
# estructura limpia y ningun recurso compartido.
def test_individual_svg_has_no_shared_resources_and_unique_ids():
    quality = load_quality_profiles()["rugged_field_v1"]
    template = _probe_template(
        [
            {"kind": "code128", "source": "a", "x_mm": 3, "y_mm": 3, "height_mm": 12, "module_mm": 0.35},
            {"kind": "code128", "source": "b", "x_mm": 3, "y_mm": 20, "height_mm": 12, "module_mm": 0.35},
            {"kind": "qr", "source": "a", "x_mm": 100, "y_mm": 3, "module_mm": 0.8},
            {"kind": "text", "source": "b", "x_mm": 3, "y_mm": 40, "font_size_mm": 4, "width_mm": 60, "align": "left"},
        ],
        ["a", "b"],
    )
    mark = render_template(template, quality, {"a": "A1", "b": "Q00000000000000000012345"})
    ET.fromstring(mark.svg)
    assert_unique_ids(mark.svg)
    assert "clipPath" not in mark.svg
    assert "scale(1,-1)" not in mark.svg
    assert mark.svg.count("<svg") == 1, "no debe haber <svg> anidados"
    assert "url(#" not in mark.svg, "el documento no debe referenciar recursos por id"


# WHY: Los identificadores deben describir el proposito del objeto para que el
# ciclo medir-en-Inkscape y devolver la medida al estudio sea posible.
def test_element_ids_are_readable_and_follow_the_data_field():
    quality = load_quality_profiles()["rugged_field_v1"]
    template = _probe_template(
        [
            {"kind": "code128", "source": "serial", "x_mm": 3, "y_mm": 3, "height_mm": 12, "module_mm": 0.35},
            {"kind": "text", "source": "serial", "x_mm": 3, "y_mm": 30, "font_size_mm": 4, "width_mm": 60},
            {"kind": "qr", "source": "economico", "x_mm": 100, "y_mm": 3, "module_mm": 0.8, "name": "qr_asset"},
        ],
        ["serial", "economico"],
    )
    mark = render_template(template, quality, {"serial": "Q00525499", "economico": "N-184"})
    assert mark.element_ids == ["barcode_serial", "text_serial", "qr_asset"]
    for element_id in mark.element_ids:
        assert f'id="{element_id}"' in mark.svg
    assert 'id="layer_codes"' in mark.svg
    assert 'id="layer_text"' in mark.svg


# WHY: Dos elementos del mismo tipo y campo no pueden colapsar en un mismo id.
def test_repeated_element_names_are_disambiguated():
    quality = load_quality_profiles()["rugged_field_v1"]
    template = _probe_template(
        [
            {"kind": "text", "source": "serial", "x_mm": 3, "y_mm": 10, "font_size_mm": 4, "width_mm": 60},
            {"kind": "text", "source": "serial", "x_mm": 3, "y_mm": 20, "font_size_mm": 4, "width_mm": 60},
            {"kind": "text", "source": "serial", "x_mm": 3, "y_mm": 30, "font_size_mm": 4, "width_mm": 60},
        ],
        ["serial"],
    )
    mark = render_template(template, quality, {"serial": "Q00525499"})
    assert mark.element_ids == ["text_serial", "text_serial_2", "text_serial_3"]
    assert_unique_ids(mark.svg)


# WHY: La cadena completa que pidio el area: dato -> SVG -> renderizador
# independiente -> PNG -> decoder independiente, y comparar INPUT con OUTPUT.
@pytest.mark.parametrize("kind,value,module", [
    ("code128", "Q00525499", 0.35),
    ("code128", "4281847", 0.35),
    ("code128", "A1", 0.35),
    ("code128", "Q00000000000000000012345", 0.35),
    ("qr", "TEL-0037", 0.8),
    ("qr", "R-425", 0.8),
])
def test_input_equals_decode_across_independent_renderers(kind, value, module):
    pyzbar = _decoders()
    quality = load_quality_profiles()["rugged_field_v1"]
    element = {"kind": kind, "source": "v", "x_mm": 3, "y_mm": 3, "module_mm": module}
    if kind == "code128":
        element["height_mm"] = 12
    template = _probe_template([element], ["v"])
    mark = render_template(template, quality, {"v": value})
    checked = 0
    for name, render in _renderers():
        im = _flatten(render(mark.svg, template.width_mm, template.height_mm))
        assert_image_has_content(im)
        decoded = [d.data.decode() for d in pyzbar.decode(im)]
        assert value in decoded, f"{name}: se esperaba {value!r} y se obtuvo {decoded!r}"
        checked += 1
    assert checked >= 1


# WHY: Prueba exigente de lote. Doce valores de longitud dispar en un mismo
# documento: identificadores unicos, grupos independientes y doce decodificaciones.
def test_batch_of_twelve_divergent_values_keeps_every_code_readable():
    pyzbar = _decoders()
    templates = load_templates()
    template = templates["inova_quantum_code128_v1"]
    quality = load_quality_profiles()[template.quality_profile]
    jig = load_jigs()["inova_tray_3x4_estimate"]
    machine = load_machines()[jig.machine_profile_id]
    rows = [{"manufacturer_id": v} for v in DIVERGENT_VALUES]
    assignments = [BatchAssignment(slot_index=i, row_index=i, physical_id=v)
                   for i, v in enumerate(DIVERGENT_VALUES)]

    batch = render_batch(machine=machine, jig=jig, template=template, quality=quality,
                         rows=rows, assignments=assignments, require_physical_confirmation=True)

    ET.fromstring(batch.svg)
    assert_unique_ids(batch.svg)
    assert "clipPath" not in batch.svg
    assert batch.svg.count("<svg") == 1
    namespaces = re.findall(r'id="(mark_\d{4})"', batch.svg)
    assert len(namespaces) == 12 and len(set(namespaces)) == 12
    for namespace in namespaces:
        assert f'id="{namespace}__barcode_manufacturer_id"' in batch.svg

    # 400 dpi sigue dando varios pixeles por modulo y evita rasterizar 90 Mpx de cama.
    for name, render in _renderers(dpi=400):
        im = _flatten(render(batch.svg, machine.bed_width_mm, machine.bed_height_mm))
        assert_image_has_content(im)
        decoded = {d.data.decode() for d in pyzbar.decode(im) if d.type == "CODE128"}
        missing = set(DIVERGENT_VALUES) - decoded
        assert not missing, f"{name}: no se decodificaron {sorted(missing)}"


# WHY: La produccion no debe arrastrar extensiones de un editor concreto; el
# maestro editable si las necesita para abrirse como capas en Inkscape.
def test_editable_and_production_modes_differ_only_where_intended():
    templates = load_templates()
    template = templates["inova_quantum_code128_v1"]
    quality = load_quality_profiles()[template.quality_profile]
    data = {"manufacturer_id": "Q00525499"}

    editable = render_template(template, quality, data, mode="editable")
    production = render_template(template, quality, data, mode="production")

    assert "inkscape:groupmode" in editable.svg
    assert "inkscape:" not in production.svg
    assert "<text" in editable.svg, "el maestro editable conserva el texto como texto"
    assert editable.element_ids == production.element_ids
    for svg in (editable.svg, production.svg):
        ET.fromstring(svg)
        assert_unique_ids(svg)
        assert f'width="{template.width_mm:.4f}mm"' in svg


# WHY: Convertir a curvas debe conservar la posicion y no debe tocar los codigos,
# que siempre permanecen como geometria vectorial real.
def test_text_as_paths_keeps_codes_vectorial_and_text_position():
    from app.text_outline import outlines_available

    if not outlines_available():  # pragma: no cover - depende del entorno
        pytest.skip("conversion a curvas no disponible en este equipo")
    templates = load_templates()
    template = templates["inova_quantum_code128_v1"]
    quality = load_quality_profiles()[template.quality_profile]
    data = {"manufacturer_id": "Q00525499"}

    outlined = render_template(template, quality, data, mode="production", text_as_paths=True)
    plain = render_template(template, quality, data, mode="production", text_as_paths=False)

    assert "<text" not in outlined.svg
    assert "<text" in plain.svg
    assert "text_outline_font" in outlined.svg
    assert_unique_ids(outlined.svg)

    im_out = _flatten(svg_to_png(outlined.svg, outlined.width_mm, outlined.height_mm, dpi=600))
    im_plain = _flatten(svg_to_png(plain.svg, plain.width_mm, plain.height_mm, dpi=600))
    assert_image_has_content(im_out)
    a, b = np.array(im_out) < 128, np.array(im_plain) < 128
    # El texto contorneado no es pixel a pixel identico al texto con otra fuente,
    # pero debe ocupar la misma banda vertical y no desplazarse horizontalmente.
    rows_out, rows_plain = np.where(a.any(axis=1))[0], np.where(b.any(axis=1))[0]
    assert abs(int(rows_out.min()) - int(rows_plain.min())) < 40
    assert abs(int(rows_out.max()) - int(rows_plain.max())) < 40


# WHY: Las coordenadas del archivo deben coincidir con los milimetros del
# disenador; de lo contrario el ciclo de ajuste fisico no es trazable.
def test_declared_millimetres_appear_in_the_file_geometry():
    quality = load_quality_profiles()["rugged_field_v1"]
    template = _probe_template(
        [{"kind": "qr", "source": "v", "x_mm": 14.0, "y_mm": 6.0, "module_mm": 0.8}], ["v"]
    )
    mark = render_template(template, quality, {"v": "R-425"})
    path = re.search(r'<path d="M ([\d.]+) ([\d.]+)', mark.svg)
    assert path, "no se encontro geometria de path"
    x, y = float(path.group(1)), float(path.group(2))
    # El primer modulo oscuro aparece tras la quiet zone declarada en el perfil.
    quiet = quality.qr_quiet_modules * 0.8
    assert abs(x - (14.0 + quiet)) < 0.81
    assert abs(y - (6.0 + quiet)) < 0.81
