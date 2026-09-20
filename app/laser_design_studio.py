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

    @model_validator(mode="after")
    def dimensions_make_sense(self) -> "PapercutRequest":
        if self.margin_mm * 2 >= min(self.width_mm, self.height_mm):
            raise ValueError("El margen consume todo el diseño")
        return self


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

    @model_validator(mode="after")
    def geometry_is_possible(self) -> "HalftoneRequest":
        if self.margin_mm * 2 >= min(self.width_mm, self.height_mm):
            raise ValueError("El margen consume todo el diseño")
        if self.min_diameter_mm > self.max_diameter_mm:
            raise ValueError("min_diameter_mm no puede superar max_diameter_mm")
        return self


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

    @model_validator(mode="after")
    def frame_is_possible(self) -> "StencilRequest":
        if self.frame_mm * 2 >= min(self.width_mm, self.height_mm):
            raise ValueError("El marco consume todo el diseño")
        return self


class BridgeCouponRequest(BaseModel):
    widths_mm: list[float] = Field(default_factory=lambda: [0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0])
    length_mm: float = Field(default=24.0, ge=8.0, le=100.0)
    gap_mm: float = Field(default=4.0, ge=1.0, le=30.0)
    label: bool = True

    @field_validator("widths_mm")
    @classmethod
    def widths_valid(cls, value: list[float]) -> list[float]:
        if not value or len(value) > 30:
            raise ValueError("Use entre 1 y 30 anchos")
        out = [round(float(v), 3) for v in value]
        if any(v < 0.2 or v > 20 for v in out):
            raise ValueError("Cada ancho debe estar entre 0.2 y 20 mm")
        return out


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


def _geometry_paths(geom: Polygon | MultiPolygon) -> list[str]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [_polygon_path(geom)]
    return [_polygon_path(p) for p in geom.geoms if isinstance(p, Polygon) and not p.is_empty]


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


def _halftone_shape(kind: HalftoneShape, cx: float, cy: float, diameter: float) -> Polygon:
    r = diameter / 2.0
    if kind == "circle":
        return Point(cx, cy).buffer(r, quad_segs=10)
    if kind == "diamond":
        return Polygon([(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)])
    return Polygon([(cx + math.cos(math.radians(a))*r, cy + math.sin(math.radians(a))*r) for a in range(0, 360, 60)])


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


def artifact_response(artifact: CutArtifact, min_bridge_mm: float) -> dict[str, Any]:
    preflight = analyze_artifact(artifact, min_bridge_mm)
    warnings = list(artifact.warnings)
    warnings.extend(preflight["issues"])
    return {
        "kind": artifact.kind,
        "width_mm": artifact.width_mm,
        "height_mm": artifact.height_mm,
        "svg": artifact_svg(artifact, preview=False),
