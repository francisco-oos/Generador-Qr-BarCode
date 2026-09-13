"""Physical-dimension barcode/2D-code primitives used by templates.

The engine returns SVG fragments whose dimensions are expressed in millimetres.
It deliberately contains no INOVA/Sercel/phone rules; those live in JSON templates.

WHY (v0.7.0):
La *generacion* de cada simbologia sigue delegada en las mismas librerias que
v0.6.2 (``reportlab.graphics.barcode`` y ``qrcode``).  Lo que cambio es la
*serializacion*: antes se incrustaba el SVG que emitia ReportLab, con ``<svg>``
anidado, ``clipPath`` compartido y ``transform="scale(1,-1)"``.  Ahora la
geometria se extrae como rectangulos milimetricos (``code_geometry``) y se emite
como un unico ``<path>`` plano en coordenadas absolutas del lienzo.

Consecuencias buscadas, todas verificadas por pruebas:
- ningun identificador generado por librerias externas entra al documento;
- ningun recurso referenciado (``url(#...)``) puede colisionar entre marcas;
- las coordenadas del archivo coinciden con los milimetros del disenador;
- el mismo archivo se comporta igual en svglib, CairoSVG e Inkscape.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Mapping

import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.units import mm

from .code_geometry import Rectangle, expand_and_union_rects, merge_horizontal_runs, rects_from_drawing, rects_to_path_data


# WHY: Resultado geometrico reutilizable con SVG interno y dimensiones fisicas explicitas.
# ``rects`` guarda la geometria relativa al origen del fragmento para poder reposicionar
# un simbolo sin volver a codificarlo, que es el paso costoso en lotes grandes.
@dataclass(frozen=True)
class SvgFragment:
    svg: str
    width_mm: float
    height_mm: float
    rects: tuple[Rectangle, ...] = field(default=())


# WHY: Permite formatear literales con campos ausentes sin romper todo el render durante diseno/preview.
class SafeFormatDict(dict):
    # WHY: Conserva el marcador faltante para hacerlo visible al disenador en lugar de perder silenciosamente informacion.
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


# WHY: Resuelve la fuente de un elemento desde datos o literal y aplica formato seguro de variables.
def resolve_value(data: Mapping[str, str], source: str | None, literal: str | None = None) -> str:
    if literal is not None:
        return literal.format_map(SafeFormatDict({k: str(v) for k, v in data.items()}))
    if not source:
        return ""
    # A source can define fallbacks: manufacturer_id|asset_id
    for candidate in source.split("|"):
        candidate = candidate.strip()
        value = data.get(candidate)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


# WHY: Punto unico de serializacion de cualquier simbolo; garantiza que todos los
# generadores produzcan la misma clase de nodo SVG y evita divergencias por simbologia.
def _fragment_from_rects(rects: list[Rectangle], x_mm: float, y_mm: float,
                         width_mm: float, height_mm: float) -> SvgFragment:
    merged = merge_horizontal_runs(rects)
    path = rects_to_path_data(merged, x_mm, y_mm)
    svg = f'<path d="{path}" fill="#000" fill-rule="nonzero"/>' if path else ""
    return SvgFragment(svg, width_mm, height_mm, tuple(merged))


# WHY: Genera el complemento vectorial del simbolo dentro de su propia
# caja fisica. El laser llena el fondo/espacios y deja barras o modulos como
# "islas" sin grabar. Esto habilita un flujo de relieve donde, tras grabar, se
# puede frotar marcador/pintura sobre la superficie elevada para recuperar una
# polaridad optica normal. La funcion NO afirma que el SVG negativo sea legible
# directamente por cualquier lector; esa aceptacion sigue siendo fisica.
# WHY: El complemento se aplica despues de generar la simbologia; no altera el dato codificado.
def _expanded_rects(rects: tuple[Rectangle, ...] | list[Rectangle], total_compensation_mm: float, compensate_y: bool = True) -> list[Rectangle]:
    """Expand and union protected modules before using them as even-odd holes.

    WHY: adjacent QR/Data Matrix modules can touch.  Expanding each rectangle and
    writing all of them directly into one even-odd path would make overlaps flip
    parity and re-fill protected regions.  The axis-aligned union keeps the
    intended physical semantics without a general boolean-geometry dependency.
    """
    return expand_and_union_rects(rects, total_compensation_mm, compensate_y=compensate_y)


def negative_background_fragment(
    fragment: SvgFragment, x_mm: float, y_mm: float,
    field_margin_mm: float = 0.0, kerf_compensation_mm: float = 0.0,
    kerf_compensate_y: bool = True,
) -> SvgFragment:
    """Return the geometric complement used for relief/background ablation.

    The symbol encoder is untouched: the outer field is filled and the canonical
    positive modules become holes using ``fill-rule=evenodd``.  A positive margin
    grows only the sacrificial field; kerf compensation grows only the protected
    module holes.
    """
    if not fragment.rects:
        return fragment
    margin = max(0.0, float(field_margin_mm or 0.0))
    fx, fy = x_mm - margin, y_mm - margin
    fw, fh = fragment.width_mm + 2*margin, fragment.height_mm + 2*margin
    outer = f"M {fx:.4f} {fy:.4f} h {fw:.4f} v {fh:.4f} h {-fw:.4f} z"
    protected = _expanded_rects(fragment.rects, kerf_compensation_mm, compensate_y=kerf_compensate_y)
    # WHY: Un hueco compensado que sale del campo even-odd deja de ser un hueco y puede
    # crear tinta/ablación fuera del rectángulo. Se rechaza antes de producir arte engañoso.
    eps = 1e-6
    for rx, ry, rw, rh in protected:
        if rx < -margin - eps or ry < -margin - eps or rx + rw > fragment.width_mm + margin + eps or ry + rh > fragment.height_mm + margin + eps:
            raise ValueError("kerf_compensation_mm demasiado grande para el campo/quiet zone del símbolo; aumente field_margin_mm o reduzca la compensación")
    holes = rects_to_path_data(protected, x_mm, y_mm)
    path = f"{outer} {holes}".strip()
    return SvgFragment(
        f'<path d="{path}" fill="#000" fill-rule="evenodd"/>',
        fw, fh, fragment.rects,
    )

# WHY: Reposiciona un fragmento ya generado; se usa para alinear elementos sin regenerar la simbologia.
def reposition_fragment(fragment: SvgFragment, x_mm: float, y_mm: float) -> SvgFragment:
    """Reposition a fragment without re-encoding the symbol.

    Barcode encoding is the expensive step in CSV batches, so alignment only
    re-serializes the stored millimetre geometry at a new origin.
    """
    if not fragment.rects:
        return fragment
    path = rects_to_path_data(list(fragment.rects), x_mm, y_mm)
    return SvgFragment(
        f'<path d="{path}" fill="#000" fill-rule="nonzero"/>',
        fragment.width_mm,
        fragment.height_mm,
        fragment.rects,
    )


# WHY: Genera Code 128 vectorial porque es el estandar inicial de nodos y mantiene lectura por escaner mas texto visible.
def code128_fragment(value: str, x_mm: float, y_mm: float, module_mm: float,
                     bar_height_mm: float, quiet_modules: int = 10) -> SvgFragment:
    if not value:
        raise ValueError("Code 128 value is empty")
    quiet_mm = max(module_mm * quiet_modules, 2.0)
    drawing = createBarcodeDrawing(
        "Code128",
        value=value,
        barWidth=module_mm * mm,
        barHeight=bar_height_mm * mm,
        humanReadable=False,
        quiet=True,
        lquiet=quiet_mm * mm,
        rquiet=quiet_mm * mm,
    )
    width_mm = float(drawing.width / mm)
    height_mm = float(drawing.height / mm)
    rects = rects_from_drawing(drawing, float(drawing.height))
    return _fragment_from_rects(rects, x_mm, y_mm, width_mm, height_mm)


# WHY: Ofrece Code 39 para equipos/procesos heredados sin introducir logica especifica en el disenador.
def code39_fragment(value: str, x_mm: float, y_mm: float, module_mm: float,
                    bar_height_mm: float, quiet_modules: int = 10) -> SvgFragment:
    if not value:
        raise ValueError("Code 39 value is empty")
    quiet_mm = max(module_mm * quiet_modules, 2.0)
    drawing = createBarcodeDrawing(
        "Standard39",
        value=value,
        barWidth=module_mm * mm,
        barHeight=bar_height_mm * mm,
        humanReadable=False,
        quiet=True,
        lquiet=quiet_mm * mm,
        rquiet=quiet_mm * mm,
    )
    width_mm = float(drawing.width / mm)
    height_mm = float(drawing.height / mm)
    rects = rects_from_drawing(drawing, float(drawing.height))
    return _fragment_from_rects(rects, x_mm, y_mm, width_mm, height_mm)


# WHY: Genera QR vectorial con tamano de modulo fisico, apropiado para activos leidos con camaras o lectores 2D.
def qr_fragment(value: str, x_mm: float, y_mm: float, module_mm: float,
                quiet_modules: int = 4, error_correction: str = "M") -> SvgFragment:
    if not value:
        raise ValueError("QR value is empty")
    ec = {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }[error_correction]
    qr = qrcode.QRCode(version=None, error_correction=ec, box_size=1, border=quiet_modules)
    qr.add_data(value)
    qr.make(fit=True)
    matrix = qr.get_matrix()  # Includes border requested above.
    size = len(matrix)
    width_mm = size * module_mm
    rects: list[Rectangle] = []
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if dark:
                rects.append((c * module_mm, r * module_mm, module_mm, module_mm))
    return _fragment_from_rects(rects, x_mm, y_mm, width_mm, width_mm)


# WHY: Genera Data Matrix compacto para piezas donde un QR resulte demasiado grande.
def datamatrix_fragment(value: str, x_mm: float, y_mm: float, module_mm: float,
                        quiet_modules: int = 1) -> SvgFragment:
    if not value:
        raise ValueError("Data Matrix value is empty")
    # ReportLab's ECC200 implementation currently emits a fixed 44x44 symbol.
    # We preserve module geometry by scaling it to module_mm and add a DPM quiet zone.
    drawing = createBarcodeDrawing("ECC200DataMatrix", value=value)
    symbol_modules = 44
    symbol_mm = symbol_modules * module_mm
    quiet_mm = quiet_modules * module_mm
    total_mm = symbol_mm + 2 * quiet_mm
    # WHY: El Drawing viene en unidades propias; se escala al modulo fisico pedido
    # mediante aritmetica sobre la geometria, no mediante un transform en el archivo.
    native = rects_from_drawing(drawing, float(drawing.height))
    native_w = float(drawing.width / mm)
    scale = symbol_mm / native_w if native_w else 1.0
    scaled = [(x * scale + quiet_mm, y * scale + quiet_mm, w * scale, h * scale)
              for x, y, w, h in native]
    return _fragment_from_rects(scaled, x_mm, y_mm, total_mm, total_mm)


# WHY: Genera texto vectorial posicionado en milimetros para conservar inspeccion visual junto al codigo.
def text_fragment(value: str, x_mm: float, y_mm: float, font_size_mm: float,
                  width_mm: float | None = None, align: str = "center",
                  font_family: str = "Arial,Helvetica,sans-serif",
                  font_weight: str = "700") -> SvgFragment:
    if align == "left":
        anchor = "start"
        x = x_mm
    elif align == "right":
        anchor = "end"
        x = x_mm + (width_mm or 0)
    else:
        anchor = "middle"
        x = x_mm + (width_mm or 0) / 2
    # SVG text stays vector-aware in LightBurn; raster exports flatten it for LaserGRBL.
    escaped = html.escape(value)
    return SvgFragment(
        f'<text x="{x:.4f}" y="{y_mm:.4f}" text-anchor="{anchor}" '
        f'font-family="{font_family}" font-size="{font_size_mm:.4f}" '
        f'font-weight="{font_weight}" fill="#000">{escaped}</text>',
        width_mm or 0,
        font_size_mm,
    )
