from app.config_loader import load_templates
from app.template_engine import apply_input_rules


def test_inova_manual_short_number_gets_configured_prefix():
    template = load_templates()["inova_quantum_code128_v1"]
    result = apply_input_rules(template, {"manufacturer_id": "525499"}, capture_mode="manual")
    assert result["manufacturer_id"] == "Q00525499"


def test_inova_manual_full_identifier_is_not_double_prefixed():
    template = load_templates()["inova_quantum_code128_v1"]
    result = apply_input_rules(template, {"manufacturer_id": "q00525499"}, capture_mode="manual")
    assert result["manufacturer_id"] == "Q00525499"


def test_inova_imported_identifier_is_respected_as_is():
    template = load_templates()["inova_quantum_code128_v1"]
    full = apply_input_rules(template, {"manufacturer_id": "Q00525499"}, capture_mode="import")
    short = apply_input_rules(template, {"manufacturer_id": "525499"}, capture_mode="import")
    assert full["manufacturer_id"] == "Q00525499"
    assert short["manufacturer_id"] == "525499"


def test_import_mode_can_be_explicitly_configured_to_ensure_prefix():
    from copy import deepcopy
    template = deepcopy(load_templates()["inova_quantum_code128_v1"])
    template.input_rules[0].imported_values = "ensure_prefix_suffix"
    result = apply_input_rules(template, {"manufacturer_id": "525499"}, capture_mode="import")
    assert result["manufacturer_id"] == "Q00525499"
