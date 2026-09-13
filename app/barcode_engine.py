"""Physical-dimension barcode/2D-code primitives used by templates.

The engine returns SVG fragments whose dimensions are expressed in millimetres.
It deliberately contains no INOVA/Sercel/phone rules; those live in JSON templates.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Mapping

import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from reportlab.graphics import renderSVG
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.units import mm


@dataclass(frozen=True)
class SvgFragment:
    svg: str
    width_mm: float
    height_mm: float


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


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


def _extract_svg_root(svg: str) -> str:
    idx = svg.find("<svg")
    if idx < 0:
        raise ValueError("reportlab did not produce SVG")
    return svg[idx:]


def _nest_svg(svg: str, x_mm: float, y_mm: float, width_mm: float, height_mm: float) -> str:
    root = _extract_svg_root(svg)
    # ReportLab emits width/height on the root. Remove them before adding placement
    # attributes so the nested SVG remains valid XML (no duplicate attributes).
    m = re.match(r"<svg\b([^>]*)>", root, flags=re.S)
    if not m:
        raise ValueError("invalid SVG root")
    attrs = m.group(1)
    attrs = re.sub(r'\s(?:width|height|x|y)="[^"]*"', '', attrs)
    opening = (
        f'<svg x="{x_mm:.4f}" y="{y_mm:.4f}" '
        f'width="{width_mm:.4f}" height="{height_mm:.4f}"{attrs}>'
    )
    return opening + root[m.end():]



def reposition_fragment(fragment: SvgFragment, x_mm: float, y_mm: float) -> SvgFragment:
    """Reposition a nested SVG fragment without regenerating the barcode.

    This is important for CSV batches: barcode encoding is the expensive step, so
    centering should only rewrite placement attributes.
    """
    svg = re.sub(r'<svg\s+x="[^"]+"\s+y="[^"]+"',
                 f'<svg x="{x_mm:.4f}" y="{y_mm:.4f}"', fragment.svg, count=1)
    return SvgFragment(svg, fragment.width_mm, fragment.height_mm)

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
    return SvgFragment(_nest_svg(renderSVG.drawToString(drawing), x_mm, y_mm, width_mm, height_mm), width_mm, height_mm)


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
    return SvgFragment(_nest_svg(renderSVG.drawToString(drawing), x_mm, y_mm, width_mm, height_mm), width_mm, height_mm)


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
    # Build a single compound path from horizontal dark runs instead of one
    # <rect> per module. This avoids hairline anti-alias seams in some SVG
    # rasterizers and keeps the laser handoff compact. Adjacent dark modules in
    # the same row become one rectangle, while the QR geometry remains exact.
    commands: list[str] = []
    for r, row in enumerate(matrix):
        c = 0
        while c < size:
            if not row[c]:
                c += 1
                continue
            start = c
            while c < size and row[c]:
                c += 1
            run = c - start
            x = x_mm + start * module_mm
            y = y_mm + r * module_mm
            w = run * module_mm
            h = module_mm
            commands.append(
                f'M {x:.4f} {y:.4f} h {w:.4f} v {h:.4f} h {-w:.4f} z'
            )
    return SvgFragment(f'<path d="{" ".join(commands)}" fill="#000"/>', width_mm, width_mm)


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
    nested = _nest_svg(
        renderSVG.drawToString(drawing),
        x_mm + quiet_mm,
        y_mm + quiet_mm,
        symbol_mm,
        symbol_mm,
    )
    return SvgFragment(nested, total_mm, total_mm)


def text_fragment(value: str, x_mm: float, y_mm: float, font_size_mm: float,
                  width_mm: float | None = None, align: str = "center") -> SvgFragment:
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
        f'font-family="Arial,Helvetica,sans-serif" font-size="{font_size_mm:.4f}" '
        f'font-weight="700" fill="#000">{escaped}</text>',
        width_mm or 0,
        font_size_mm,
    )
