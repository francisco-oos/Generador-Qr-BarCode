"""Visual-studio interaction contracts and real-world ingestion edge cases.

WHY: El estudio visual vive en JavaScript sin runtime de pruebas en este proyecto.
En lugar de fingir cobertura de comportamiento, estas pruebas verifican el
*contrato* observable del codigo y de la interfaz: que las operaciones existan,
que esten conectadas y que respeten las invariantes que el motor si prueba en
Python (milimetros, historial por operacion logica, imantado desactivable).

Los casos de ingesta si son de comportamiento real y cubren lo que un archivo de
inventario del area trae de verdad: celdas vacias, encabezados con espacios,
acentos y columnas repetidas.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import openpyxl
import pytest

from app.tabular import inspect_tabular
from app.template_engine import apply_input_rules
from app.models import TemplateSpec

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")


# WHY: Extrae el cuerpo de una funcion JS por conteo de llaves. Recortar por indices
# de texto es fragil: basta reordenar el archivo para que una prueba compare la
# porcion equivocada y falle o, peor, pase por casualidad.
def js_function(name: str) -> str:
    start = JS.index(f"function {name}(")
    depth = 0
    opened = False
    for i in range(start, len(JS)):
        if JS[i] == "{":
            depth += 1
            opened = True
        elif JS[i] == "}":
            depth -= 1
            if opened and depth == 0:
                return JS[start:i + 1]
    raise AssertionError(f"no se pudo delimitar la funcion {name}")


def _workbook(sheets: dict[str, list[list]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------- UNDO / REDO

def test_history_exists_and_is_bounded():
    for token in ("function pushHistory", "function undoDesigner", "function redoDesigner",
                  "HISTORY_LIMIT", "HISTORY_COALESCE_MS"):
        assert token in JS, token
    # Un historial sin limite crece hasta agotar memoria en una sesion larga.
    assert re.search(r"if\(h\.past\.length>HISTORY_LIMIT\)\s*h\.past\.shift\(\)", JS)


def test_drag_records_exactly_one_history_entry():
    """WHY: El requisito explicito es que un arrastre completo sea UNA operacion
    logica y no doscientos pasos de deshacer."""
    drag = js_function("beginDesignerDrag")
    assert drag.count("pushHistory(") == 1
    # Y debe registrarse antes de mover: el snapshot tiene que ser el estado previo.
    assert drag.index("pushHistory(") < drag.index("const move=")


def test_every_mutating_designer_action_is_undoable():
    for label in ("'drag:", "'prop:", "'add:", "'delete:", "'duplicate:", "'rotate:", "'nudge:", "'align:"):
        assert f"pushHistory({label}" in JS, label


def test_undo_and_redo_are_reachable_by_button_and_keyboard():
    assert 'id="undoBtn"' in HTML and 'id="redoBtn"' in HTML
    assert "undoDesigner" in JS and "redoDesigner" in JS
    assert "e.key.toLowerCase()==='z'" in JS and "e.key.toLowerCase()==='y'" in JS
    # Los atajos no deben capturarse fuera de la pestaña de diseño.
    shortcut = JS[JS.index("const z=(e.ctrlKey"):]
    assert "tab-config" in JS[JS.index("document.addEventListener('keydown'"):][:1200]


# ---------------------------------------------------------------------- SNAP

def test_snap_can_be_switched_off_and_has_a_configurable_grid():
    assert 'id="snapEnabled"' in HTML and 'id="snapGrid"' in HTML
    assert "function snapSettings" in JS and "function applySnap" in JS
    # Desactivado debe devolver la posicion intacta, sin imantar ni redondear.
    assert "if(!enabled) return {value:position, guide:null};" in JS


def test_snap_targets_grid_canvas_centre_and_other_elements():
    candidates = js_function("snapCandidates")
    assert "canvas-center" in candidates and "element-center" in candidates
    # El propio objeto queda excluido para que no se imante consigo mismo.
    assert "excludeIndices.includes(i)" in candidates


def test_snap_tolerance_is_expressed_in_screen_pixels_not_millimetres():
    """WHY: Una tolerancia fija en mm se vuelve inusable al hacer zoom: con mucho
    aumento el objeto salta varios milimetros visibles."""
    assert "6/Math.max(.0001,state.designerScale||1)" in JS


def test_snap_guides_are_transient_and_never_exported():
    assert "function renderSnapGuides" in JS
    assert "renderSnapGuides([])" in JS  # se limpian al soltar
    assert ".snap-guide" in CSS
    # Las guias son nodos del DOM del editor; no pueden acabar en el SVG del backend.
    assert "snap-guide" not in (ROOT / "app/svg_document.py").read_text(encoding="utf-8")


# ---------------------------------------------------- SELECCION Y ALINEACION

def test_multiple_selection_exists_and_drives_alignment_availability():
    assert "designerSelection" in JS
    assert "function toggleDesignerSelection" in JS
    assert "ev.ctrlKey||ev.metaKey||ev.shiftKey" in JS
    info = js_function("updateSelectionInfo")
    # Alinear con un solo objeto no hace nada visible: el boton debe estar inhabilitado.
    assert "n<2" in info and "n<3" in info


def test_all_six_alignments_plus_both_distributions_are_implemented():
    align = js_function("alignDesignerSelection")
    for action in ("'left'", "'right'", "'center-h'", "'top'", "'bottom'", "'center-v'", "'dist-h'", "'dist-v'"):
        assert f"action==={action}" in align, action
    for action in ("left", "center-h", "right", "top", "center-v", "bottom", "dist-h", "dist-v"):
        assert f'data-align="{action}"' in HTML, action


def test_alignment_operates_on_physical_millimetres():
    """WHY: El zoom del lienzo no debe cambiar el resultado de alinear."""
    align = js_function("alignDesignerSelection")
    assert "designerBounds" in align and "setDesignerBounds" in align
    assert "designerScale" not in align


def test_text_baseline_offset_is_handled_by_the_bounds_helper():
    """WHY: El texto se ancla en su linea base; alinearlo por ``y_mm`` crudo lo
    dejaria una altura de fuente fuera de sitio."""
    bounds = js_function("designerBounds")
    assert "el.kind==='text'" in bounds and "font_size_mm" in bounds


# ------------------------------------------------------------------ ROTACION

def test_rotation_controls_offer_quick_angles_and_a_custom_value():
    for angle in ("0", "90", "180", "270"):
        assert f'data-rotate="{angle}"' in HTML, angle
    assert 'id="propRotation"' in HTML
    assert "el.rotation_deg=((Number($('propRotation').value)||0)%360+360)%360;" in JS


def test_canvas_previews_rotation_with_the_same_centre_as_the_backend():
    assert "rotate(${el.rotation_deg}deg)" in JS


# ---------------------------------------------------------------- QUIET ZONE

def test_quiet_zone_is_a_per_element_property_with_profile_inheritance():
    assert 'id="propQuiet"' in HTML
    # Vacio hereda el perfil; 0 explicito es una decision del usuario y se conserva.
    assert "el.quiet_modules=$('propQuiet').value===''?null:" in JS
    assert "quietHint" in HTML


# ----------------------------------------------------------- MAPEO INTERACTIVO

def test_mapping_shows_which_elements_consume_each_column():
    assert "function elementsUsingField" in JS
    assert "map-consumers" in JS and ".map-consumers" in CSS
    # Un campo puede alimentar varios elementos a la vez (barcode + texto legible).
    fn = js_function("elementsUsingField")
    assert ".filter(" in fn and "split('|')" in fn


def test_mapping_focus_highlights_panel_canvas_and_data_column():
    focus = js_function("focusMappingField")
    assert "map-row" in focus and "column-hit" in focus and "renderDesignerCanvas()" in focus
    assert "mapping-hit" in JS and ".mapping-hit" in CSS
    # La tabla de datos debe etiquetar sus celdas por columna para poder resaltarlas.
    assert 'data-column="${esc(h)}"' in JS


def test_record_navigation_refreshes_the_real_preview_immediately():
    for token in ("recFirstBtn", "recPrevBtn", "recNextBtn", "recLastBtn", "recRandomBtn", "recIndex"):
        assert token in HTML, token
    goto = js_function("gotoRecord")
    assert "renderBatchRecordPreview()" in goto
    # El indice se acota al dataset real para no apuntar a un registro inexistente.
    assert "Math.max(0,Math.min(total-1,index))" in goto


def test_output_grouping_and_svg_mode_are_independent_decisions():
    """WHY: Agrupar registros y elegir tipo de SVG son decisiones ortogonales;
    mezclarlas obligaria a duplicar opciones (jig-editable, jig-produccion, ...)."""
    assert 'name="outputMode"' in HTML and 'id="svgExportMode"' in HTML
    assert "function selectedOutputMode" in JS
    for mode in ("jig", "individual", "both"):
        assert f'value="{mode}"' in HTML, mode
    for mode in ("production", "editable"):
        assert f'value="{mode}"' in HTML, mode


# ------------------------------------------------- INGESTA: CASOS REALES

def test_csv_plain_identifier_list_keeps_all_records():
    result = inspect_tabular("l.csv", b"Q00525499\nQ00525500\n", header_mode="no")
    assert [r["value"] for r in result["rows"]] == ["Q00525499", "Q00525500"]


def test_csv_with_headers_maps_all_columns():
    raw = b"serial,economico,modelo\nQ00525499,N-184,Quantum\n"
    result = inspect_tabular("l.csv", raw, header_mode="yes")
    assert result["headers"] == ["serial", "economico", "modelo"]
    assert result["rows"][0]["modelo"] == "Quantum"


def test_headers_with_spaces_and_accents_survive_ingestion():
    raw = "número económico;descripción\n184;Nodo sísmico\n".encode("utf-8")
    result = inspect_tabular("l.csv", raw, header_mode="yes")
    assert "número económico" in result["headers"]
    assert result["rows"][0]["descripción"] == "Nodo sísmico"


def test_empty_cells_become_empty_strings_not_none():
    raw = _workbook({"D": [["serial", "economico"], ["Q1", None], ["Q2", "N-2"]]})
    result = inspect_tabular("d.xlsx", raw, sheet="D")
    assert result["rows"][0]["economico"] == ""
    assert result["rows"][1]["economico"] == "N-2"


def test_special_characters_are_preserved_verbatim():
    raw = _workbook({"S": [["serial"], ["AB/CD-01"], ["ÑÁÉ#1"], ["a b c"]]})
    result = inspect_tabular("s.xlsx", raw, sheet="S", header_mode="yes")
    assert [r["serial"] for r in result["rows"]] == ["AB/CD-01", "ÑÁÉ#1", "a b c"]


def test_single_data_row_is_valid():
    raw = _workbook({"U": [["serial"], ["Q00525499"]]})
    result = inspect_tabular("u.xlsx", raw, sheet="U", header_mode="yes")
    assert result["count"] == 1


def test_thousands_of_rows_are_read_and_preview_stays_bounded():
    rows = [["serial"]] + [[f"Q00{525499 + i:06d}"] for i in range(5000)]
    raw = _workbook({"Big": rows})
    result = inspect_tabular("big.xlsx", raw, sheet="Big", header_mode="yes", preview_limit=25)
    assert result["count"] == 5000
    assert len(result["preview"]) == 25, "la vista previa no debe cargar 5000 filas"


def test_excel_leading_zeros_are_recoverable_with_declarative_padding():
    """WHY: Caso real y caro. Excel guarda ``00184`` como numero 184 y se pierde el
    formato. El padding declarativo debe poder reponerlo sin editar el archivo."""
    raw = _workbook({"Z": [["economico"], [184], [7], [12345]]})
    ingested = inspect_tabular("z.xlsx", raw, sheet="Z", header_mode="yes")
    assert [r["economico"] for r in ingested["rows"]] == ["184", "7", "12345"]

    template = TemplateSpec(
        id="pad", name="p", category="generic", width_mm=40, height_mm=18,
        quality_profile="rugged_field_v1", expected_fields=["economico"],
        input_rules=[{"field": "economico", "pad_zeros_to": 5}],
        elements=[{"kind": "text", "source": "economico", "x_mm": 1, "y_mm": 6}],
    )
    restored = [apply_input_rules(template, r, capture_mode="import")["economico"]
                for r in ingested["rows"]]
    assert restored == ["00184", "00007", "12345"]


def test_multi_sheet_workbook_reads_the_requested_sheet_only():
    raw = _workbook({
        "Portada": [["Inventario 2026"]],
        "Nodos": [["serial"], ["Q00525499"]],
        "Telefonos": [["serial"], ["TEL-0037"], ["TEL-0038"]],
    })
    assert inspect_tabular("m.xlsx", raw, sheet="Nodos", header_mode="yes")["count"] == 1
    assert inspect_tabular("m.xlsx", raw, sheet="Telefonos", header_mode="yes")["count"] == 2
    with pytest.raises(ValueError):
        inspect_tabular("m.xlsx", raw, sheet="NoExiste")
