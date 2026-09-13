from app.calibration import calibration_target_svg, evaluate_reference_points, jig_reference_points
from app.config_loader import load_jigs, load_machines
from app.models import CalibrationPoint


def test_calibration_target_and_perfect_measurement():
    jig = load_jigs()["inova_tray_3x4_estimate"]
    machine = load_machines()[jig.machine_profile_id]
    expected = jig_reference_points(jig)
    assert [p.name for p in expected] == ["P0", "PX", "PY"]
    svg = calibration_target_svg(machine, jig)
    assert "CALIBRATION ONLY" in svg
    assert f'{machine.bed_width_mm}mm' in svg
    result = evaluate_reference_points(expected, expected)
    assert result["within_guidance"] is True
    assert abs(result["x_scale"] - 1.0) < 1e-12
    assert abs(result["squareness_error_deg"]) < 1e-12
    assert result["automatic_correction_applied"] is False


def test_calibration_detects_translation_scale_and_skew():
    jig = load_jigs()["inova_tray_3x4_estimate"]
    expected = jig_reference_points(jig)
    e = {p.name: p for p in expected}
    measured = [
        CalibrationPoint(name="P0", x_mm=e["P0"].x_mm + 1.2, y_mm=e["P0"].y_mm - 0.8),
        CalibrationPoint(name="PX", x_mm=e["PX"].x_mm + 2.2, y_mm=e["PX"].y_mm - 0.1),
        CalibrationPoint(name="PY", x_mm=e["PY"].x_mm + 2.0, y_mm=e["PY"].y_mm + 1.4),
    ]
    result = evaluate_reference_points(expected, measured)
    assert result["within_guidance"] is False
    assert result["diagnostics"]
