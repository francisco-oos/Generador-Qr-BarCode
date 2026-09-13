"""Extract pure rectangle geometry from the existing code generators.

WHY:
Hasta v0.6.2 los símbolos 1D y Data Matrix se insertaban en el documento final
usando la salida SVG de ReportLab (``renderSVG.drawToString``).  Esa salida es
un ``<svg>`` anidado con ``<clipPath id="clip">``, ``<g id="group">`` y
``transform="scale(1,-1)"``.  Tres consecuencias medidas:

1. los identificadores ``clip`` y ``group`` se repetían por cada símbolo, lo que
   viola la unicidad de ``id`` exigida por XML/SVG y hace que dos símbolos con
   recortes distintos compartan el mismo ``url(#clip)``;
2. la estructura era innecesariamente compleja para edicion e interoperabilidad
   (``<svg>`` anidados, recortes y transformaciones), aunque la supuesta falla
   de CairoSVG reportada inicialmente en PRE resulto ser un falso positivo de
   medicion del canal alfa y quedo corregida/documentada;
3. las coordenadas visibles dentro del archivo no correspondían a los
   milímetros del diseñador, lo que impedía el ciclo
   «medir en Inkscape → devolver la medida al estudio».

Este módulo NO reimplementa ninguna simbología.  Toma el objeto ``Drawing`` que
ya calcula ReportLab, recorre su árbol de formas y devuelve los rectángulos
resultantes en milímetros y en el sistema de coordenadas de SVG (origen arriba
a la izquierda, Y hacia abajo).  La aritmética del código de barras permanece
exactamente donde estaba; lo único que cambia es cómo se serializa.
"""

from __future__ import annotations

from reportlab.graphics.shapes import Group, Rect, mmult
from reportlab.lib.units import mm

# WHY: Un rectángulo en milímetros relativo al origen del fragmento, con Y hacia abajo como en SVG.
Rectangle = tuple[float, float, float, float]

# WHY: Tolerancia para considerar que dos bordes coinciden; 1e-9 mm está muy por debajo
# de cualquier resolución física de grabado y evita fusiones falsas por redondeo binario.
_EPSILON = 1e-9


# WHY: Detecta transformaciones con rotación o sesgo para fallar de forma explícita
# en lugar de emitir una geometría silenciosamente incorrecta.
def _is_axis_aligned(transform) -> bool:
    _, b, c, _, _, _ = transform
    return abs(b) < 1e-12 and abs(c) < 1e-12


# WHY: Aplica una transformación afín alineada a ejes a una esquina.
def _apply(transform, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = transform
    return (a * x + c * y + e, b * x + d * y + f)


# WHY: Expande widgets a formas primitivas usando el propio ``draw()`` de ReportLab,
# de modo que la geometría emitida sea la misma que ReportLab dibujaría.
def _flatten(node, transform, sink: list[tuple[Rect, tuple]]) -> None:
    if isinstance(node, Group):
        transform = mmult(transform, node.transform)
        for child in node.contents:
            _flatten(child, transform, sink)
        return
    if isinstance(node, Rect):
        sink.append((node, transform))
        return
    contents = getattr(node, "contents", None)
    if contents is not None:
        for child in contents:
            _flatten(child, transform, sink)
        return
    draw = getattr(node, "draw", None)
    if callable(draw):
        _flatten(draw(), transform, sink)


# WHY: Convierte un Drawing de ReportLab en rectángulos milimétricos con Y hacia abajo,
# descartando el fondo sin relleno que ReportLab añade como marco del símbolo.
def rects_from_drawing(drawing, height_pt: float) -> list[Rectangle]:
    """Return filled rectangles of ``drawing`` in millimetres, SVG orientation.

    ``height_pt`` is the drawing height in points and is required to flip the
    vertical axis: ReportLab places the origin at the bottom-left and SVG at the
    top-left.  Flipping by arithmetic (instead of ``transform="scale(1,-1)"``)
    is what makes the resulting document portable across renderers.
    """
    collected: list[tuple[Rect, tuple]] = []
    _flatten(drawing, (1, 0, 0, 1, 0, 0), collected)

    out: list[Rectangle] = []
    for rect, transform in collected:
        if rect.fillColor is None:
            # ReportLab emits an unfilled frame around the symbol; it carries no ink.
            continue
        if not _is_axis_aligned(transform):
            raise ValueError("unsupported rotated/skewed transform in barcode geometry")
        x0, y0 = _apply(transform, rect.x, rect.y)
        x1, y1 = _apply(transform, rect.x + rect.width, rect.y + rect.height)
        left, right = min(x0, x1), max(x0, x1)
        bottom, top = min(y0, y1), max(y0, y1)
        out.append((
            left / mm,
            (height_pt - top) / mm,
            (right - left) / mm,
            (top - bottom) / mm,
        ))
    return out


# WHY: Fusiona módulos contiguos de una misma fila para reducir el tamaño del archivo
# y eliminar las costuras finas que algunos rasterizadores dibujan entre rectángulos
# adyacentes; la geometría resultante cubre exactamente la misma área.
def merge_horizontal_runs(rects: list[Rectangle]) -> list[Rectangle]:
    if not rects:
        return []
    ordered = sorted(rects, key=lambda r: (round(r[1], 9), round(r[3], 9), r[0]))
    merged: list[Rectangle] = []
    cur_x, cur_y, cur_w, cur_h = ordered[0]
    for x, y, w, h in ordered[1:]:
        same_row = abs(y - cur_y) < _EPSILON and abs(h - cur_h) < _EPSILON
        touching = abs(x - (cur_x + cur_w)) < _EPSILON
        if same_row and touching:
            cur_w += w
            continue
        merged.append((cur_x, cur_y, cur_w, cur_h))
        cur_x, cur_y, cur_w, cur_h = x, y, w, h
    merged.append((cur_x, cur_y, cur_w, cur_h))
    return merged


# WHY: Serializa rectángulos como un único path compuesto: un solo nodo por símbolo,
# sin recursos referenciados (``clipPath``, ``use``) que puedan colisionar entre marcas.
def rects_to_path_data(rects: list[Rectangle], origin_x_mm: float, origin_y_mm: float) -> str:
    parts: list[str] = []
    for x, y, w, h in rects:
        px = origin_x_mm + x
        py = origin_y_mm + y
        parts.append(f"M {px:.4f} {py:.4f} h {w:.4f} v {h:.4f} h {-w:.4f} z")
    return " ".join(parts)


# WHY (v0.8.0): Kerf compensation can make neighbouring protected modules overlap.
# Under one even-odd path, overlapping hole subpaths would cancel each other and
# re-fill exactly the region we intended to protect.  This helper computes the
# union of axis-aligned rectangles without adding a general boolean-geometry
# dependency.  It is intentionally limited to the geometry Marking Studio emits.
# WHY: Une rectángulos compensados antes de usarlos como huecos even-odd para evitar cancelación por solapamiento.
def union_axis_aligned_rects(rects: list[Rectangle] | tuple[Rectangle, ...]) -> list[Rectangle]:
    clean = [(float(x), float(y), float(w), float(h)) for x, y, w, h in rects if w > _EPSILON and h > _EPSILON]
    if not clean:
        return []

    ys = sorted({y for _, y, _, _ in clean} | {y + h for _, y, _, h in clean})
    bands: list[Rectangle] = []
    for y0, y1 in zip(ys, ys[1:]):
        if y1 - y0 <= _EPSILON:
            continue
        mid = (y0 + y1) / 2.0
        intervals: list[tuple[float, float]] = []
        for x, y, w, h in clean:
            if y - _EPSILON <= mid <= y + h + _EPSILON:
                intervals.append((x, x + w))
        if not intervals:
            continue
        intervals.sort()
        cur_l, cur_r = intervals[0]
        merged_intervals: list[tuple[float, float]] = []
        for left, right in intervals[1:]:
            if left <= cur_r + _EPSILON:
                cur_r = max(cur_r, right)
            else:
                merged_intervals.append((cur_l, cur_r))
                cur_l, cur_r = left, right
        merged_intervals.append((cur_l, cur_r))
        for left, right in merged_intervals:
            bands.append((left, y0, right - left, y1 - y0))

    # Merge vertically adjacent bands with the same horizontal span.
    bands.sort(key=lambda r: (round(r[0], 9), round(r[2], 9), r[1]))
    merged: list[Rectangle] = []
    for rect in bands:
        if merged:
            px, py, pw, ph = merged[-1]
            x, y, w, h = rect
            if abs(px - x) < _EPSILON and abs(pw - w) < _EPSILON and abs((py + ph) - y) < _EPSILON:
                merged[-1] = (px, py, pw, ph + h)
                continue
        merged.append(rect)
    return merged


# WHY (v0.8.0): Apply a measured kerf recovery to protected geometry and union
# the result before it becomes an even-odd hole.  For 1D barcodes the critical
# dimension is bar width, so callers can keep Y unchanged.
# WHY: Aplica la compensación de kerf medida y devuelve una unión no solapada apta para SVG even-odd.
def expand_and_union_rects(
    rects: list[Rectangle] | tuple[Rectangle, ...],
    total_compensation_mm: float,
    *,
    compensate_y: bool = True,
) -> list[Rectangle]:
    c = max(0.0, float(total_compensation_mm or 0.0)) / 2.0
    if c == 0.0:
        return union_axis_aligned_rects(rects)
    expanded: list[Rectangle] = []
    for x, y, w, h in rects:
        if compensate_y:
            expanded.append((x - c, y - c, w + 2*c, h + 2*c))
        else:
            expanded.append((x - c, y, w + 2*c, h))
    return union_axis_aligned_rects(expanded)
