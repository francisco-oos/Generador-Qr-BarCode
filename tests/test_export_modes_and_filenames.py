"""Export-mode selection and cross-platform output file names.

WHY:
El area pidio explicitamente poder elegir entre maestro editable, produccion o
ambos, y que "ambos" NO fuera el comportamiento por defecto de un lote masivo:
duplicar miles de archivos sin necesidad es un coste real en disco y en
confusion del operador.  Estas pruebas fijan ese contrato.
"""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from app.filenames import resolve_filename, sanitize_filename
from app.main import app

client = TestClient(app)


def _names(payload: bytes) -> set[str]:
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        return set(z.namelist())


# WHY: El valor por defecto debe ser produccion; nadie debe recibir el doble de
# archivos por no haber tocado una opcion.
def test_bulk_export_defaults_to_production_only():
    rows = [{"manufacturer_id": f"Q00{525499 + i:06d}"} for i in range(5)]
    r = client.post("/api/bulk/svg-export", json={
        "template_id": "inova_quantum_code128_v1", "rows": rows,
    })
    assert r.status_code == 200
    names = _names(r.content)
    assert any(n.startswith("svg/") for n in names)
    assert not any(n.startswith("editable/") for n in names)


# WHY: "Ambos" existe para calibracion y depuracion y debe entregar las dos
# modalidades en carpetas separadas para que no se confundan.
def test_bulk_export_both_modes_emits_separate_folders():
    rows = [{"manufacturer_id": "Q00525499"}, {"manufacturer_id": "Q00525500"}]
    r = client.post("/api/bulk/svg-export", json={
        "template_id": "inova_quantum_code128_v1", "rows": rows, "export_mode": "both",
    })
    assert r.status_code == 200
    names = _names(r.content)
    assert "svg/Q00525499.svg" in names
    assert "editable/Q00525499.svg" in names
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        production = z.read("svg/Q00525499.svg").decode()
        editable = z.read("editable/Q00525499.svg").decode()
    assert "inkscape:groupmode" in editable
    assert "inkscape:" not in production


# WHY: El modo editable por si solo no debe arrastrar la carpeta de produccion.
def test_bulk_export_editable_only():
    r = client.post("/api/bulk/svg-export", json={
        "template_id": "inova_quantum_code128_v1",
        "rows": [{"manufacturer_id": "Q00525499"}], "export_mode": "editable",
    })
    assert r.status_code == 200
    names = _names(r.content)
    assert any(n.startswith("editable/") for n in names)
    assert not any(n.startswith("svg/") for n in names)


# WHY: El patron de nombre es una peticion directa del area: {economico}_{serial}.svg
def test_filename_pattern_combines_multiple_fields():
    rows = [{"manufacturer_id": "Q00525499", "economico": "N-184"}]
    r = client.post("/api/bulk/svg-export", json={
        "template_id": "inova_quantum_code128_v1", "rows": rows,
        "filename_pattern": "{economico}_{manufacturer_id}",
    })
    assert r.status_code == 200
    assert "svg/N-184_Q00525499.svg" in _names(r.content)


# WHY: Un CSV real trae barras, dos puntos y acentos; el nombre debe seguir siendo
# abrible en Windows, Linux y macOS sin que el operador tenga que renombrar nada.
def test_filenames_are_sanitized_for_every_target_platform():
    assert sanitize_filename("A/B:C*D?E") == "A_B_C_D_E"
    assert sanitize_filename("  espacio  interno ") == "espacio_interno"
    assert sanitize_filename("ñandú-Q00") == "nandu-Q00"
    assert sanitize_filename("") == "mark"
    # Nombres reservados de Windows no pueden quedar tal cual.
    assert sanitize_filename("CON") != "CON"
    assert sanitize_filename("lpt1.svg").startswith("_")
    assert len(sanitize_filename("X" * 400)) <= 100


# WHY: Sin patron ni campo, el nombre cae en la identidad principal de la plantilla,
# que es configuracion y no una rama por fabricante en el codigo.
def test_filename_falls_back_to_template_primary_identity():
    from app.config_loader import load_templates

    template = load_templates()["inova_quantum_code128_v1"]
    name = resolve_filename({"manufacturer_id": "Q00525499"}, template, None, None, 1)
    assert name == "Q00525499"


# WHY: Duplicados en el CSV no deben sobrescribirse en silencio dentro del ZIP.
def test_duplicate_identifiers_do_not_overwrite_each_other():
    rows = [{"manufacturer_id": "Q00525499"}, {"manufacturer_id": "Q00525499"}]
    r = client.post("/api/bulk/svg-export", json={
        "template_id": "inova_quantum_code128_v1", "rows": rows,
    })
    names = _names(r.content)
    assert "svg/Q00525499.svg" in names
    assert "svg/Q00525499_002.svg" in names


# WHY: La conversion a curvas solo debe aplicarse cuando se pidio, y solo al texto.
def test_render_endpoint_exposes_both_svg_modes():
    body = {"template_id": "inova_quantum_code128_v1", "data": {"manufacturer_id": "525499"}}
    production = client.post("/api/render", json={**body, "svg_mode": "production"}).json()
    editable = client.post("/api/render", json={**body, "svg_mode": "editable"}).json()
    outlined = client.post("/api/render", json={**body, "svg_mode": "production", "text_as_paths": True}).json()

    assert production["svg_mode"] == "production"
    assert "inkscape:" not in production["svg"]
    assert "inkscape:groupmode" in editable["svg"]
    assert "<text" in editable["svg"]
    assert "<text" not in outlined["svg"]
    assert production["element_ids"] == editable["element_ids"]


# WHY: Un lote con jig tambien debe respetar la eleccion, y el maestro editable
# debe quedar en su propia carpeta para no confundirse con el archivo de maquina.
def test_batch_zip_includes_editable_master_only_when_requested():
    rows = [{"manufacturer_id": f"Q00{525499 + i:06d}"} for i in range(3)]
    payload = {
        "template_id": "inova_quantum_code128_v1",
        "jig_id": "inova_tray_3x4_estimate",
        "rows": rows,
        "assignments": [
            {"slot_index": i, "row_index": i, "physical_id": rows[i]["manufacturer_id"]}
            for i in range(3)
        ],
        "require_physical_confirmation": True,
    }
    default = client.post("/api/batch/export", json=payload)
    assert default.status_code == 200
    assert not any(n.startswith("editable/") for n in _names(default.content))

    both = client.post("/api/batch/export", json={**payload, "export_mode": "both"})
    assert both.status_code == 200
    assert "editable/batch_master_editable.svg" in _names(both.content)


# WHY: Encontrado durante la verificacion del paquete 0.7.0. El concepto "que tipo de
# SVG generar" se llamaba ``svg_mode`` en los endpoints de artefacto unico y
# ``export_mode`` en los de lote. Pydantic ignora los campos desconocidos, asi que un
# cliente que usara el nombre equivocado recibia produccion en silencio y solo lo
# descubria al abrir el archivo. Ambos nombres deben funcionar.
def test_svg_mode_and_export_mode_are_interchangeable_on_single_artifact_requests():
    from app.models import RenderRequest, TemplatePreviewRequest

    spec = {
        "id": "alias_probe", "name": "p", "category": "generic",
        "width_mm": 40, "height_mm": 18, "quality_profile": "rugged_field_v1",
        "expected_fields": ["a"],
        "elements": [{"kind": "text", "source": "a", "x_mm": 1, "y_mm": 6}],
    }

    assert RenderRequest(template_id="t", data={}, svg_mode="editable").svg_mode == "editable"
    assert RenderRequest(**{"template_id": "t", "data": {}, "export_mode": "editable"}).svg_mode == "editable"
    assert RenderRequest(template_id="t", data={}).svg_mode == "production"

    assert TemplatePreviewRequest(template=spec, svg_mode="editable").svg_mode == "editable"
    assert TemplatePreviewRequest(**{"template": spec, "export_mode": "editable"}).svg_mode == "editable"
    assert TemplatePreviewRequest(template=spec).svg_mode == "production"


def test_editable_mode_actually_differs_from_production_over_the_api():
    """WHY: El alias no sirve de nada si ambos modos devuelven el mismo archivo."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    body = {"template_id": "inova_quantum_code128_v1",
            "data": {"manufacturer_id": "Q00525499"}, "output": "svg"}

    production = client.post("/api/render", json={**body, "export_mode": "production"}).json()["svg"]
    editable = client.post("/api/render", json={**body, "export_mode": "editable"}).json()["svg"]

    assert production != editable
    assert "inkscape:label" in editable
    assert "inkscape:label" not in production
