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

from .models import BatchAssignment, JigProfile, MachineProfile, QualityProfile, TemplateSpec, MarkingMode
from .svg_document import IdRegistry, SvgDocumentBuilder, element_group, build_batch_document
from .template_engine import GENERATOR_NAME, GENERATOR_VERSION, apply_input_rules, build_mark_nodes, render_template


# WHY: Normaliza sólo cuando la política lo solicita; evita que comparaciones físicas fallen por formato incidental.
def normalize_identifier(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip()).upper()


# WHY: Convierte CSV/listas flexibles en filas uniformes y detecta encabezados sin imponer un esquema de empresa.
def parse_csv_text(text: str, has_header: bool | None = None) -> tuple[list[str], list[dict[str, str]]]:
    """Parse spreadsheet-style CSV or a plain one-column identifier list.

    ``has_header=None`` uses ``csv.Sniffer`` but falls back conservatively.  A
    headerless file such as one serial per line becomes a generic ``value``
    column and the first identifier is preserved instead of being lost as a
    field name.
    """
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows_raw = [row for row in csv.reader(io.StringIO(text), dialect=dialect) if any(str(v).strip() for v in row)]
    if not rows_raw:
        raise ValueError("Archivo sin datos")
    width = max(len(r) for r in rows_raw)
    if has_header is None:
        try:
            detected = csv.Sniffer().has_header(sample)
        except csv.Error:
            detected = False
        # For a one-column sequence of IDs, Sniffer can over-fit the first ID as
        # a heading. Treat it as a list unless the first token looks explicitly
        # like a field name commonly used in spreadsheets.
        if width == 1:
            first = str(rows_raw[0][0]).strip()
            looks_like_label = first.lower() in {"serial", "serie", "id", "asset_id", "manufacturer_id", "economic_number", "numero", "número", "value", "valor"}
            detected = bool(detected and looks_like_label)
        has_header = detected
    if has_header:
        headers = [str(v).strip() or f"col_{i+1}" for i, v in enumerate(rows_raw[0])]
        data_rows = rows_raw[1:]
    else:
        headers = ["value"] if width == 1 else [f"col_{i+1}" for i in range(width)]
        data_rows = rows_raw
    rows: list[dict[str, str]] = []
    for raw in data_rows:
        padded = list(raw) + [""] * (len(headers) - len(raw))
        row = {headers[i]: str(padded[i]).strip() for i in range(len(headers))}
        if any(row.values()):
            rows.append(row)
    return headers, rows


# WHY: Calcula coordenadas de slots desde el jig para que la colocación en cama sea reproducible y auditable.
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


# WHY: Calcula cuántas cargas físicas requiere un dataset sin confundir cantidad de registros con capacidad de jig.
def chunk_count(total_records: int, capacity: int) -> int:
    if capacity <= 0:
        raise ValueError("jig capacity must be > 0")
    return math.ceil(total_records / capacity)


# WHY: Prefijo de espacio de nombres de una marca dentro de un lote.
# Cada posicion recibe su propio prefijo (``mark_0001__``) para que los identificadores
# de sus elementos no puedan colisionar con los de otra marca del mismo documento.
def mark_namespace(sequence: int) -> str:
    return f"mark_{sequence:04d}"


def _place_mark(namespace: str, nodes, x_mm: float, y_mm: float) -> str:
    """Place one already-built mark at its physical slot origin.

    WHY: ``translate`` es la unica transformacion que LightBurn, Sculpfun Space e
    Inkscape interpretan de forma identica, y deja la geometria interna en los
    milimetros absolutos de la plantilla, tal como los ve el disenador.
    """
    # WHY: Se reutiliza el mismo serializador de elemento que la marca individual
    # para que la rotacion de un objeto se comporte igual suelta que dentro de un lote.
    inner = "".join(element_group(n) for n in nodes if n.svg)
    return f'<g id="{namespace}" transform="translate({x_mm:.4f} {y_mm:.4f})">{inner}</g>'


# WHY: Agrupa el SVG final y la información usada para manifestar cada posición.
@dataclass
class BatchRenderResult:
    svg: str
    preview_svg: str
    warnings: list[str] = field(default_factory=list)
    manifest: list[dict] = field(default_factory=list)


# WHY: Valida asignaciones, conciliación y posiciones y construye una cama de grabado sin mezclar guías visuales con producción.
def render_batch(
    machine: MachineProfile,
    jig: JigProfile,
    template: TemplateSpec,
    quality: QualityProfile,
    rows: list[dict[str, str]],
    assignments: list[BatchAssignment],
    require_physical_confirmation: bool = True,
    mode: str = "production",
    text_as_paths: bool = False,
    marking_mode_override: MarkingMode | None = None,
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

        # Physical reconciliation is template-driven.  Equipment-specific field
        # names are configuration, not core logic.  Prefer the template's declared
        # identity field, then its first expected field, then the first non-empty
        # imported value as a safe generic fallback.
        primary_field = str(template.metadata.get("primary_identity_field", "")).strip()
        candidate = str(row.get(primary_field, "")).strip() if primary_field else ""
        if not candidate and template.expected_fields:
            candidate = str(row.get(template.expected_fields[0], "")).strip()
        if not candidate:
            candidate = next((str(v).strip() for v in row.values() if str(v).strip()), "")
        match: bool | None = None
        if a.physical_id is not None and a.physical_id.strip() != "":
            match = normalize_identifier(a.physical_id) == normalize_identifier(candidate)
            if not match:
                raise ValueError(
                    f"Slot {a.slot_index}: identificación física '{a.physical_id}' no coincide con CSV '{candidate}'"
                )
        elif require_physical_confirmation:
            raise ValueError(f"Slot {a.slot_index}: falta confirmación del ID escrito físicamente")

        namespace = mark_namespace(len(manifest) + 1)
        # WHY: Un registro de IDs por marca, con prefijo propio, hace estructuralmente
        # imposible repetir un identificador entre posiciones del mismo lote.
        registry = IdRegistry(prefix=f"{namespace}__")
        nodes, mark_warnings, _resolved, _ids, _estimated = build_mark_nodes(
            template, quality, row, registry, text_as_paths=text_as_paths,
            marking_mode=(marking_mode_override or template.marking_mode), svg_mode=mode
        )
        warnings.extend([f"slot {a.slot_index}: {w}" for w in mark_warnings])
        mx = float(slot["mark_x_mm"])
        my = float(slot["mark_y_mm"])
        if mx + template.width_mm > machine.bed_width_mm or my + template.height_mm > machine.bed_height_mm:
            raise ValueError(f"Slot {a.slot_index}: el marcado sale del área útil de {machine.name}")
        parts.append(_place_mark(namespace, nodes, mx, my))
        manifest.append({
            "slot_index": a.slot_index,
            "row_index": a.row_index,
            "id": candidate,
            "physical_id": a.physical_id or "",
            "physical_match": match,
            "mark_x_mm": mx,
            "mark_y_mm": my,
            "template_id": template.id,
            "polarity": (marking_mode_override or template.marking_mode).polarity,
            "polarity_scope": (marking_mode_override or template.marking_mode).polarity_scope,
            "negative_field": (marking_mode_override or template.marking_mode).negative_field,
            "field_margin_mm": (marking_mode_override or template.marking_mode).field_margin_mm,
            "kerf_compensation_mm": (marking_mode_override or template.marking_mode).kerf_compensation_mm,
        })

    # Registration-only outlines are deliberately dashed and assigned to a non-marking guide group.
    guides = []
    for s in slot_positions(jig):
        guides.append(
            f'<rect x="{float(s["slot_x_mm"]):.3f}" y="{float(s["slot_y_mm"]):.3f}" '
            f'width="{jig.grid.slot_width_mm:.3f}" height="{jig.grid.slot_height_mm:.3f}" '
            f'fill="none" stroke="#00A0FF" stroke-width="0.15" stroke-dasharray="2,2"/>'
        )

    metadata = {
        "template_id": template.id,
        "template_version": template.version,
        "jig_id": jig.id,
        "machine_profile_id": machine.id,
        "record_count": str(len(manifest)),
        "generated_by": GENERATOR_NAME,
        "generated_version": GENERATOR_VERSION,
        "units": "mm",
        "svg_mode": mode,
        "polarity": (marking_mode_override or template.marking_mode).polarity,
        "polarity_scope": (marking_mode_override or template.marking_mode).polarity_scope,
        "negative_field": (marking_mode_override or template.marking_mode).negative_field,
        "field_margin_mm": str((marking_mode_override or template.marking_mode).field_margin_mm),
        "kerf_compensation_mm": str((marking_mode_override or template.marking_mode).kerf_compensation_mm),
    }
    svg = build_batch_document(
        machine.bed_width_mm, machine.bed_height_mm,
        marks_svg="".join(parts), guides_svg="", mode=mode, metadata=metadata,
    )
    preview_svg = build_batch_document(
        machine.bed_width_mm, machine.bed_height_mm,
        marks_svg="".join(parts),
        guides_svg=f'<g id="GUIDES_DO_NOT_ENGRAVE" opacity="0.35">{"".join(guides)}</g>',
        mode=mode, metadata={**metadata, "artifact": "preview_do_not_engrave"},
    )
    return BatchRenderResult(svg=svg, preview_svg=preview_svg, warnings=warnings, manifest=manifest)
