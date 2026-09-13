from pathlib import Path

import pytest

from app.batch_engine import chunk_count, parse_csv_text, render_batch, slot_positions
from app.config_loader import load_jigs, load_machines, load_quality_profiles, load_templates
from app.models import BatchAssignment

ROOT = Path(__file__).resolve().parent.parent


def test_csv_1200_and_chunking():
    text = (ROOT / "samples/input/inova_1200.csv").read_text(encoding="utf-8-sig")
    headers, rows = parse_csv_text(text)
    assert "manufacturer_id" in headers
    assert len(rows) == 1200
    jig = load_jigs()["inova_tray_3x4_estimate"]
    assert jig.capacity == 12
    assert chunk_count(len(rows), jig.capacity) == 100


def test_batch_requires_physical_match():
    t = load_templates()["inova_quantum_code128_v1"]
    q = load_quality_profiles()[t.quality_profile]
    j = load_jigs()["inova_tray_3x4_estimate"]
    m = load_machines()[j.machine_profile_id]
    rows = [{"manufacturer_id": "Q00525499"}]
    good = [BatchAssignment(slot_index=0, row_index=0, physical_id="Q00525499")]
    result = render_batch(m, j, t, q, rows, good, True)
    assert len(result.manifest) == 1
    assert result.manifest[0]["physical_match"] is True
    bad = [BatchAssignment(slot_index=0, row_index=0, physical_id="Q00525498")]
    with pytest.raises(ValueError, match="no coincide"):
        render_batch(m, j, t, q, rows, bad, True)


def test_all_jig_slots_are_inside_machine_bed():
    machines = load_machines()
    for jig in load_jigs().values():
        m = machines[jig.machine_profile_id]
        for s in slot_positions(jig):
            assert float(s["slot_x_mm"]) >= 0
            assert float(s["slot_y_mm"]) >= 0
            assert float(s["slot_x_mm"]) + jig.grid.slot_width_mm <= m.bed_width_mm + 1e-6
            assert float(s["slot_y_mm"]) + jig.grid.slot_height_mm <= m.bed_height_mm + 1e-6


def test_csv_dialects_bom_quotes_blank_and_5000_rows():
    text = '\ufeffmanufacturer_id;note\n"Q00525499";"campo, uno"\n\nQ00525500;ok\n'
    headers, rows = parse_csv_text(text)
    assert headers == ["manufacturer_id", "note"]
    assert len(rows) == 2
    assert rows[0]["note"] == "campo, uno"

    tsv = "manufacturer_id\tnote\n" + "\n".join(f"Q{i:08d}\trow {i}" for i in range(5000))
    headers2, rows2 = parse_csv_text(tsv)
    assert headers2 == ["manufacturer_id", "note"]
    assert len(rows2) == 5000
    assert rows2[-1]["manufacturer_id"] == "Q00004999"


def test_physical_reconciliation_uses_template_primary_identity_not_fixed_field_names():
    from app.models import TemplateSpec, BatchAssignment
    from app.config_loader import load_machines, load_jigs, load_quality_profiles
    from app.batch_engine import render_batch

    template = TemplateSpec.model_validate({
        "id":"qa_custom_identity","name":"QA","category":"generic","width_mm":30,"height_mm":12,
        "quality_profile":"rugged_field_v1","expected_fields":["folio_local"],"input_rules":[],
        "elements":[{"kind":"text","x_mm":1,"y_mm":8,"source":"folio_local","width_mm":28,"font_size_mm":4,"align":"center"}],
        "metadata":{"primary_identity_field":"folio_local"},
    })
    machine = load_machines()["sculpfun_s9_pro_10w"]
    jig = load_jigs()["single_asset"]
    quality = load_quality_profiles()["rugged_field_v1"]
    result = render_batch(machine, jig, template, quality, [{"folio_local":"ABC-77"}], [BatchAssignment(slot_index=0,row_index=0,physical_id="ABC-77")], True)
    assert result.manifest[0]["id"] == "ABC-77"
