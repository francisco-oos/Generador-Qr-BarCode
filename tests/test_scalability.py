from app.config_loader import load_quality_profiles, load_templates
from app.template_engine import render_template


def test_generate_more_than_1000_marks_without_state_leak():
    t = load_templates()["inova_quantum_code128_v1"]
    q = load_quality_profiles()[t.quality_profile]
    seen = set()
    for i in range(1100):
        value = f"Q{5000000+i:08d}"
        result = render_template(t, q, {"manufacturer_id": value})
        assert value in result.svg
        assert not result.warnings
        seen.add(value)
    assert len(seen) == 1100
