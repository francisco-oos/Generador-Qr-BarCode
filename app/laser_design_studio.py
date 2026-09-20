"""Experimental laser-design engines for Marking Studio v0.9.

This module deliberately stays on the *document-generation* side of the system.
It never emits G-code, motion, power, or machine commands.  It turns design
intent into bounded 2D geometry in millimetres, performs manufacturability
checks, and serialises SVG for hand-off to established laser software.

The first engines are intentionally complementary:
- papel picado: parametric, reproducible cut patterns;
- halftone: raster image -> perforation field;
- stencil: raster image -> cut regions with automatic material bridges;
- OpenAI Lab: physical survival analysis + calibration coupon generation.

The architecture is provider-friendly: future vectorisers (for example VTracer)
or nesting engines can plug in without changing the API contract or UI model.
"""
from __future__ import annotations

import base64
import io
import json
import hashlib
import math
import random
from dataclasses import dataclass
from html import escape
from typing import Any, Literal

from PIL import Image, ImageOps
from pydantic import BaseModel, Field, field_validator, model_validator
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree


MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_STENCIL_GRID = 180
MAX_HALFTONE_HOLES = 4000
MAX_PREFLIGHT_GEOMETRIES = 5000

Motif = Literal["diamond", "circle", "hex", "star", "heart"]
HalftoneShape = Literal["circle", "diamond", "hex"]


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
class PapercutRequest(BaseModel):
    width_mm: float = Field(default=180.0, ge=40.0, le=1200.0)
    height_mm: float = Field(default=260.0, ge=40.0, le=1200.0)
    margin_mm: float = Field(default=8.0, ge=1.0, le=100.0)
    rows: int = Field(default=8, ge=2, le=40)
    cols: int = Field(default=6, ge=2, le=40)
    density: float = Field(default=0.66, ge=0.15, le=0.90)
    motif: Motif = "diamond"
    symmetry: Literal["grid", "mirror"] = "mirror"
    seed: int = Field(default=1, ge=0, le=2_147_483_647)
    min_bridge_mm: float = Field(default=1.5, ge=0.2, le=25.0)
    cut_outer: bool = True

    # WHY: Mantiene explícita la razón de cada contrato para que geometría, validación y seguridad sean auditables.
    @model_validator(mode="after")
    def dimensions_make_sense(self) -> "PapercutRequest":
        if self.margin_mm * 2 >= min(self.width_mm, self.height_mm):
            raise ValueError("El margen consume todo el diseño")
        return self


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
class HalftoneRequest(BaseModel):
    image_data_uri: str = Field(min_length=32, max_length=6_500_000)
    width_mm: float = Field(default=160.0, ge=20.0, le=1000.0)
    height_mm: float = Field(default=220.0, ge=20.0, le=1000.0)
    margin_mm: float = Field(default=5.0, ge=0.5, le=80.0)
    cell_mm: float = Field(default=4.0, ge=0.5, le=30.0)
    min_diameter_mm: float = Field(default=0.6, ge=0.1, le=20.0)
    max_diameter_mm: float = Field(default=3.0, ge=0.2, le=30.0)
    min_bridge_mm: float = Field(default=0.8, ge=0.1, le=20.0)
    gamma: float = Field(default=1.0, ge=0.2, le=5.0)
    invert: bool = False
    shape: HalftoneShape = "circle"
    cut_outer: bool = True

    # WHY: Mantiene explícita la razón de cada contrato para que geometría, validación y seguridad sean auditables.
    @model_validator(mode="after")
    def geometry_is_possible(self) -> "HalftoneRequest":
        if self.margin_mm * 2 >= min(self.width_mm, self.height_mm):
            raise ValueError("El margen consume todo el diseño")
        if self.min_diameter_mm > self.max_diameter_mm:
            raise ValueError("min_diameter_mm no puede superar max_diameter_mm")
        return self


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
class StencilRequest(BaseModel):
    image_data_uri: str = Field(min_length=32, max_length=6_500_000)
    width_mm: float = Field(default=160.0, ge=20.0, le=1000.0)
    height_mm: float = Field(default=220.0, ge=20.0, le=1000.0)
    threshold: int = Field(default=140, ge=0, le=255)
    invert: bool = False
    frame_mm: float = Field(default=4.0, ge=0.5, le=50.0)
    bridge_width_mm: float = Field(default=1.8, ge=0.2, le=25.0)
    sample_max_px: int = Field(default=120, ge=32, le=MAX_STENCIL_GRID)
    max_auto_bridges: int = Field(default=40, ge=0, le=200)
    min_bridge_mm: float = Field(default=1.0, ge=0.1, le=20.0)
    cut_outer: bool = True

    # WHY: Mantiene explícita la razón de cada contrato para que geometría, validación y seguridad sean auditables.
    @model_validator(mode="after")
    def frame_is_possible(self) -> "StencilRequest":
        if self.frame_mm * 2 >= min(self.width_mm, self.height_mm):
            raise ValueError("El marco consume todo el diseño")
        return self


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
class BridgeCouponRequest(BaseModel):
    widths_mm: list[float] = Field(default_factory=lambda: [0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0])
    length_mm: float = Field(default=24.0, ge=8.0, le=100.0)
    gap_mm: float = Field(default=4.0, ge=1.0, le=30.0)
    label: bool = True

    # WHY: Mantiene explícita la razón de cada contrato para que geometría, validación y seguridad sean auditables.
    @field_validator("widths_mm")
    @classmethod
    def widths_valid(cls, value: list[float]) -> list[float]:
        if not value or len(value) > 30:
            raise ValueError("Use entre 1 y 30 anchos")
        out = [round(float(v), 3) for v in value]
        if any(v < 0.2 or v > 20 for v in out):
            raise ValueError("Cada ancho debe estar entre 0.2 y 20 mm")
        return out


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
class MaterialPassportRequest(BaseModel):
    """Sacrificial proof sheet used to measure physical geometry limits.

    The sheet intentionally spans features that may fail. It records no laser
    power/speed and does not call the machine; the operator uses an already
    established process and records which features survive.
    """
    bridge_widths_mm: list[float] = Field(default_factory=lambda: [0.5, 0.7, 0.9, 1.2, 1.5, 2.0, 2.5])
    hole_diameters_mm: list[float] = Field(default_factory=lambda: [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0])
    gap_widths_mm: list[float] = Field(default_factory=lambda: [0.5, 0.7, 0.9, 1.2, 1.5, 2.0, 2.5])
    row_height_mm: float = Field(default=10.0, ge=6.0, le=30.0)
    feature_length_mm: float = Field(default=22.0, ge=8.0, le=60.0)

    # WHY: Mantiene explícita la razón de cada contrato para que geometría, validación y seguridad sean auditables.
    @field_validator("bridge_widths_mm", "hole_diameters_mm", "gap_widths_mm")
    @classmethod
    def passport_values_valid(cls, value: list[float]) -> list[float]:
        if not value or len(value) > 20:
            raise ValueError("Cada serie debe contener entre 1 y 20 medidas")
        values = [round(float(v), 3) for v in value]
        if any(v < 0.2 or v > 30 for v in values):
            raise ValueError("Las medidas del pasaporte deben estar entre 0.2 y 30 mm")
        return values


# WHY: Mantiene explícita la razón de cada contrato para que geometría, validación y seguridad sean auditables.
@dataclass(frozen=True)
class CutArtifact:
    outer: Polygon
    cutouts: tuple[Polygon, ...]
    width_mm: float
    height_mm: float
    kind: str
    recipe: dict[str, Any]
    guides: tuple[Polygon, ...] = ()
    warnings: tuple[str, ...] = ()


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _decode_raster(data_uri: str) -> Image.Image:
    prefix = "base64,"
    if prefix not in data_uri:
        raise ValueError("La imagen debe venir embebida como data URI base64")
    head, payload = data_uri.split(prefix, 1)
    if "image/png" not in head.lower() and "image/jpeg" not in head.lower() and "image/jpg" not in head.lower():
        raise ValueError("Para esta herramienta use PNG o JPG/JPEG")
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise ValueError("La imagen base64 es inválida") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("La imagen está vacía o excede 4 MB")
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            return ImageOps.exif_transpose(im).convert("L")
    except OSError as exc:
        raise ValueError("PNG/JPG no decodificable") from exc


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _polygon_path(poly: Polygon) -> str:
    def ring_path(coords: Any) -> str:
        pts = list(coords)
        if not pts:
            return ""
        commands = [f"M {pts[0][0]:.4f} {pts[0][1]:.4f}"]
        commands.extend(f"L {x:.4f} {y:.4f}" for x, y in pts[1:])
        commands.append("Z")
        return " ".join(commands)

    parts = [ring_path(poly.exterior.coords)]
    parts.extend(ring_path(r.coords) for r in poly.interiors)
    return " ".join(p for p in parts if p)


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _geometry_paths(geom: Polygon | MultiPolygon) -> list[str]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [_polygon_path(geom)]
    return [_polygon_path(p) for p in geom.geoms if isinstance(p, Polygon) and not p.is_empty]


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _motif_geometry(kind: Motif, cx: float, cy: float, radius: float) -> Polygon:
    if kind == "circle":
        return Point(cx, cy).buffer(radius, quad_segs=14)
    if kind == "diamond":
        return Polygon([(cx, cy-radius), (cx+radius, cy), (cx, cy+radius), (cx-radius, cy)])
    if kind == "hex":
        return Polygon([(cx + math.cos(math.radians(a))*radius, cy + math.sin(math.radians(a))*radius) for a in range(0, 360, 60)])
    if kind == "star":
        pts = []
        for i in range(10):
            a = math.radians(-90 + i*36)
            r = radius if i % 2 == 0 else radius * 0.43
            pts.append((cx + math.cos(a)*r, cy + math.sin(a)*r))
        return Polygon(pts)
    # Heart = two lobes + tapered lower body, then clean union.
    l = Point(cx-radius*0.35, cy-radius*0.18).buffer(radius*0.48, quad_segs=10)
    r = Point(cx+radius*0.35, cy-radius*0.18).buffer(radius*0.48, quad_segs=10)
    tri = Polygon([(cx-radius*0.78, cy), (cx+radius*0.78, cy), (cx, cy+radius)])
    return unary_union([l, r, tri]).buffer(0)


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _halftone_shape(kind: HalftoneShape, cx: float, cy: float, diameter: float) -> Polygon:
    r = diameter / 2.0
    if kind == "circle":
        return Point(cx, cy).buffer(r, quad_segs=10)
    if kind == "diamond":
        return Polygon([(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)])
    return Polygon([(cx + math.cos(math.radians(a))*r, cy + math.sin(math.radians(a))*r) for a in range(0, 360, 60)])


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _nearest_web_width(outer: Polygon, cutouts: list[Polygon]) -> tuple[float | None, list[dict[str, Any]]]:
    if not cutouts:
        return None, []
    hotspots: list[dict[str, Any]] = []
    minimum = math.inf
    boundary = outer.exterior
    for i, g in enumerate(cutouts):
        d = float(g.distance(boundary))
        minimum = min(minimum, d)
        hotspots.append({"kind": "edge", "index": i, "distance_mm": round(d, 4)})
    if len(cutouts) > 1:
        tree = STRtree(cutouts)
        for i, g in enumerate(cutouts):
            try:
                idx, dist = tree.query_nearest(g, exclusive=True, return_distance=True)
            except TypeError:
                continue
            if len(dist):
                d = float(min(dist))
                minimum = min(minimum, d)
                hotspots.append({"kind": "between_cutouts", "index": i, "distance_mm": round(d, 4)})
    hotspots.sort(key=lambda x: x["distance_mm"])
    return (None if math.isinf(minimum) else minimum), hotspots[:12]


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def analyze_artifact(artifact: CutArtifact, min_bridge_mm: float) -> dict[str, Any]:
    cutouts = [g for g in artifact.cutouts if not g.is_empty and g.area > 1e-8]
    if len(cutouts) > MAX_PREFLIGHT_GEOMETRIES:
        raise ValueError("Demasiadas geometrías para preflight")
    union = unary_union(cutouts) if cutouts else Polygon()
    remaining = artifact.outer.difference(union)
    if isinstance(remaining, Polygon):
        components = 1 if not remaining.is_empty else 0
    elif isinstance(remaining, MultiPolygon):
        components = len(remaining.geoms)
    else:
        components = 0
    web, hotspots = _nearest_web_width(artifact.outer, cutouts)
    area_ratio = 0.0 if artifact.outer.area <= 0 else min(1.0, max(0.0, union.intersection(artifact.outer).area / artifact.outer.area))
    safe_scale = None
    if web and web > 0:
        safe_scale = max(100.0, (min_bridge_mm / web) * 100.0)
    status = "PASS"
    issues: list[str] = []
    if components != 1:
        status = "FAIL"
        issues.append(f"El material restante queda en {components} componentes; debe ser una sola pieza")
    if web is not None and web < min_bridge_mm:
        status = "FAIL" if web < min_bridge_mm * 0.65 else "WARN"
        issues.append(f"Puente/espacio mínimo estimado {web:.2f} mm < objetivo {min_bridge_mm:.2f} mm")
    if area_ratio > 0.72:
        if status == "PASS":
            status = "WARN"
        issues.append("Se elimina más del 72 % del área; la pieza puede quedar frágil")
    return {
        "status": status,
        "component_count": components,
        "cutout_count": len(cutouts),
        "removed_area_ratio": round(area_ratio, 4),
        "min_web_mm": None if web is None else round(web, 4),
        "target_min_bridge_mm": round(min_bridge_mm, 4),
        "minimum_safe_scale_percent": None if safe_scale is None else round(safe_scale, 1),
        "hotspots": hotspots,
        "issues": issues,
    }


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def artifact_svg(artifact: CutArtifact, *, preview: bool = False) -> str:
    meta = {
        "generator": "Marking Studio Laser Design Studio v0.9",
        "kind": artifact.kind,
        "units": "mm",
        "machine_control": False,
        "recipe": artifact.recipe,
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{artifact.width_mm:.4f}mm" height="{artifact.height_mm:.4f}mm" viewBox="0 0 {artifact.width_mm:.4f} {artifact.height_mm:.4f}">',
        f"<metadata>{escape(json.dumps(meta, ensure_ascii=False, sort_keys=True))}</metadata>",
        '<g id="layer_cut" data-operation="cut" fill="none" stroke="#000" stroke-width="0.10" vector-effect="non-scaling-stroke">',
    ]
    if artifact.recipe.get("cut_outer", True):
        parts.append(f'<path id="outer_cut" d="{_polygon_path(artifact.outer)}"/>')
    for i, g in enumerate(artifact.cutouts):
        for j, d in enumerate(_geometry_paths(g)):
            parts.append(f'<path id="cutout_{i:04d}_{j}" d="{d}"/>')
    parts.append("</g>")
    if preview and artifact.guides:
        parts.append('<g id="layer_guides" data-operation="guide" fill="none" stroke="#1f6feb" stroke-width="0.20" stroke-dasharray="1 1">')
        for i, g in enumerate(artifact.guides):
            for d in _geometry_paths(g):
                parts.append(f'<path id="guide_bridge_{i:03d}" d="{d}"/>')
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def artifact_response(artifact: CutArtifact, min_bridge_mm: float) -> dict[str, Any]:
    preflight = analyze_artifact(artifact, min_bridge_mm)
    warnings = list(artifact.warnings)
    warnings.extend(preflight["issues"])
    return {
        "kind": artifact.kind,
        "width_mm": artifact.width_mm,
        "height_mm": artifact.height_mm,
        "svg": artifact_svg(artifact, preview=False),
        "preview_svg": artifact_svg(artifact, preview=True),
        "recipe": artifact.recipe,
        "preflight": preflight,
        "warnings": warnings,
        "operation_layers": ["cut"] + (["guide"] if artifact.guides else []),
        "machine_control": False,
    }


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def generate_papercut(req: PapercutRequest) -> dict[str, Any]:
    outer = box(0, 0, req.width_mm, req.height_mm)
    rng = random.Random(req.seed)
    inner_w = req.width_mm - 2 * req.margin_mm
    inner_h = req.height_mm - 2 * req.margin_mm
    cell_w = inner_w / req.cols
    cell_h = inner_h / req.rows
    max_radius = max(0.1, min(cell_w, cell_h) * req.density * 0.42)
    # Preserve a deliberate web between neighbouring cells. This is a design-time
    # guard, not a substitute for preflight after geometry is generated.
    max_radius = min(max_radius, max(0.1, (min(cell_w, cell_h) - req.min_bridge_mm) / 2.0))
    cutouts: list[Polygon] = []
    half_cols = (req.cols + 1) // 2 if req.symmetry == "mirror" else req.cols
    for row in range(req.rows):
        for col in range(half_cols):
            cx = req.margin_mm + (col + 0.5) * cell_w
            cy = req.margin_mm + (row + 0.5) * cell_h
            radius = max_radius * rng.uniform(0.70, 1.0)
            g = _motif_geometry(req.motif, cx, cy, radius)
            # Alternate angle so the pattern is less mechanically repetitive while
            # still exactly reproducible from the seed.
            g = affinity.rotate(g, (row + col) % 2 * 45.0, origin=(cx, cy))
            if outer.contains(g):
                cutouts.append(g)
            if req.symmetry == "mirror":
                mirror_col = req.cols - 1 - col
                if mirror_col != col:
                    mcx = req.margin_mm + (mirror_col + 0.5) * cell_w
                    mirrored = affinity.scale(g, xfact=-1, yfact=1, origin=(req.width_mm / 2.0, req.height_mm / 2.0))
                    # Numeric symmetry around the page centre can drift from the exact
                    # mirrored cell centre if cols are even, so translate to the target.
                    dx = mcx - mirrored.centroid.x
                    mirrored = affinity.translate(mirrored, xoff=dx, yoff=0)
                    if outer.contains(mirrored):
                        cutouts.append(mirrored)
    recipe = req.model_dump()
    recipe.update({"engine": "papercut-parametric", "design_genome": f"papercut:{req.seed}:{req.rows}x{req.cols}:{req.motif}:{req.symmetry}"})
    artifact = CutArtifact(outer=outer, cutouts=tuple(cutouts), width_mm=req.width_mm, height_mm=req.height_mm, kind="papercut", recipe=recipe)
    return artifact_response(artifact, req.min_bridge_mm)


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _fit_image_cover(gray: Image.Image, cols: int, rows: int) -> Image.Image:
    # Fit rather than stretch: crop the centre after preserving source aspect ratio.
    target_ratio = cols / rows
    src_ratio = gray.width / gray.height
    if src_ratio > target_ratio:
        new_w = max(1, round(gray.height * target_ratio))
        left = max(0, (gray.width - new_w) // 2)
        gray = gray.crop((left, 0, left + new_w, gray.height))
    elif src_ratio < target_ratio:
        new_h = max(1, round(gray.width / target_ratio))
        top = max(0, (gray.height - new_h) // 2)
        gray = gray.crop((0, top, gray.width, top + new_h))
    return gray.resize((cols, rows), Image.Resampling.LANCZOS)


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def generate_halftone(req: HalftoneRequest) -> dict[str, Any]:
    gray = _decode_raster(req.image_data_uri)
    inner_w = req.width_mm - 2 * req.margin_mm
    inner_h = req.height_mm - 2 * req.margin_mm
    cols = max(1, int(inner_w // req.cell_mm))
    rows = max(1, int(inner_h // req.cell_mm))
    if cols * rows > MAX_HALFTONE_HOLES:
        scale = math.sqrt((cols * rows) / MAX_HALFTONE_HOLES)
        cols = max(1, int(cols / scale))
        rows = max(1, int(rows / scale))
    cell_w = inner_w / cols
    cell_h = inner_h / rows
    physical_cell = min(cell_w, cell_h)
    allowed_max = max(req.min_diameter_mm, physical_cell - req.min_bridge_mm)
    effective_max = min(req.max_diameter_mm, allowed_max)
    sampled = _fit_image_cover(gray, cols, rows)
    pix = sampled.load()
    outer = box(0, 0, req.width_mm, req.height_mm)
    cutouts: list[Polygon] = []
    for y in range(rows):
        for x in range(cols):
            darkness = 1.0 - (pix[x, y] / 255.0)
            if req.invert:
                darkness = 1.0 - darkness
            strength = max(0.0, min(1.0, darkness)) ** req.gamma
            diameter = req.min_diameter_mm + (effective_max - req.min_diameter_mm) * strength
            if diameter <= req.min_diameter_mm * 1.02 and strength < 0.05:
                continue
            cx = req.margin_mm + (x + 0.5) * cell_w
            cy = req.margin_mm + (y + 0.5) * cell_h
            cutouts.append(_halftone_shape(req.shape, cx, cy, diameter))
    warnings: list[str] = []
    if effective_max < req.max_diameter_mm:
        warnings.append(f"Diámetro máximo limitado automáticamente a {effective_max:.2f} mm para conservar ≥ {req.min_bridge_mm:.2f} mm entre celdas")
    recipe = req.model_dump(exclude={"image_data_uri"})
    recipe.update({"engine": "halftone-cut", "source": "embedded-raster", "effective_max_diameter_mm": round(effective_max, 4), "grid": [cols, rows]})
    artifact = CutArtifact(outer=outer, cutouts=tuple(cutouts), width_mm=req.width_mm, height_mm=req.height_mm, kind="halftone", recipe=recipe, warnings=tuple(warnings))
    return artifact_response(artifact, req.min_bridge_mm)


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _components(mask: list[list[bool]], value: bool) -> list[list[tuple[int, int]]]:
    rows = len(mask)
    cols = len(mask[0]) if rows else 0
    seen = [[False] * cols for _ in range(rows)]
    out: list[list[tuple[int, int]]] = []
    for y in range(rows):
        for x in range(cols):
            if seen[y][x] or mask[y][x] != value:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            comp: list[tuple[int, int]] = []
            while stack:
                px, py = stack.pop()
                comp.append((px, py))
                for nx, ny in ((px-1, py), (px+1, py), (px, py-1), (px, py+1)):
                    if 0 <= nx < cols and 0 <= ny < rows and not seen[ny][nx] and mask[ny][nx] == value:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            out.append(comp)
    return out


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _force_frame(material: list[list[bool]], frame_x: int, frame_y: int) -> None:
    rows = len(material); cols = len(material[0])
    for y in range(rows):
        for x in range(cols):
            if x < frame_x or x >= cols-frame_x or y < frame_y or y >= rows-frame_y:
                material[y][x] = True


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _bridge_to_frame(material: list[list[bool]], comp: list[tuple[int, int]], width_px: int) -> tuple[int, int, int, int]:
    rows = len(material); cols = len(material[0])
    # Choose the component pixel with the globally shortest cardinal route to the frame.
    best = None
    for x, y in comp:
        candidates = [(x, "left"), (cols-1-x, "right"), (y, "top"), (rows-1-y, "bottom")]
        dist, side = min(candidates, key=lambda z: z[0])
        if best is None or dist < best[0]:
            best = (dist, side, x, y)
    assert best is not None
    _, side, x, y = best
    half = max(0, width_px // 2)
    if side in {"left", "right"}:
        y0, y1 = max(0, y-half), min(rows, y+half+1)
        x0, x1 = (0, x+1) if side == "left" else (x, cols)
    else:
        x0, x1 = max(0, x-half), min(cols, x+half+1)
        y0, y1 = (0, y+1) if side == "top" else (y, rows)
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            material[yy][xx] = True
    return x0, y0, x1, y1


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _mask_to_polygons(cut_mask: list[list[bool]], width_mm: float, height_mm: float) -> list[Polygon]:
    rows = len(cut_mask); cols = len(cut_mask[0]) if rows else 0
    sx = width_mm / cols; sy = height_mm / rows
    runs: list[Polygon] = []
    for y, row in enumerate(cut_mask):
        x = 0
        while x < cols:
            if not row[x]:
                x += 1; continue
            start = x
            while x < cols and row[x]:
                x += 1
            runs.append(box(start*sx, y*sy, x*sx, (y+1)*sy))
    if not runs:
        return []
    merged = unary_union(runs)
    if isinstance(merged, Polygon):
        return [merged]
    if isinstance(merged, MultiPolygon):
        return [p for p in merged.geoms if p.area > 1e-8]
    return []


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def generate_stencil(req: StencilRequest) -> dict[str, Any]:
    gray = _decode_raster(req.image_data_uri)
    ratio = req.width_mm / req.height_mm
    if ratio >= 1:
        cols = req.sample_max_px
        rows = max(16, round(cols / ratio))
    else:
        rows = req.sample_max_px
        cols = max(16, round(rows * ratio))
    sampled = _fit_image_cover(gray, cols, rows)
    pix = sampled.load()
    # True = material retained, False = region to cut out.
    material: list[list[bool]] = []
    for y in range(rows):
        row: list[bool] = []
        for x in range(cols):
            dark = pix[x, y] < req.threshold
            if req.invert:
                dark = not dark
            row.append(not dark)
        material.append(row)
    sx, sy = req.width_mm / cols, req.height_mm / rows
    frame_x = max(1, math.ceil(req.frame_mm / sx))
    frame_y = max(1, math.ceil(req.frame_mm / sy))
    _force_frame(material, frame_x, frame_y)

    guides_px: list[tuple[int, int, int, int]] = []
    bridge_px = max(1, math.ceil(req.bridge_width_mm / min(sx, sy)))
    # Every retained-material component not connected to the forced frame is an island.
    # Bridge iteratively and recompute because one bridge can merge several components.
    bridges = 0
    while bridges < req.max_auto_bridges:
        comps = _components(material, True)
        islands = []
        for comp in comps:
            touches = any(x < frame_x or x >= cols-frame_x or y < frame_y or y >= rows-frame_y for x, y in comp)
            if not touches:
                islands.append(comp)
        if not islands:
            break
        islands.sort(key=len, reverse=True)
        guides_px.append(_bridge_to_frame(material, islands[0], bridge_px))
        bridges += 1

    remaining_islands = 0
    for comp in _components(material, True):
        if not any(x < frame_x or x >= cols-frame_x or y < frame_y or y >= rows-frame_y for x, y in comp):
            remaining_islands += 1
    cut_mask = [[not v for v in row] for row in material]
    cutouts = _mask_to_polygons(cut_mask, req.width_mm, req.height_mm)
    guide_polys = [box(x0*sx, y0*sy, x1*sx, y1*sy) for x0, y0, x1, y1 in guides_px]
    warnings: list[str] = []
    if remaining_islands:
        warnings.append(f"Quedan {remaining_islands} islas sin conectar; aumente max_auto_bridges o ajuste la imagen")
    if bridges:
        warnings.append(f"Se insertaron {bridges} puentes automáticos de material; revíselos en la vista previa antes de cortar")
    recipe = req.model_dump(exclude={"image_data_uri"})
    recipe.update({"engine": "raster-stencil-bridge-planner", "source": "embedded-raster", "grid": [cols, rows], "auto_bridges": bridges, "remaining_islands": remaining_islands})
    artifact = CutArtifact(
        outer=box(0, 0, req.width_mm, req.height_mm), cutouts=tuple(cutouts),
        width_mm=req.width_mm, height_mm=req.height_mm, kind="stencil",
        recipe=recipe, guides=tuple(guide_polys), warnings=tuple(warnings),
    )
    result = artifact_response(artifact, req.min_bridge_mm)
    result["bridge_plan"] = {"auto_bridges": bridges, "remaining_islands": remaining_islands, "bridge_width_mm": req.bridge_width_mm}
    return result


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def generate_bridge_coupon(req: BridgeCouponRequest) -> dict[str, Any]:
    # A physical bridge ladder: two large windows leave a narrow central ligament
    # whose width is known. The operator cuts it in sacrificial material and records
    # the smallest width that survives cleanly. No laser parameters are inferred.
    margin = 6.0
    row_h = max(10.0, max(req.widths_mm) + 6.0)
    width = margin*2 + req.length_mm*2 + req.gap_mm
    height = margin*2 + row_h*len(req.widths_mm)
    outer = box(0, 0, width, height)
    holes: list[Polygon] = []
    label_guides: list[Polygon] = []
    for i, bridge in enumerate(req.widths_mm):
        cy = margin + row_h*(i+0.5)
        h = max(2.0, row_h - 3.0)
        left_end = width/2 - bridge/2
        right_start = width/2 + bridge/2
        holes.append(box(margin, cy-h/2, left_end, cy+h/2))
        holes.append(box(right_start, cy-h/2, width-margin, cy+h/2))
        # Tiny guide tick outside the cut windows, useful for visual identification.
        label_guides.append(box(width-3.5, cy-0.15, width-1.5, cy+0.15))
    recipe = {"engine": "openai-bridge-ladder", **req.model_dump(), "cut_outer": True, "purpose": "physical minimum-feature calibration"}
    artifact = CutArtifact(outer=outer, cutouts=tuple(holes), width_mm=width, height_mm=height, kind="bridge-coupon", recipe=recipe, guides=tuple(label_guides), warnings=("Cupón experimental: use material de sacrificio y registre el ancho mínimo que sobreviva; no deduce potencia/velocidad.",))
    result = artifact_response(artifact, min(req.widths_mm))
    result["calibration_steps"] = [
        "Corte el cupón en material de sacrificio con los ajustes que usted ya usa.",
        "Identifique el puente más estrecho que sale íntegro y repetible.",
        "Use ese valor (con margen de seguridad) como min_bridge_mm para diseños futuros.",
    ]
    return result



# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def generate_material_passport(req: MaterialPassportRequest) -> dict[str, Any]:
    """Generate a multi-constraint sacrificial sheet: bridges, holes and gaps.

    This is an OpenAI Lab synthesis: one physical coupon characterises three
    geometry limits used by all generators. The output also carries a stable
    fingerprint so measured results can later become a material constraint
    profile without coupling that profile to a specific design.
    """
    margin = 8.0
    section_gap = 7.0
    widths = [float(v) for v in req.bridge_widths_mm]
    holes_d = [float(v) for v in req.hole_diameters_mm]
    gaps = [float(v) for v in req.gap_widths_mm]
    rows = len(widths) + len(holes_d) + len(gaps)
    width = 170.0
    height = margin * 2 + rows * req.row_height_mm + section_gap * 2
    outer = box(0, 0, width, height)
    cutouts: list[Polygon] = []
    guides: list[Polygon] = []
    measurement_rows: list[dict[str, Any]] = []
    y = margin

    # Zone A: two windows leave a central ligament of known width.
    for i, bridge in enumerate(widths, start=1):
        cy = y + req.row_height_mm / 2
        h = max(2.0, req.row_height_mm - 2.5)
        cx = width / 2
        left = box(margin, cy-h/2, cx-bridge/2, cy+h/2)
        right = box(cx+bridge/2, cy-h/2, width-margin, cy+h/2)
        cutouts.extend([left, right])
        guides.append(box(2.0, cy-0.12, 5.0, cy+0.12))
        measurement_rows.append({"zone":"bridge", "index":i, "target_mm":bridge, "record":"survived_cleanly"})
        y += req.row_height_mm

    y += section_gap
    # Zone B: minimum reproducible holes. Three repetitions make one accidental
    # survivor less likely to be mistaken for a reliable process capability.
    for i, diameter in enumerate(holes_d, start=1):
        cy = y + req.row_height_mm / 2
        xs = (width*0.36, width*0.50, width*0.64)
        for cx in xs:
            cutouts.append(Point(cx, cy).buffer(diameter/2, quad_segs=16))
        guides.append(box(2.0, cy-0.12, 5.0, cy+0.12))
        measurement_rows.append({"zone":"hole", "index":i, "target_mm":diameter, "repetitions":3, "record":"all_three_open_cleanly"})
        y += req.row_height_mm

    y += section_gap
    # Zone C: two windows separated by a known web/gap. This characterises
    # adjacent-cut survival independently from the central bridge ladder.
    for i, gap in enumerate(gaps, start=1):
        cy = y + req.row_height_mm / 2
        h = max(2.0, req.row_height_mm - 2.5)
        cx = width / 2
        fw = req.feature_length_mm
        cutouts.append(box(cx-gap/2-fw, cy-h/2, cx-gap/2, cy+h/2))
        cutouts.append(box(cx+gap/2, cy-h/2, cx+gap/2+fw, cy+h/2))
        guides.append(box(2.0, cy-0.12, 5.0, cy+0.12))
        measurement_rows.append({"zone":"gap", "index":i, "target_mm":gap, "record":"web_survived_cleanly"})
        y += req.row_height_mm

    recipe = {
        "engine": "openai-material-dna-proof-sheet",
        **req.model_dump(),
        "cut_outer": True,
        "purpose": "physical constraint characterization",
    }
    fingerprint_source = json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode("utf-8")
    passport_id = "MDNA-" + hashlib.sha256(fingerprint_source).hexdigest()[:12].upper()
    recipe["passport_id"] = passport_id
    artifact = CutArtifact(
        outer=outer, cutouts=tuple(cutouts), width_mm=width, height_mm=height,
        kind="material-passport", recipe=recipe, guides=tuple(guides),
        warnings=(
            "Hoja de caracterización experimental: algunas características están diseñadas para fallar; use material de sacrificio.",
            "No deduce ni recomienda potencia/velocidad. Mide límites geométricos del proceso que usted ya validó.",
        ),
    )
    # Use the smallest requested web only as a neutral digital reference. This
    # sheet is intentionally exploratory, so FAIL/WARN is not a rejection.
    digital_target = min(widths + gaps)
    result = artifact_response(artifact, digital_target)
    result["passport_id"] = passport_id
    result["measurement_schema"] = {
        "rows": measurement_rows,
        "record_after_cut": {
            "minimum_reliable_bridge_mm": None,
            "minimum_reliable_hole_mm": None,
            "minimum_reliable_gap_mm": None,
            "material_label": "",
            "thickness_mm": None,
            "machine_profile_id": "",
            "preset_reference": "",
            "notes": "",
        },
        "rule": "Use el menor valor repetible que salga íntegro; agregue margen antes de convertirlo en límite productivo.",
    }
    result["interpretation"] = "CHARACTERIZATION_SHEET_NOT_PRODUCTION_PREFLIGHT"
    return result


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def capabilities() -> dict[str, Any]:
    return {
        "version": "0.9.0-experimental",
        "geometry_units": "mm",
        "machine_control": False,
        "engines": {
            "papercut": {"available": True, "provider": "native-parametric"},
            "halftone": {"available": True, "provider": "native-pillow-shapely"},
            "stencil": {"available": True, "provider": "native-raster-bridge-planner"},
            "manufacturability": {"available": True, "provider": "shapely"},
            "vtracer": {"available": _vtracer_available(), "provider": "optional-vtracer", "role": "future high-detail vectorisation"},
            "nesting": {"available": False, "provider": "adapter-reserved", "role": "future Deepnest-compatible packing boundary"},
        },
        "openai_lab": {
            "cut_survival_map": True,
            "minimum_safe_scale": True,
            "adaptive_bridge_planner": True,
            "bridge_ladder_coupon": True,
            "material_dna_passport": True,
            "self_guarding_geometry": True,
            "reproducible_design_genome": True,
        },
    }


# WHY: Encapsula una responsabilidad geométrica verificable sin mezclarla con control de máquina.
def _vtracer_available() -> bool:
    try:
        import vtracer  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False
