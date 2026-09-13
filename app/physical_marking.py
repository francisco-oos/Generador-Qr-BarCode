"""Physical-marking helpers introduced in v0.8.0.

This module deliberately does not encode QR/barcode data. It only transforms the
already-generated positive geometry into an ablation strategy. Keeping this layer
separate prevents a physical experiment (relief/intaglio) from changing the data
that a scanner is expected to read.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .code_geometry import Rectangle, expand_and_union_rects, rects_to_path_data
from .models import MarkingMode

CODE_KINDS = {"code128", "code39", "qr", "datamatrix"}


# WHY: Agrupa métricas aproximadas de ablación sin convertirlas en recetas de potencia/tiempo no medidas.
@dataclass(frozen=True)
class MarkingMetrics:
    estimated_ablation_mm2: float | None = None
    estimated_canvas_ratio: float | None = None


def effective_marking_mode(template_mode: MarkingMode, override: MarkingMode | None) -> MarkingMode:
    """Choose a job override without mutating the saved template."""
    return (override or template_mode).model_copy(deep=True)


def validate_marking_mode_for_render(mode: MarkingMode, svg_mode: str) -> None:
    """Reject combinations whose physical semantics would otherwise be misleading."""
    if not mode.is_negative:
        return
    # ``codes + template`` is intentionally allowed as a TWO-STAGE artifact:
    # background/code relief lives in layer_background and positive text/geometry in
    # their semantic layers.  The application does not stream laser parameters, so
    # the machine software/operator must explicitly assign the secondary operation.
    # A prominent warning/metadata flag is emitted by the renderer.
    if mode.polarity_scope == "all" and svg_mode == "editable":
        raise ValueError(
            "Invertido + alcance 'todo' requiere convertir texto y trazos a geometría. "
            "No es compatible con el maestro editable; exporte Producción."
        )


# WHY: Normaliza rectángulos a paths para que campos y huecos compartan la misma semántica even-odd.
def rect_path(x: float, y: float, w: float, h: float) -> str:
    return f"M {x:.4f} {y:.4f} h {w:.4f} v {h:.4f} h {-w:.4f} z"


# WHY: Construye campo exterior + huecos como una operación geométrica declarativa sin librerías booleanas.
def negative_field_path(field_rect: tuple[float, float, float, float], hole_path: str) -> str:
    x, y, w, h = field_rect
    return f"{rect_path(x, y, w, h)} {hole_path}".strip()


def code_hole_path(rects: tuple[Rectangle, ...] | list[Rectangle], x_mm: float, y_mm: float,
                   kerf_compensation_mm: float = 0.0, compensate_y: bool = True) -> str:
    """Return protected module geometry for a negative field.

    kerf_compensation_mm is the TOTAL intended width recovery. The hole expands
    half that amount on every side; no default compensation is invented.
    """
    expanded = expand_and_union_rects(
        rects, kerf_compensation_mm, compensate_y=compensate_y
    )
    return rects_to_path_data(expanded, x_mm, y_mm)


def line_stroke_path(x1: float, y1: float, x2: float, y2: float, stroke_mm: float) -> str:
    """Convert an open line stroke into a filled four-corner polygon."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        r = stroke_mm / 2.0
        return rect_path(x1-r, y1-r, stroke_mm, stroke_mm)
    nx, ny = -dy / length, dx / length
    r = stroke_mm / 2.0
    pts = [
        (x1 + nx*r, y1 + ny*r),
        (x2 + nx*r, y2 + ny*r),
        (x2 - nx*r, y2 - ny*r),
        (x1 - nx*r, y1 - ny*r),
    ]
    return "M " + " L ".join(f"{x:.4f} {y:.4f}" for x, y in pts) + " z"


def rect_stroke_path(x: float, y: float, w: float, h: float, stroke_mm: float) -> str:
    """Return a ring path representing a stroked rectangle under even-odd fill."""
    r = stroke_mm / 2.0
    outer = rect_path(x-r, y-r, w+2*r, h+2*r)
    inner_w, inner_h = max(0.0, w-2*r), max(0.0, h-2*r)
    inner = rect_path(x+r, y+r, inner_w, inner_h) if inner_w > 0 and inner_h > 0 else ""
    return f"{outer} {inner}".strip()


# WHY: Expande el campo de ablación sin modificar la geometría canónica del código que evalúa el preflight.
def bounds_with_margin(x: float, y: float, w: float, h: float, margin: float) -> tuple[float, float, float, float]:
    m = max(0.0, float(margin or 0.0))
    return (x-m, y-m, w+2*m, h+2*m)


# WHY: Estima área de módulos para informar carga de ablación; no pretende sustituir una medición física de energía.
def area_of_rects(rects: tuple[Rectangle, ...] | list[Rectangle]) -> float:
    return sum(max(0.0, w) * max(0.0, h) for _, _, w, h in rects)
