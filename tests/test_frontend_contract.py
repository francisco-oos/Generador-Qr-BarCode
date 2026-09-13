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
