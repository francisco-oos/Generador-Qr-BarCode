"""Convert template text to vector outlines for the production export.

WHY:
Un ``<text>`` depende de que la maquina que abre el archivo tenga instalada la
fuente declarada.  Si no la tiene, LightBurn o Inkscape sustituyen la fuente y
el texto grabado cambia de ancho, lo que puede invadir el area del codigo o
salirse de la pieza.  Para el archivo de produccion eso es inaceptable.

Para el archivo editable ocurre lo contrario: convertir a curvas destruye la
posibilidad de corregir un caracter, que es justamente para lo que existe ese
archivo.  Por eso la conversion es una opcion por trabajo y no un comportamiento
automatico.

La fuente usada para el contorneado viene incluida en ReportLab, que ya es una
dependencia obligatoria del proyecto.  No se agrega ninguna dependencia de
fuentes nueva.  ``fontTools`` si es una dependencia declarada, con degradacion
explicita: si falta, la exportacion continua con texto y lo informa en lugar de
fallar de forma silenciosa.
"""

from __future__ import annotations

import os
from functools import lru_cache

import reportlab

# WHY: Fuentes empaquetadas con ReportLab. Bitstream Vera Sans tiene licencia
# permisiva y metricas estables, y viaja con una dependencia que ya existe.
_FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
_REGULAR = os.path.join(_FONT_DIR, "Vera.ttf")
_BOLD = os.path.join(_FONT_DIR, "VeraBd.ttf")

OUTLINE_FONT_NAME = "Bitstream Vera Sans"


# WHY: Senala que la conversion a curvas no esta disponible en este equipo,
# para que el llamador informe al usuario en vez de entregar un archivo distinto al pedido.
class OutlineUnavailable(RuntimeError):
    pass


# WHY: Cachea la fuente porque abrir el TTF por cada texto domina el tiempo de
# un lote de miles de registros; el objeto se usa en solo lectura.
@lru_cache(maxsize=4)
def _load_font(bold: bool):
    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise OutlineUnavailable("fontTools no esta instalado") from exc
    path = _BOLD if bold else _REGULAR
    if not os.path.exists(path):  # pragma: no cover - depende del entorno
        raise OutlineUnavailable(f"fuente de contorneado no encontrada: {path}")
    font = TTFont(path)
    return font


# WHY: Indica de antemano si el modo produccion podra convertir texto a curvas.
def outlines_available() -> bool:
    try:
        _load_font(True)
        return True
    except OutlineUnavailable:
        return False


# WHY: Convierte una cadena en un path SVG en milimetros absolutos del lienzo,
# replicando el mismo anclaje que usa el texto editable para que no se desplace.
def text_to_path_data(value: str, x_mm: float, baseline_y_mm: float, font_size_mm: float,
                      width_mm: float | None = None, align: str = "center",
                      bold: bool = True) -> tuple[str, float]:
    """Return ``(path_data, advance_width_mm)`` for ``value``.

    Coordinates are absolute millimetres in the template canvas, matching the
    ``<text>`` element it replaces, so switching export mode never moves the text.
    """
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen

    font = _load_font(bold)
    upem = float(font["head"].unitsPerEm)
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    hmtx = font["hmtx"]
    scale = font_size_mm / upem

    # WHY: El ancho total se necesita antes de dibujar para resolver el anclaje.
    names: list[str] = []
    advance_units = 0.0
    for ch in value:
        name = cmap.get(ord(ch)) or ".notdef"
        names.append(name)
        advance_units += hmtx[name][0] if name in hmtx.metrics else 0.0
    advance_mm = advance_units * scale

    if align == "left":
        pen_x = x_mm
    elif align == "right":
        pen_x = x_mm + (width_mm or 0) - advance_mm
    else:
        pen_x = x_mm + ((width_mm or 0) - advance_mm) / 2

    parts: list[str] = []
    for name in names:
        glyph = glyph_set[name]
        pen = SVGPathPen(glyph_set)
        # Font units are Y-up with the origin on the baseline; SVG is Y-down.
        # The negative vertical scale performs that flip arithmetically, so the
        # emitted path needs no transform attribute of its own.
        glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, pen_x, baseline_y_mm)))
        data = pen.getCommands()
        if data:
            parts.append(data)
        pen_x += (hmtx[name][0] if name in hmtx.metrics else 0.0) * scale
    return " ".join(parts), advance_mm
