"""Render one asset mark from a declarative template and a quality profile.

The output preserves physical millimetre geometry and reports layout/data warnings
instead of silently inventing missing identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .barcode_engine import (
    code128_fragment,
    code39_fragment,
    datamatrix_fragment,
    qr_fragment,
    reposition_fragment,
    resolve_value,
    text_fragment,
)
from .models import QualityProfile, TemplateSpec


@dataclass
class RenderedMark:
    svg: str
    width_mm: float
    height_mm: float
    warnings: list[str] = field(default_factory=list)
    resolved: dict[str, str] = field(default_factory=dict)


def apply_input_rules(template: TemplateSpec, data: Mapping[str, str], capture_mode: str = "manual") -> dict[str, str]:
    """Normalize template input without corrupting imported identifiers.

    Manual capture may use a configured prefix/suffix convenience. Imported CSV
    values default to ``as_is`` so a list containing ``Q00525499`` never becomes
    ``Q00Q00525499``. Rules are declarative and versioned with the template.
    """
    out = {str(k): str(v) for k, v in data.items()}
    for rule in template.input_rules:
        value = str(out.get(rule.field, ""))
        if rule.trim:
            value = value.strip()
        if rule.uppercase:
            value = value.upper()
        if capture_mode == "manual":
            if rule.manual_prefix_enabled and rule.manual_prefix and value and not value.startswith(rule.manual_prefix):
                value = rule.manual_prefix + value
            if rule.manual_suffix_enabled and rule.manual_suffix and value and not value.endswith(rule.manual_suffix):
                value = value + rule.manual_suffix
        elif capture_mode == "import" and rule.imported_values == "ensure_prefix_suffix":
            if rule.manual_prefix_enabled and rule.manual_prefix and value and not value.startswith(rule.manual_prefix):
                value = rule.manual_prefix + value
            if rule.manual_suffix_enabled and rule.manual_suffix and value and not value.endswith(rule.manual_suffix):
                value = value + rule.manual_suffix
        out[rule.field] = value
    return out


def render_template(template: TemplateSpec, quality: QualityProfile, data: Mapping[str, str]) -> RenderedMark:
    parts: list[str] = []
    warnings: list[str] = []
    resolved: dict[str, str] = {}

    for field_name in template.expected_fields:
        value = str(data.get(field_name, "")).strip()
        resolved[field_name] = value
        if not value:
            warnings.append(f"Campo esperado vacío: {field_name}")

    for i, el in enumerate(template.elements):
        value = resolve_value(data, el.source, el.literal)
        if el.source:
            resolved[el.source] = value
        if el.kind in {"text", "code128", "code39", "qr", "datamatrix"} and not value:
            warnings.append(f"Elemento {i} ({el.kind}) quedó vacío")
            continue

        if el.kind == "text":
            frag = text_fragment(value, el.x_mm, el.y_mm, el.font_size_mm, el.width_mm, el.align)
            parts.append(frag.svg)
        elif el.kind == "code128":
            module = el.module_mm or quality.code128_module_mm
            bar_height = el.height_mm or quality.code128_bar_height_mm
            probe = code128_fragment(value, 0, el.y_mm, module, bar_height, quality.code128_quiet_modules)
            px = el.x_mm
            if el.width_mm and el.align == "center" and probe.width_mm <= el.width_mm:
                px = el.x_mm + (el.width_mm - probe.width_mm) / 2
            elif el.width_mm and el.align == "right" and probe.width_mm <= el.width_mm:
                px = el.x_mm + el.width_mm - probe.width_mm
            frag = reposition_fragment(probe, px, el.y_mm)
            parts.append(frag.svg)
            if el.width_mm and frag.width_mm > el.width_mm:
                warnings.append(
                    f"Code128 '{value}' mide {frag.width_mm:.1f} mm y excede la caja de {el.width_mm:.1f} mm"
                )
            if el.x_mm + frag.width_mm > template.width_mm + 0.01:
                warnings.append(f"Code128 '{value}' sale del ancho de la plantilla")
        elif el.kind == "code39":
            module = el.module_mm or quality.code128_module_mm
            bar_height = el.height_mm or quality.code128_bar_height_mm
            probe = code39_fragment(value, 0, el.y_mm, module, bar_height, quality.code128_quiet_modules)
            px = el.x_mm
            if el.width_mm and el.align == "center" and probe.width_mm <= el.width_mm:
                px = el.x_mm + (el.width_mm - probe.width_mm) / 2
            elif el.width_mm and el.align == "right" and probe.width_mm <= el.width_mm:
                px = el.x_mm + el.width_mm - probe.width_mm
            frag = reposition_fragment(probe, px, el.y_mm)
            parts.append(frag.svg)
            if el.x_mm + frag.width_mm > template.width_mm + 0.01:
                warnings.append(f"Code39 '{value}' sale del ancho de la plantilla")
        elif el.kind == "qr":
            frag = qr_fragment(
                value, el.x_mm, el.y_mm,
                el.module_mm or quality.qr_module_mm,
                quality.qr_quiet_modules,
                el.error_correction,
            )
            parts.append(frag.svg)
            if el.x_mm + frag.width_mm > template.width_mm + 0.01 or el.y_mm + frag.height_mm > template.height_mm + 0.01:
                warnings.append(f"QR '{value}' sale de los límites de la plantilla")
        elif el.kind == "datamatrix":
            frag = datamatrix_fragment(
                value, el.x_mm, el.y_mm,
                el.module_mm or quality.datamatrix_module_mm,
                quality.datamatrix_quiet_modules,
            )
            parts.append(frag.svg)
            if el.x_mm + frag.width_mm > template.width_mm + 0.01 or el.y_mm + frag.height_mm > template.height_mm + 0.01:
                warnings.append(f"DataMatrix '{value}' sale de los límites de la plantilla")
        elif el.kind == "rect":
            parts.append(
                f'<rect x="{el.x_mm:.4f}" y="{el.y_mm:.4f}" '
                f'width="{(el.width_mm or 1):.4f}" height="{(el.height_mm or 1):.4f}" '
                f'fill="none" stroke="#000" stroke-width="{el.stroke_mm:.4f}"/>'
            )
        elif el.kind == "line":
            parts.append(
                f'<line x1="{el.x_mm:.4f}" y1="{el.y_mm:.4f}" '
                f'x2="{el.x_mm + (el.width_mm or 1):.4f}" y2="{el.y_mm + (el.height_mm or 0):.4f}" '
                f'stroke="#000" stroke-width="{el.stroke_mm:.4f}"/>'
            )

    body = "\n".join(parts)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{template.width_mm:.4f}mm" '
        f'height="{template.height_mm:.4f}mm" viewBox="0 0 {template.width_mm:.4f} {template.height_mm:.4f}">\n'
        f'<g id="mark">{body}</g>\n</svg>'
    )
    return RenderedMark(svg=svg, width_mm=template.width_mm, height_mm=template.height_mm, warnings=warnings, resolved=resolved)
