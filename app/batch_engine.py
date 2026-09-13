"""CSV ingestion, jig positioning and physical-ID reconciliation for batch marking.

Production output contains marks only. Registration guides are emitted to a separate
preview SVG to reduce the risk of accidentally engraving jig geometry.
"""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field
from typing import Iterable

from .models import BatchAssignment, JigProfile, MachineProfile, QualityProfile, TemplateSpec
from .template_engine import apply_input_rules, render_template


def normalize_identifier(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip()).upper()


def parse_csv_text(text: str) -> tuple[list[str], list[dict[str, str]]]:
    # utf-8-sig allows Excel CSV exports with BOM.
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV sin encabezados")
    headers = [str(h).strip() for h in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {str(k).strip(): "" if v is None else str(v).strip() for k, v in raw.items() if k is not None}
        if any(v for v in row.values()):
            rows.append(row)
    return headers, rows


def slot_positions(jig: JigProfile) -> list[dict[str, float | int]]:
    g = jig.grid
    disabled = set(jig.disabled_slots)
    slots: list[dict[str, float | int]] = []
    idx = 0
    for r in range(g.rows):
        for c in range(g.cols):
            if idx not in disabled:
                sx = g.origin_x_mm + c * g.pitch_x_mm
                sy = g.origin_y_mm + r * g.pitch_y_mm
                slots.append({
                    "slot_index": idx,
                    "row": r,
                    "col": c,
                    "slot_x_mm": sx,
                    "slot_y_mm": sy,
                    "mark_x_mm": sx + g.mark_offset_x_mm,
                    "mark_y_mm": sy + g.mark_offset_y_mm,
                })
            idx += 1
    return slots


def chunk_count(total_records: int, capacity: int) -> int:
    if capacity <= 0:
        raise ValueError("jig capacity must be > 0")
    return math.ceil(total_records / capacity)


def _extract_svg(svg: str) -> str:
    idx = svg.find("<svg")
    return svg[idx:] if idx >= 0 else svg


def _nest_mark(svg: str, x_mm: float, y_mm: float, width_mm: float, height_mm: float) -> str:
    root = _extract_svg(svg)
    # Template viewBox uses millimetres as user units. Strip its outer SVG and
    # translate the contents to the calibrated mark origin. This avoids duplicate
    # width/height attributes and keeps exact geometry.
    start = root.find(">")
    end = root.rfind("</svg>")
    if start < 0 or end < 0:
        raise ValueError("invalid mark SVG")
    inner = root[start + 1:end]
    return f'<g transform="translate({x_mm:.4f} {y_mm:.4f})">{inner}</g>'


@dataclass
class BatchRenderResult:
    svg: str
    preview_svg: str
    warnings: list[str] = field(default_factory=list)
    manifest: list[dict] = field(default_factory=list)


def render_batch(
    machine: MachineProfile,
    jig: JigProfile,
    template: TemplateSpec,
    quality: QualityProfile,
    rows: list[dict[str, str]],
    assignments: list[BatchAssignment],
    require_physical_confirmation: bool = True,
) -> BatchRenderResult:
    slots = {int(s["slot_index"]): s for s in slot_positions(jig)}
    warnings: list[str] = []
    manifest: list[dict] = []
    parts: list[str] = []

    if jig.template_id != template.id:
        warnings.append(f"El jig {jig.id} fue definido para {jig.template_id}, no para {template.id}")

    for a in assignments:
        if a.row_index >= len(rows):
            raise ValueError(f"row_index {a.row_index} fuera de rango")
        if a.slot_index not in slots:
            raise ValueError(f"slot_index {a.slot_index} no existe o está deshabilitado")
        raw_row = rows[a.row_index]
        row = apply_input_rules(template, raw_row, capture_mode="import")
        slot = slots[a.slot_index]

        # Resolve the best candidate ID for physical reconciliation after template
        # import rules. Default policy is as-is, so CSV identifiers are never
        # double-prefixed unless a template explicitly opts in.
        candidate = (
            row.get("manufacturer_id")
            or row.get("operational_id")
            or row.get("asset_id")
            or row.get("serial")
            or row.get("economic_number")
            or ""
        )
        match: bool | None = None
        if a.physical_id is not None and a.physical_id.strip() != "":
            match = normalize_identifier(a.physical_id) == normalize_identifier(candidate)
            if not match:
                raise ValueError(
                    f"Slot {a.slot_index}: identificación física '{a.physical_id}' no coincide con CSV '{candidate}'"
                )
        elif require_physical_confirmation:
            raise ValueError(f"Slot {a.slot_index}: falta confirmación del ID escrito físicamente")

        mark = render_template(template, quality, row)
        warnings.extend([f"slot {a.slot_index}: {w}" for w in mark.warnings])
        mx = float(slot["mark_x_mm"])
        my = float(slot["mark_y_mm"])
        if mx + template.width_mm > machine.bed_width_mm or my + template.height_mm > machine.bed_height_mm:
            raise ValueError(f"Slot {a.slot_index}: el marcado sale del área útil de {machine.name}")
        parts.append(_nest_mark(mark.svg, mx, my, template.width_mm, template.height_mm))
        manifest.append({
            "slot_index": a.slot_index,
            "row_index": a.row_index,
            "id": candidate,
            "physical_id": a.physical_id or "",
            "physical_match": match,
            "mark_x_mm": mx,
            "mark_y_mm": my,
            "template_id": template.id,
        })

    # Registration-only outlines are deliberately dashed and assigned to a non-marking guide group.
    guides = []
    for s in slot_positions(jig):
        guides.append(
            f'<rect x="{float(s["slot_x_mm"]):.3f}" y="{float(s["slot_y_mm"]):.3f}" '
            f'width="{jig.grid.slot_width_mm:.3f}" height="{jig.grid.slot_height_mm:.3f}" '
            f'fill="none" stroke="#00A0FF" stroke-width="0.15" stroke-dasharray="2,2"/>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{machine.bed_width_mm:.3f}mm" '
        f'height="{machine.bed_height_mm:.3f}mm" viewBox="0 0 {machine.bed_width_mm:.3f} {machine.bed_height_mm:.3f}">\n'
        f'<g id="MARKS">{"".join(parts)}</g>\n'
        f'</svg>'
    )
    preview_svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{machine.bed_width_mm:.3f}mm" '
        f'height="{machine.bed_height_mm:.3f}mm" viewBox="0 0 {machine.bed_width_mm:.3f} {machine.bed_height_mm:.3f}">\n'
        f'<g id="GUIDES_DO_NOT_ENGRAVE" opacity="0.35">{"".join(guides)}</g>\n'
        f'<g id="MARKS">{"".join(parts)}</g>\n'
        f'</svg>'
    )
    return BatchRenderResult(svg=svg, preview_svg=preview_svg, warnings=warnings, manifest=manifest)
