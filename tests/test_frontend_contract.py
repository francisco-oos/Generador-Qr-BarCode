import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_javascript_dom_id_exists_in_html_and_html_ids_are_unique():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    referenced = set(re.findall(r"\$\(['\"]([A-Za-z0-9_-]+)['\"]\)", js))
    ids = re.findall(r'\bid=["\']([^"\']+)["\']', html)
    missing = sorted(referenced - set(ids))
    duplicates = sorted({x for x in ids if ids.count(x) > 1})
    assert not missing, f"JS references missing HTML IDs: {missing}"
    assert not duplicates, f"Duplicate HTML IDs: {duplicates}"


def test_visual_studio_contract_and_csv_flexibility_are_exposed():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    # WHY (v0.7.0): ``exportAllSvgBtn`` desaparecio como boton independiente.  El tipo
    # de entrega pasó a ser una decision explicita del operador (``outputMode``) en
    # lugar de dos botones cuya diferencia solo se entendia leyendo la etiqueta.
    for token in ("designerCanvas", "saveVisualTemplateBtn", "data-add-kind=\"code128\"", "data-add-kind=\"qr\"", "csvHeaderMode", "exportBatchBtn", 'name="outputMode"', "batchRecordPreview", "designerQualityBtn", "individualQualityBtn"):
        assert token in html
    assert "/api/templates/preview" in js
    assert "/api/bulk/svg-export" in js


def test_spreadsheet_ingestion_and_record_navigation_are_exposed():
    """WHY: Un XLSX sin selector de hoja lee la hoja equivocada en silencio, y sin
    navegador de registros nadie comprueba el registro mas largo del dataset."""
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    for token in ("csvSheet", "csvPreviewLimit", "csvPreviewTable", "recRandomBtn", "recLastBtn", "filenamePattern", "svgExportMode"):
        assert token in html, token
    assert ".xlsx" in html
    assert "/api/data/sheets" in js
    # Equipment-specific CSV synonym tables were deliberately removed from JS.
    assert "const synonyms=" not in js


def test_visual_toolbox_supports_click_and_drag_drop_without_machine_control():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    assert "application/x-marking-element" in js
    assert "dragstart" in js and "drop" in js
    assert "Pulse para agregar o arrastre directamente" in html
    # The visual editor remains a document generator, not a motion/power controller.
    assert "G0 " not in js and "G1 " not in js and "M3 " not in js and "M4 " not in js


def test_negative_engraving_strategy_is_exposed_only_as_document_generation():
    """WHY: El modo negativo debe ser una propiedad del arte SVG, no un atajo que
    mande potencia/movimiento a la grabadora ni una regla hardcodeada por fabricante."""
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    assert "propEngravingMode" in html
    assert "negative_background" in html and "negative_background" in js
    assert "G0 " not in js and "G1 " not in js and "M3 " not in js and "M4 " not in js
