from __future__ import annotations

import csv
import io
import json
import zipfile

from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg


# WHY: Rasteriza una marca sólo como alternativa de interoperabilidad; SVG sigue siendo la geometría autoritativa.
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


# WHY: Genera un manifiesto simple interoperable con Excel/otras herramientas y útil para revisión humana.
def manifest_csv_bytes(manifest: list[dict]) -> bytes:
    if not manifest:
        return b""
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(manifest[0].keys()))
    writer.writeheader()
    writer.writerows(manifest)
    return out.getvalue().encode("utf-8-sig")


# WHY: Empaqueta producción, preview separado y manifiestos para que una entrega de lote sea autocontenida y auditable.
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


# WHY: Empaqueta miles de SVG individuales con manifiesto sin requerir un jig físico.
def build_bulk_template_zip(items: list[dict], metadata: dict) -> bytes:
    """Package one SVG per data row plus a manifest for downstream machine software.

    ``items`` entries contain ``filename``, ``svg`` and ``data``.  The function
    never emits controller commands; it only packages portable artwork.
    """
    buf = io.BytesIO()
    manifest: list[dict] = []
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for index, item in enumerate(items, start=1):
            filename = str(item["filename"])
            z.writestr(f"svg/{filename}.svg", str(item["svg"]).encode("utf-8"))
            manifest.append({"index": index, "filename": filename, **{str(k): str(v) for k, v in item.get("data", {}).items()}})
        z.writestr("manifest/manifest.csv", manifest_csv_bytes(manifest))
        z.writestr("manifest/manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
        z.writestr("manifest/job.json", json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8"))
        z.writestr(
            "README_FIRST.txt",
            (
                "SERVER OFICINA MARKING STUDIO — EXPORTACION MASIVA\n"
                "Cada archivo de svg/ es una marca individual generada desde la misma plantilla.\n"
                "Importe los SVG en LightBurn, Sculpfun Space u otro software de máquina compatible.\n"
                "Este paquete NO contiene G-code ni controla el láser.\n"
                "Verifique Frame/origen, material, preset y lectura del código antes de producción.\n"
            ).encode("utf-8"),
        )
    return buf.getvalue()
