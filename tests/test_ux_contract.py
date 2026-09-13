from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_task_first_home_and_grouped_navigation_exist():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    for token in (
        'id="tab-home"',
        'data-open-tab="individual"',
        'data-open-tab="batch"',
        'data-open-tab="config"',
        'data-open-tab="verify"',
        'class="nav-group">Operación',
        'class="nav-group">Diseño',
        'class="nav-group">Control',
    ):
        assert token in html


def test_batch_stepper_and_designer_layer_list_are_exposed():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    for token in ('id="batchStepper"', 'data-batch-step="1"', 'data-batch-step="4"', 'id="designerLayerList"'):
        assert token in html
    assert "function updateBatchStepper" in js
    assert "function renderDesignerLayerList" in js


def test_individual_preview_is_live_but_debounced():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "function scheduleIndividualPreview" in js
    assert "setTimeout(renderIndividual,160)" in js
    assert "addEventListener('input',scheduleIndividualPreview)" in js


def test_guided_mode_hides_system_navigation_only_as_presentation():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert 'data-tab="system" class="expert-nav"' in html
    assert "querySelectorAll('.expert-nav')" in js
    # Safety boundary remains independent of UX mode.
    assert "G0 " not in js and "G1 " not in js and "M3 " not in js and "M4 " not in js
