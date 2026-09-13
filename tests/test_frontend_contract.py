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
    for token in ("designerCanvas", "saveVisualTemplateBtn", "data-add-kind=\"code128\"", "data-add-kind=\"qr\"", "csvHeaderMode", "exportAllSvgBtn", "batchRecordPreview"):
        assert token in html
    assert "/api/templates/preview" in js
    assert "/api/bulk/svg-export" in js
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
