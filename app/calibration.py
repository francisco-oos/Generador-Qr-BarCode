"""Calibration/reference helpers for repeatable jig-based marking.

Marking Studio deliberately does not move or fire the laser.  Calibration here
means producing reference geometry and evaluating measurements made by an
operator.  This is appropriate for open-frame GRBL machines where a removable
jig and a manually established origin are common.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot
from typing import Iterable
from xml.sax.saxutils import escape

from .models import CalibrationPoint, JigProfile, MachineProfile


def _grid_extents(jig: JigProfile) -> tuple[float, float]:
    g = jig.grid
    x_span = max(g.slot_width_mm, (g.cols - 1) * g.pitch_x_mm + g.slot_width_mm)
    y_span = max(g.slot_height_mm, (g.rows - 1) * g.pitch_y_mm + g.slot_height_mm)
    return x_span, y_span


def jig_reference_points(jig: JigProfile) -> list[CalibrationPoint]:
    """Return three repeatable physical datums for a jig.

    P0 is the jig origin; PX and PY are near the far X/Y edges.  The points are
    independent from artwork offsets, so they can be measured with a rule/caliper
    or marked on a sacrificial calibration sheet below the jig.
    """
    g = jig.grid
    x_span, y_span = _grid_extents(jig)
    return [
        CalibrationPoint(name="P0", x_mm=g.origin_x_mm, y_mm=g.origin_y_mm),
        CalibrationPoint(name="PX", x_mm=g.origin_x_mm + x_span, y_mm=g.origin_y_mm),
        CalibrationPoint(name="PY", x_mm=g.origin_x_mm, y_mm=g.origin_y_mm + y_span),
    ]


def calibration_target_svg(machine: MachineProfile, jig: JigProfile) -> str:
    """Generate a machine-bed SVG containing non-production calibration marks."""
    points = jig_reference_points(jig)
    cross = 4.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{machine.bed_width_mm}mm" height="{machine.bed_height_mm}mm" viewBox="0 0 {machine.bed_width_mm} {machine.bed_height_mm}">',
        '<g fill="none" stroke="#000" stroke-width="0.25">',
    ]
    for p in points:
        parts.append(f'<line x1="{p.x_mm-cross}" y1="{p.y_mm}" x2="{p.x_mm+cross}" y2="{p.y_mm}"/>')
        parts.append(f'<line x1="{p.x_mm}" y1="{p.y_mm-cross}" x2="{p.x_mm}" y2="{p.y_mm+cross}"/>')
        parts.append(f'<circle cx="{p.x_mm}" cy="{p.y_mm}" r="1.2"/>')
    g = jig.grid
    x_span, y_span = _grid_extents(jig)
    parts.append(f'<rect x="{g.origin_x_mm}" y="{g.origin_y_mm}" width="{x_span}" height="{y_span}" stroke-dasharray="2 2"/>')
    parts.append('</g>')
    parts.append('<g fill="#000" font-family="sans-serif" font-size="3">')
    for p in points:
        label = escape(f'{p.name} ({p.x_mm:.2f},{p.y_mm:.2f})')
        parts.append(f'<text x="{p.x_mm+2}" y="{p.y_mm-2}">{label}</text>')
    parts.append(f'<text x="5" y="8">CALIBRATION ONLY — {escape(jig.name)}</text>')
    parts.append('<text x="5" y="13">NO GRABAR SOBRE EQUIPO. Usar material de sacrificio y Frame antes de ejecutar.</text>')
    parts.append('</g></svg>')
    return ''.join(parts)


def _vector(a: CalibrationPoint, b: CalibrationPoint) -> tuple[float, float]:
    return b.x_mm - a.x_mm, b.y_mm - a.y_mm


def _length(v: tuple[float, float]) -> float:
    return hypot(v[0], v[1])


def _angle(v: tuple[float, float]) -> float:
    return degrees(atan2(v[1], v[0]))


def evaluate_reference_points(expected: Iterable[CalibrationPoint], measured: Iterable[CalibrationPoint]) -> dict:
    """Evaluate translation, scale and squareness from P0/PX/PY measurements.

    The function is diagnostic only.  It does not auto-correct coordinates or
    communicate with the controller; the operator decides whether to update the
    jig configuration after checking the physical setup.
    """
    exp = {p.name: p for p in expected}
    got = {p.name: p for p in measured}
    missing = [name for name in ("P0", "PX", "PY") if name not in exp or name not in got]
    if missing:
        raise ValueError(f"Faltan puntos requeridos: {', '.join(missing)}")
    e0, ex, ey = exp["P0"], exp["PX"], exp["PY"]
    m0, mx, my = got["P0"], got["PX"], got["PY"]
    evx, evy = _vector(e0, ex), _vector(e0, ey)
    mvx, mvy = _vector(m0, mx), _vector(m0, my)
    ex_len, ey_len = _length(evx), _length(evy)
    if ex_len <= 0 or ey_len <= 0:
        raise ValueError("La geometría esperada no tiene extensión suficiente")
    x_scale = _length(mvx) / ex_len
    y_scale = _length(mvy) / ey_len
    x_angle = _angle(mvx)
    y_angle = _angle(mvy)
    # Normalize angle between axes around 90 degrees.
    axis_angle = (y_angle - x_angle) % 360
    if axis_angle > 180:
        axis_angle = 360 - axis_angle
    square_error = axis_angle - 90.0
    translation = {"x_mm": m0.x_mm - e0.x_mm, "y_mm": m0.y_mm - e0.y_mm}
    diagnostics: list[str] = []
    if hypot(translation["x_mm"], translation["y_mm"]) > 0.5:
        diagnostics.append("El origen físico está desplazado más de 0.5 mm respecto al jig configurado.")
    if abs(x_scale - 1.0) > 0.002 or abs(y_scale - 1.0) > 0.002:
        diagnostics.append("La escala medida difiere más de 0.2%; revisar pasos/mm, dimensiones del jig o medición.")
    if abs(square_error) > 0.3:
        diagnostics.append("Los ejes medidos se desvían más de 0.3° de escuadra; revisar jig/mecánica/alineación.")
    if abs(x_angle) > 0.3:
        diagnostics.append("El eje X del jig está rotado más de 0.3° respecto a la referencia configurada.")
    return {
        "translation_mm": translation,
        "x_scale": x_scale,
        "y_scale": y_scale,
        "x_axis_angle_deg": x_angle,
        "y_axis_angle_deg": y_angle,
        "orthogonality_deg": axis_angle,
        "squareness_error_deg": square_error,
        "diagnostics": diagnostics,
        "within_guidance": not diagnostics,
        "automatic_correction_applied": False,
    }
