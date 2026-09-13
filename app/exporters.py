from __future__ import annotations

import csv
import io
import json
import zipfile

from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg


def svg_to_png(svg: str, width_mm: float, height_mm: float, dpi: int = 600) -> bytes:
    """Rasterize our generated SVG without depending on an external browser.

    svglib parses the SVG and ReportLab/rlPyCairo renders it. Width/height are
    retained in the signature as an explicit contract with callers; the SVG
    itself carries physical mm dimensions and is the source of truth.
    """
    drawing = svg2rlg(io.BytesIO(svg.encode("utf-8")))
    if drawing is None:
        raise ValueError("No fue posible interpretar el SVG para rasterizar")
    # Guard against malformed/imported SVGs that do not match the requested
    # physical canvas. Our own generator should always be within this tolerance.
    expected_w_pt = width_mm / 25.4 * 72.0
    expected_h_pt = height_mm / 25.4 * 72.0
    if abs(float(drawing.width) - expected_w_pt) > max(1.0, expected_w_pt * 0.02):
        raise ValueError("El ancho físico del SVG no coincide con la plantilla")
    if abs(float(drawing.height) - expected_h_pt) > max(1.0, expected_h_pt * 0.02):
        raise ValueError("El alto físico del SVG no coincide con la plantilla")
    return renderPM.drawToString(drawing, fmt="PNG", dpi=dpi, bg=0xFFFFFF)


def manifest_csv_bytes(manifest: list[dict]) -> bytes:
    if not manifest:
        return b""
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(manifest[0].keys()))
    writer.writeheader()
    writer.writerows(manifest)
    return out.getvalue().encode("utf-8-sig")


def build_batch_zip(svg: str, preview_svg: str, png: bytes, manifest: list[dict], metadata: dict, raster_dpi: int = 300) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("engraving/batch.svg", svg.encode("utf-8"))
        z.writestr("preview/preview_DO_NOT_ENGRAVE.svg", preview_svg.encode("utf-8"))
        z.writestr(f"engraving/batch_{raster_dpi}dpi.png", png)
        z.writestr("manifest/manifest.csv", manifest_csv_bytes(manifest))
        z.writestr("manifest/manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
        z.writestr("manifest/job.json", json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8"))
        z.writestr(
            "README_FIRST.txt",
            (
                "SERVER OFICINA MARKING STUDIO\n"
                "1) batch.svg: recomendado para LightBurn o Sculpfun Space (vector).\n"
                f"2) batch_{raster_dpi}dpi.png: alternativa raster para LaserGRBL u otros flujos compatibles.\n"
                "3) preview/preview_DO_NOT_ENGRAVE.svg contiene la geometría de la base SOLO para revisión.\n"
                "4) batch.svg y el PNG de engraving/ contienen únicamente las marcas.\n"
                "5) Antes de grabar sobre equipo real, ejecute una prueba física en material de descarte y valide con el lector real.\n"
            ).encode("utf-8"),
        )
    return buf.getvalue()
