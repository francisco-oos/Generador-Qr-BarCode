"""Build a four-panel physical characterization coupon from the production renderer.

WHY:
El modo invertido no puede aprobarse sólo en pantalla.  Un cupón que coloca el mismo
dato en cuatro estrategias físicas sobre una única pieza de descarte permite comparar
contraste, ablación y lectura sin mezclar identidades distintas ni inventar presets.
"""
from __future__ import annotations

import re

from .models import MarkingMode, QualityProfile, TemplateSpec
from .template_engine import apply_input_rules, render_template
from .text_outline import text_to_path_data


# WHY: Los IDs de cada panel deben ser únicos aunque cada render individual use los mismos nombres semánticos.
def _prefix_ids(fragment: str, prefix: str) -> str:
    mapping: dict[str, str] = {}

    # WHY: Prefija cada id conservando un mapa para reescribir referencias internas del mismo panel.
    def repl(match: re.Match[str]) -> str:
        original = match.group(1)
        renamed = f"{prefix}__{original}"
        mapping[original] = renamed
        return f'id="{renamed}"'

    out = re.sub(r'id="([A-Za-z_][A-Za-z0-9_-]*)"', repl, fragment)
    for old, new in mapping.items():
        out = out.replace(f"url(#{old})", f"url(#{new})")
        out = out.replace(f'href="#{old}"', f'href="#{new}"')
        out = out.replace(f"href='#{old}'", f"href='#{new}'")
    return out


# WHY: Extrae sólo las capas dibujables; los metadatos de cada panel se resumen una sola vez en el cupón.
def _drawing_body(svg: str) -> str:
    start = svg.find(">")
    end = svg.rfind("</svg>")
    if start < 0 or end < 0:
        raise ValueError("SVG de panel inválido")
    body = svg[start + 1:end]
    body = re.sub(r"<metadata>.*?</metadata>", "", body, flags=re.S)
    return body


# WHY: El rótulo físico identifica cada experimento sin depender de una fuente instalada en la PC de grabado.
def _label_path(text: str, x_mm: float, baseline_y_mm: float, width_mm: float) -> str:
    path, _ = text_to_path_data(text, x_mm, baseline_y_mm, 2.8, width_mm, "left", bold=True)
    return path


# WHY: Produce las cuatro comparaciones acordadas usando exactamente render_template, no un generador paralelo.
def render_marking_coupon(
    template: TemplateSpec,
    quality: QualityProfile,
    data: dict[str, str],
    capture_mode: str = "manual",
    negative_base: MarkingMode | None = None,
) -> dict:
    normalized = apply_input_rules(template, data, capture_mode=capture_mode)
    base = (negative_base or MarkingMode(polarity="negative")).model_copy(deep=True)
    base.polarity = "negative"

    # Four negative combinations requested for physical characterisation.  The
    # positive baseline is already available through /api/marking/compare and does
    # not consume one of the four coupon panels.
    modes = [
        ("A", "NEG CODES ISLANDS", base.model_copy(update={"polarity_scope": "codes", "negative_field": "islands"})),
        ("B", "NEG CODES TEMPLATE 2PASS", base.model_copy(update={"polarity_scope": "codes", "negative_field": "template", "field_margin_mm": 0.0})),
        ("C", "NEG ALL ISLANDS", base.model_copy(update={"polarity_scope": "all", "negative_field": "islands"})),
        ("D", "NEG ALL TEMPLATE", base.model_copy(update={"polarity_scope": "all", "negative_field": "template", "field_margin_mm": 0.0})),
    ]

    label_h = 5.0
    gutter = 4.0
    panel_w = template.width_mm
    panel_h = template.height_mm + label_h
    canvas_w = panel_w * 2 + gutter * 3
    canvas_h = panel_h * 2 + gutter * 3
    positions = [
        (gutter, gutter),
        (gutter * 2 + panel_w, gutter),
        (gutter, gutter * 2 + panel_h),
        (gutter * 2 + panel_w, gutter * 2 + panel_h),
    ]

    groups: list[str] = []
    manifest: list[dict] = []
    warnings: list[str] = []
    for (key, label, mode), (x, y) in zip(modes, positions):
        rendered = render_template(
            template, quality, normalized, mode="production",
            marking_mode_override=mode,
        )
        body = _prefix_ids(_drawing_body(rendered.svg), f"coupon_{key.lower()}")
        label_d = _label_path(f"{key} {label}", x + 0.8, y + 3.4, panel_w - 1.6)
        groups.append(
            f'<g id="coupon_{key.lower()}">'
            f'<path id="coupon_{key.lower()}__label" d="{label_d}" fill="#000"/>'
            f'<g id="coupon_{key.lower()}__mark" transform="translate({x:.4f} {y + label_h:.4f})">{body}</g>'
            f'</g>'
        )
        manifest.append({
            "panel": key,
            "label": label,
            "polarity": mode.polarity,
            "polarity_scope": mode.polarity_scope,
            "negative_field": mode.negative_field,
            "field_margin_mm": mode.field_margin_mm,
            "kerf_compensation_mm": mode.kerf_compensation_mm,
            "estimated_ablation_mm2": rendered.estimated_ablation_mm2,
            "estimated_ablation_ratio": rendered.estimated_ablation_ratio,
        })
        warnings.extend(f"{key}: {w}" for w in rendered.warnings)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.4f}mm" height="{canvas_h:.4f}mm" '
        f'viewBox="0 0 {canvas_w:.4f} {canvas_h:.4f}">'
        f'<metadata><marking-coupon generated_version="0.8.0" template_id="{template.id}"/></metadata>'
        f'{"".join(groups)}</svg>'
    )
    return {
        "svg": svg,
        "width_mm": canvas_w,
        "height_mm": canvas_h,
        "panels": manifest,
        "warnings": warnings,
        "note": "Cupón experimental: requiere pieza de descarte y aceptación física; no es un preset de producción.",
    }
