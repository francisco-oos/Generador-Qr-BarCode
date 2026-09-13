"""Ingestion (CSV/XLSX) and declarative data-transformation contracts.

WHY: Estas pruebas existen porque los dos fallos mas caros de este flujo no son
de render sino de datos: leer la hoja equivocada de un libro y grabar un
identificador alterado por Excel (``4281847.0``, ``184`` en lugar de ``00184``).
Ambos producen un SVG perfectamente valido con el dato incorrecto.
"""

from __future__ import annotations

import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import TemplateSpec
from app.tabular import cell_to_text, detect_format, inspect_tabular, list_sheets
from app.template_engine import apply_input_rules

client = TestClient(app)


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


# ---------------------------------------------------------------- XLSX reading

def test_xlsx_sheets_are_listed_and_first_is_not_assumed():
    raw = _workbook({
        "Instructivo": [["Llenar la hoja Inventario"]],
        "Inventario": [["serial", "economico"], ["Q00525499", "N-184"]],
    })
    assert list_sheets(raw) == ["Instructivo", "Inventario"]

    default = inspect_tabular("libro.xlsx", raw)
    assert default["sheet"] == "Instructivo"

    chosen = inspect_tabular("libro.xlsx", raw, sheet="Inventario")
    assert chosen["sheet"] == "Inventario"
    assert chosen["headers"] == ["serial", "economico"]
    assert chosen["rows"][0]["serial"] == "Q00525499"


def test_xlsx_numeric_identifier_never_gains_a_decimal_point():
    # Excel guarda 4281847 como numero; grabarlo como '4281847.0' seria un
    # identificador inexistente que ademas pasaria el preflight sin problema.
    raw = _workbook({"Datos": [["serial"], [4281847], [525499]]})
    result = inspect_tabular("datos.xlsx", raw, sheet="Datos")
    assert [r["serial"] for r in result["rows"]] == ["4281847", "525499"]


def test_cell_to_text_covers_types_excel_actually_produces():
    import datetime as dt
    assert cell_to_text(None) == ""
    assert cell_to_text(12) == "12"
    assert cell_to_text(12.0) == "12"
    assert cell_to_text(12.5) == "12.5"
    assert cell_to_text(True) == "TRUE"
    assert cell_to_text(dt.date(2026, 9, 12)) == "2026-09-12"


def test_xlsx_duplicate_headers_are_disambiguated_instead_of_overwritten():
    raw = _workbook({"H": [["serial", "serial"], ["A1", "B1"]]})
    result = inspect_tabular("dup.xlsx", raw, sheet="H")
    assert result["headers"] == ["serial", "serial_2"]
    assert result["rows"][0] == {"serial": "A1", "serial_2": "B1"}


def test_xlsx_single_column_list_without_header_keeps_every_record():
    raw = _workbook({"L": [["Q00525499"], ["Q00525500"], ["Q00525501"]]})
    result = inspect_tabular("lista.xlsx", raw, sheet="L", header_mode="no")
    assert result["headers"] == ["value"]
    assert [r["value"] for r in result["rows"]] == ["Q00525499", "Q00525500", "Q00525501"]


def test_legacy_xls_is_refused_with_an_actionable_message():
    raw = b"\xd0\xcf\x11\xe0" + b"\x00" * 64
    with pytest.raises(ValueError) as exc:
        inspect_tabular("viejo.xls", raw)
    assert ".xlsx" in str(exc.value)


def test_format_is_detected_by_content_not_only_by_extension():
    raw = _workbook({"A": [["serial"], ["X1"]]})
    # Un adjunto renombrado sigue siendo un XLSX.
    assert detect_format("inventario.csv", raw) == "xlsx"
    assert detect_format("lista.csv", b"serial\nX1\n") == "text"


# ------------------------------------------------------------------- endpoints

def test_inspect_endpoint_accepts_xlsx_and_exposes_sheets():
    raw = _workbook({
        "Portada": [["no usar"]],
        "Nodos": [["serial"], ["Q00525499"], ["Q00525500"]],
    })
    r = client.post(
        "/api/csv/inspect?sheet=Nodos&preview_limit=1",
        files={"file": ("inv.xlsx", raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["format"] == "xlsx"
    assert body["sheets"] == ["Portada", "Nodos"]
    assert body["sheet"] == "Nodos"
    assert body["count"] == 2
    assert len(body["preview"]) == 1


def test_sheets_endpoint_reports_text_files_without_failing():
    r = client.post("/api/data/sheets", files={"file": ("l.csv", b"serial\nQ1\n", "text/csv")})
    assert r.status_code == 200
    assert r.json()["sheets"] == []


def test_csv_path_still_returns_the_historic_contract():
    raw = b"serial,economico\nQ00525499,N-184\nQ00525500,N-185\n"
    r = client.post("/api/csv/inspect", files={"file": ("l.csv", raw, "text/csv")})
    body = r.json()
    for key in ("headers", "count", "rows", "preview", "header_mode"):
        assert key in body
    assert body["headers"] == ["serial", "economico"]
    assert body["count"] == 2
    assert body["delimiter"] == ","


def test_headerless_single_column_csv_keeps_the_first_identifier():
    # Invariante historico: una lista de seriales no debe perder el primero por
    # confundirlo con un encabezado.
    raw = b"Q00525499\nQ00525500\n"
    r = client.post("/api/csv/inspect", files={"file": ("l.csv", raw, "text/csv")})
    body = r.json()
    assert body["count"] == 2
    assert body["rows"][0]["value"] == "Q00525499"


# -------------------------------------------------------------- transformations

def _template(rules=None, derived=None) -> TemplateSpec:
    return TemplateSpec(
        id="t_transform", name="t", category="generic",
        width_mm=50, height_mm=18, quality_profile="rugged_field_v1",
        expected_fields=["serial", "economico"],
        input_rules=rules or [],
        derived_fields=derived or [],
        elements=[{"kind": "text", "source": "serial", "x_mm": 1, "y_mm": 5}],
    )


def test_zero_padding_restores_leading_zeros_lost_by_excel():
    t = _template(rules=[{"field": "economico", "pad_zeros_to": 5}])
    out = apply_input_rules(t, {"economico": "184"}, capture_mode="import")
    assert out["economico"] == "00184"


def test_zero_padding_never_truncates_a_longer_value():
    t = _template(rules=[{"field": "serial", "pad_zeros_to": 4}])
    out = apply_input_rules(t, {"serial": "Q00525499"}, capture_mode="import")
    assert out["serial"] == "Q00525499"


def test_lowercase_rule_applies_and_contradicts_uppercase():
    t = _template(rules=[{"field": "serial", "lowercase": True}])
    assert apply_input_rules(t, {"serial": "ABC-1"})["serial"] == "abc-1"
    with pytest.raises(Exception):
        _template(rules=[{"field": "serial", "uppercase": True, "lowercase": True}])


def test_derived_field_concatenates_after_input_rules():
    t = _template(
        rules=[{"field": "economico", "pad_zeros_to": 5}],
        derived=[{"field": "etiqueta", "expression": "{serial}-{economico}"}],
    )
    out = apply_input_rules(t, {"serial": "Q00525499", "economico": "184"}, capture_mode="import")
    # El padding debe haberse aplicado ANTES de componer la etiqueta.
    assert out["etiqueta"] == "Q00525499-00184"


def test_derived_field_respects_existing_csv_value_unless_overwrite():
    t = _template(derived=[{"field": "etiqueta", "expression": "{serial}"}])
    out = apply_input_rules(t, {"serial": "A", "etiqueta": "YA_VENIA"}, capture_mode="import")
    assert out["etiqueta"] == "YA_VENIA"

    t2 = _template(derived=[{"field": "etiqueta", "expression": "{serial}", "overwrite": True}])
    out2 = apply_input_rules(t2, {"serial": "A", "etiqueta": "YA_VENIA"}, capture_mode="import")
    assert out2["etiqueta"] == "A"


def test_derived_field_missing_placeholder_stays_visible():
    t = _template(derived=[{"field": "etiqueta", "expression": "{serial}/{no_existe}"}])
    out = apply_input_rules(t, {"serial": "A"}, capture_mode="import")
    assert out["etiqueta"] == "A/{no_existe}"


def test_import_mode_still_never_double_prefixes():
    # Invariante historico: no debe romperse al agregar transformaciones.
    t = _template(rules=[{"field": "serial", "manual_prefix_enabled": True, "manual_prefix": "Q00"}])
    assert apply_input_rules(t, {"serial": "Q00525499"}, capture_mode="import")["serial"] == "Q00525499"
    assert apply_input_rules(t, {"serial": "525499"}, capture_mode="manual")["serial"] == "Q00525499"
    assert apply_input_rules(t, {"serial": "Q00525499"}, capture_mode="manual")["serial"] == "Q00525499"
