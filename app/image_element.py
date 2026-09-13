"""Safe image-element preparation for the visual marking studio.

WHY:
The marking studio primarily emits vector geometry.  Image elements are therefore
normalized before they enter the SVG document instead of passing arbitrary uploaded
markup or opaque external references through to LightBurn/Sculpfun Space.

Policy:
- SVG uploads are sanitised to a deliberately small vector subset and embedded as
  geometry. Scripts, external resources, ``foreignObject``, ``use``, filters and
  live text are rejected.
- PNG/JPEG uploads are converted to 1-bit engraving geometry using either a fixed
  threshold or Floyd-Steinberg dithering.  This does not claim a physical engraving
  quality; material/machine acceptance remains a workshop test.
- No network resource is ever dereferenced and no image element can contain an
  external ``href`` in the production SVG.
"""
from __future__ import annotations

import base64
import binascii
import io
import math
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from PIL import Image, ImageOps

from .code_geometry import rects_to_path_data

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_RASTER_PIXELS = 16_000_000
MAX_VECTOR_SOURCE_CHARS = 3_000_000
MAX_OUTPUT_SAMPLES = 160_000

_ALLOWED_RASTER_MIME = {"image/png", "image/jpeg"}
_ALLOWED_MIME = _ALLOWED_RASTER_MIME | {"image/svg+xml"}
_ALLOWED_SVG_TAGS = {"g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
_ALLOWED_COMMON_ATTRS = {"transform"}
_ALLOWED_ATTRS = {
    "path": {"d", "fill", "stroke", "stroke-width", "fill-rule"},
    "rect": {"x", "y", "width", "height", "rx", "ry", "fill", "stroke", "stroke-width", "fill-rule"},
    "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width", "fill-rule"},
    "ellipse": {"cx", "cy", "rx", "ry", "fill", "stroke", "stroke-width", "fill-rule"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width"},
    "polyline": {"points", "fill", "stroke", "stroke-width", "fill-rule"},
    "polygon": {"points", "fill", "stroke", "stroke-width", "fill-rule"},
    "g": set(),
}
_SAFE_TRANSFORM = re.compile(r"^[0-9eE+.,()\- a-zA-Z]+$")
_SAFE_NUMBERISH = re.compile(r"^[0-9eE+.,%\- ]+$")
_DATA_URI = re.compile(r"^data:([^;,]+);base64,(.*)$", re.I | re.S)


# WHY: Transporta geometría ya normalizada y su caja física sin conservar recursos externos.
@dataclass(frozen=True)
class PreparedImage:
    svg: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    source_kind: str
    warnings: tuple[str, ...] = ()


def decode_data_uri(data_uri: str) -> tuple[str, bytes]:
    """Decode a bounded, embedded image. External URLs are intentionally unsupported."""
    match = _DATA_URI.match((data_uri or "").strip())
    if not match:
        raise ValueError("La imagen debe estar embebida como data URI base64; no se permiten rutas o URLs externas")
    mime = match.group(1).lower().strip()
    if mime not in _ALLOWED_MIME:
        raise ValueError("Formato de imagen no soportado; use PNG, JPG/JPEG o SVG")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("La imagen base64 es inválida") from exc
    if not raw:
        raise ValueError("La imagen está vacía")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f"La imagen excede el límite de {MAX_IMAGE_BYTES // (1024*1024)} MB")
    return mime, raw


# WHY: Los SVG reales mezclan namespaces; las decisiones de seguridad se toman por nombre local.
def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _safe_attr(tag: str, key: str, value: str) -> str | None:
    """Return a safe SVG attribute, normalising engraving colours to black."""
    key = _strip_ns(key)
    if key.lower().startswith("on") or key in {"href", "xlink:href", "style", "class", "id"}:
        return None
    if key not in _ALLOWED_COMMON_ATTRS and key not in _ALLOWED_ATTRS.get(tag, set()):
        return None
    value = str(value).strip()
    if "url(" in value.lower() or "javascript:" in value.lower():
        raise ValueError("El SVG contiene referencias o código no permitido")
    if key == "transform":
        if not _SAFE_TRANSFORM.fullmatch(value) or len(value) > 300:
            raise ValueError("Transform SVG no soportado")
        return value
    if key in {"fill", "stroke"}:
        if value.lower() == "none":
            return "none"
        return "#000"
    if key == "fill-rule":
        return value if value in {"nonzero", "evenodd"} else "nonzero"
    if key == "d":
        if len(value) > 1_000_000 or any(token in value.lower() for token in ("url(", "javascript:")):
            raise ValueError("Path SVG demasiado grande o no seguro")
        return value
    if key == "points":
        if len(value) > 500_000 or not _SAFE_NUMBERISH.fullmatch(value):
            raise ValueError("Lista de puntos SVG inválida")
        return value
    if not _SAFE_NUMBERISH.fullmatch(value):
        raise ValueError(f"Atributo SVG no numérico/no soportado: {key}")
    return value


# WHY: Re-serializa únicamente el subconjunto permitido para que markup subido no atraviese al SVG productivo.
def _serialize_sanitized(node: ET.Element) -> str:
    tag = _strip_ns(node.tag)
    if tag not in _ALLOWED_SVG_TAGS:
        raise ValueError(f"Elemento SVG no permitido: {tag}")
    attrs: list[str] = []
    for key, value in node.attrib.items():
        safe = _safe_attr(tag, key, value)
        if safe is None:
            continue
        k = _strip_ns(key)
        escaped = safe.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
        attrs.append(f'{k}="{escaped}"')
    children = "".join(_serialize_sanitized(child) for child in list(node))
    # Text nodes are deliberately discarded.  Live text needs font resolution and
    # belongs in the native ``text`` element of Marking Studio, not inside uploads.
    if tag == "g":
        return f'<g{" " if attrs else ""}{" ".join(attrs)}>{children}</g>'
    if children:
        return f'<{tag}{" " if attrs else ""}{" ".join(attrs)}>{children}</{tag}>'
    return f'<{tag}{" " if attrs else ""}{" ".join(attrs)}/>'


# WHY: Tolera unidades declarativas del SVG sólo para obtener una caja numérica segura cuando no hay viewBox.
def _parse_length(value: str | None) -> float | None:
    if not value:
        return None
    m = re.match(r"^\s*([0-9.+\-eE]+)", value)
    if not m:
        return None
    try:
        number = float(m.group(1))
    except ValueError:
        return None
    return number if math.isfinite(number) and number > 0 else None


# WHY: Hace que preview y producción compartan exactamente la misma regla de ajuste/aspect ratio.
def _fit_box(src_w: float, src_h: float, x: float, y: float, w: float, h: float, preserve: bool) -> tuple[float, float, float, float]:
    if not preserve:
        return x, y, w, h
    scale = min(w / src_w, h / src_h)
    dw, dh = src_w * scale, src_h * scale
    return x + (w - dw) / 2.0, y + (h - dh) / 2.0, dw, dh


# WHY: Convierte SVG no confiable en geometría local saneada antes de incorporarlo al documento.
def prepare_svg_image(data_uri: str, x_mm: float, y_mm: float, width_mm: float, height_mm: float,
                      preserve_aspect: bool = True) -> PreparedImage:
    mime, raw = decode_data_uri(data_uri)
    if mime != "image/svg+xml":
        raise ValueError("El modo vector requiere una imagen SVG")
    if len(raw) > MAX_VECTOR_SOURCE_CHARS:
        raise ValueError("SVG demasiado grande")
    lower = raw.lower()
    if b"<!doctype" in lower or b"<!entity" in lower:
        raise ValueError("DOCTYPE/ENTITY no están permitidos en SVG subidos")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("SVG inválido") from exc
    if _strip_ns(root.tag) != "svg":
        raise ValueError("El archivo SVG debe tener un elemento raíz <svg>")

    viewbox = (root.attrib.get("viewBox") or root.attrib.get("viewbox") or "").strip().replace(",", " ").split()
    if len(viewbox) == 4:
        try:
            vx, vy, vw, vh = map(float, viewbox)
        except ValueError as exc:
            raise ValueError("viewBox SVG inválido") from exc
    else:
        vx = vy = 0.0
        vw = _parse_length(root.attrib.get("width")) or 1.0
        vh = _parse_length(root.attrib.get("height")) or 1.0
    if not (vw > 0 and vh > 0 and all(math.isfinite(v) for v in (vx, vy, vw, vh))):
        raise ValueError("Dimensiones SVG inválidas")

    supported: list[str] = []
    for child in list(root):
        tag = _strip_ns(child.tag)
        if tag in {"defs", "metadata", "title", "desc"}:
            continue
        supported.append(_serialize_sanitized(child))
    if not supported:
        raise ValueError("El SVG no contiene geometría vectorial soportada; convierta texto/efectos a paths")

    dx, dy, dw, dh = _fit_box(vw, vh, x_mm, y_mm, width_mm, height_mm, preserve_aspect)
    sx, sy = dw / vw, dh / vh
    content = "".join(supported)
    transform = f"translate({dx:.4f} {dy:.4f}) scale({sx:.8f} {sy:.8f}) translate({-vx:.4f} {-vy:.4f})"
    return PreparedImage(
        svg=f'<g transform="{transform}">{content}</g>',
        x_mm=dx, y_mm=dy, width_mm=dw, height_mm=dh, source_kind="vector-svg",
        warnings=("SVG importado sanitizado: texto, scripts, recursos externos, filtros y elementos no soportados se rechazan.",),
    )


# WHY: Acota complejidad de salida sin cambiar las dimensiones físicas en milímetros.
def _target_raster_size(width_mm: float, height_mm: float, dpi: int) -> tuple[int, int]:
    w = max(1, round(width_mm / 25.4 * dpi))
    h = max(1, round(height_mm / 25.4 * dpi))
    if w * h > MAX_OUTPUT_SAMPLES:
        scale = math.sqrt(MAX_OUTPUT_SAMPLES / (w * h))
        w = max(1, int(w * scale))
        h = max(1, int(h * scale))
    return w, h


# WHY: Convierte tonos continuos a una decisión binaria auditable en vez de delegar un raster ambiguo al láser.
def prepare_raster_image(data_uri: str, x_mm: float, y_mm: float, width_mm: float, height_mm: float,
                         processing: str = "threshold", threshold: int = 128, dpi: int = 254,
                         preserve_aspect: bool = True) -> PreparedImage:
    mime, raw = decode_data_uri(data_uri)
    if mime not in _ALLOWED_RASTER_MIME:
        raise ValueError("El procesamiento raster requiere PNG o JPG/JPEG")
    try:
        with Image.open(io.BytesIO(raw)) as im0:
            im0.load()
            if im0.width * im0.height > MAX_RASTER_PIXELS:
                raise ValueError("La imagen raster excede el límite de 16 megapíxeles")
            src_w, src_h = im0.size
            gray = ImageOps.grayscale(im0)
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("PNG/JPG inválido o no decodificable") from exc

    dx, dy, dw, dh = _fit_box(float(src_w), float(src_h), x_mm, y_mm, width_mm, height_mm, preserve_aspect)
    tw, th = _target_raster_size(dw, dh, dpi)
    gray = gray.resize((tw, th), Image.Resampling.LANCZOS)
    if processing == "floyd_steinberg":
        bw = gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
        mode_label = "Floyd-Steinberg 1-bit"
    elif processing == "threshold":
        threshold = max(0, min(255, int(threshold)))
        bw = gray.point(lambda p: 0 if p < threshold else 255, mode="1")
        mode_label = f"threshold {threshold}"
    else:
        raise ValueError("Procesamiento raster no soportado; use threshold o floyd_steinberg")

    px_w, px_h = dw / tw, dh / th
    pixels = bw.load()
    rects: list[tuple[float, float, float, float]] = []
    for row in range(th):
        col = 0
        while col < tw:
            if pixels[col, row] != 0:
                col += 1
                continue
            start = col
            while col < tw and pixels[col, row] == 0:
                col += 1
            rects.append((dx + start * px_w, dy + row * px_h, (col - start) * px_w, px_h))
    path = rects_to_path_data(rects, 0.0, 0.0)
    svg = f'<path d="{path}" fill="#000" fill-rule="nonzero"/>' if path else ""
    warnings = (
        f"Raster convertido a geometría binaria ({mode_label}, {tw}×{th} muestras). La calidad física depende de material/máquina y requiere prueba real.",
    )
    return PreparedImage(svg=svg, x_mm=dx, y_mm=dy, width_mm=dw, height_mm=dh, source_kind=f"raster-{processing}", warnings=warnings)


# WHY: Es la única puerta pública para imágenes y evita que callers elijan rutas inseguras según la extensión/nombre.
def prepare_image_element(*, data_uri: str, x_mm: float, y_mm: float, width_mm: float, height_mm: float,
                          processing: str = "auto", threshold: int = 128, dpi: int = 254,
                          preserve_aspect: bool = True) -> PreparedImage:
    mime, _ = decode_data_uri(data_uri)
    if processing == "auto":
        processing = "vector" if mime == "image/svg+xml" else "threshold"
    if processing == "vector":
        return prepare_svg_image(data_uri, x_mm, y_mm, width_mm, height_mm, preserve_aspect)
    return prepare_raster_image(data_uri, x_mm, y_mm, width_mm, height_mm, processing, threshold, dpi, preserve_aspect)
