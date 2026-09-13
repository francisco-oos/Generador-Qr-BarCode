"""Render one asset mark from a declarative template and a quality profile.

The mathematical symbol encoders remain unchanged.  v0.8.0 adds a separate
physical-marking layer (positive vs. negative/background ablation) so an
experiment on material cannot silently change the identifier a scanner is
expected to decode.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .barcode_engine import (
    SafeFormatDict,
    code128_fragment,
    code39_fragment,
    datamatrix_fragment,
    negative_background_fragment,
    qr_fragment,
    reposition_fragment,
    resolve_value,
    text_fragment,
)
from .models import MarkingMode, QualityProfile, TemplateSpec
from .image_element import prepare_image_element
from .physical_marking import (
    CODE_KINDS,
    area_of_rects,
    bounds_with_margin,
    code_hole_path,
    effective_marking_mode,
    line_stroke_path,
    negative_field_path,
    rect_stroke_path,
    validate_marking_mode_for_render,
)
from .svg_document import (
    DEFAULT_LAYER_BY_KIND,
    DocumentNode,
    rotation_transform,
    IdRegistry,
    SvgDocumentBuilder,
    default_element_name,
    slug,
)
from .text_outline import OUTLINE_FONT_NAME, OutlineUnavailable, text_to_path_data

GENERATOR_NAME = "Server Oficina Marking Studio"
GENERATOR_VERSION = "0.8.0"


# WHY: Devuelve juntos el SVG, advertencias y métricas físicas para que UI/histórico no tengan que reinterpretar el artefacto.
@dataclass
class RenderedMark:
    svg: str
    width_mm: float
    height_mm: float
    warnings: list[str] = field(default_factory=list)
    resolved: dict[str, str] = field(default_factory=dict)
    element_ids: list[str] = field(default_factory=list)
    marking_mode: dict = field(default_factory=dict)
    estimated_ablation_mm2: float | None = None
    estimated_ablation_ratio: float | None = None


def apply_input_rules(template: TemplateSpec, data: Mapping[str, str], capture_mode: str = "manual") -> dict[str, str]:
    """Normalize input while preserving the established manual/import prefix invariant."""
    out = {str(k): str(v) for k, v in data.items()}
    for rule in template.input_rules:
        value = str(out.get(rule.field, ""))
        if rule.trim:
            value = value.strip()
        if rule.uppercase:
            value = value.upper()
        elif rule.lowercase:
            value = value.lower()
        if rule.pad_zeros_to and value:
            value = value.zfill(rule.pad_zeros_to)
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

    for derived in template.derived_fields:
        existing = str(out.get(derived.field, "")).strip()
        if existing and not derived.overwrite:
            continue
        out[derived.field] = derived.expression.format_map(SafeFormatDict({k: str(v) for k, v in out.items()}))
    return out


# WHY: La unicidad semántica de IDs permite editar/auditar SVG individuales y lotes sin colisiones XML.
def assign_element_ids(template: TemplateSpec, registry: IdRegistry) -> list[str]:
    ids: list[str] = []
    for index, el in enumerate(template.elements):
        base = slug(el.name) if el.name else default_element_name(el.kind, el.source, el.literal, index)
        ids.append(registry.reserve(base or f"element_{index + 1:02d}"))
    return ids


# WHY: Todo negativo debe advertir explícitamente que describe ablación y que el kerf real requiere medición física.
def _marking_warning(mode: MarkingMode) -> str:
    return (
        "MODO INVERTIDO: el SVG describe ablación, no el símbolo que se escanea. "
        "En negativo el módulo físico puede reducirse aproximadamente por el kerf/spot; "
        "mida sobre pieza real antes de estandarizar."
    )


# WHY: Encapsula el patrón even-odd campo menos contenido para mantener una sola implementación del negativo por isla.
def _negative_island_svg(field_rect: tuple[float, float, float, float], hole_path: str) -> str:
    return f'<path d="{negative_field_path(field_rect, hole_path)}" fill="#000" fill-rule="evenodd"/>'


# WHY: Un margen de campo puede sacar la ablación fuera del lienzo aunque el código positivo todavía quepa; se informa explícitamente.
def _warn_negative_field_bounds(field_rect: tuple[float, float, float, float], template: TemplateSpec, label: str, warnings: list[str]) -> None:
    x, y, w, h = field_rect
    if x < -0.01 or y < -0.01 or x + w > template.width_mm + 0.01 or y + h > template.height_mm + 0.01:
        warnings.append(f"Campo invertido de {label} sale de los límites de la plantilla; reduzca field_margin_mm o reposicione el elemento")


def build_mark_nodes(
    template: TemplateSpec,
    quality: QualityProfile,
    data: Mapping[str, str],
    registry: IdRegistry,
    text_as_paths: bool = False,
    marking_mode: MarkingMode | None = None,
    svg_mode: str = "production",
) -> tuple[list[DocumentNode], list[str], dict[str, str], list[str], float | None]:
    """Build semantic nodes for one mark.

    Negative rendering is a physical post-process over canonical positive geometry.
    The QR/barcode encoders are never given an inverted payload or polarity.
    """
    effective = marking_mode or template.marking_mode
    validate_marking_mode_for_render(effective, svg_mode)
    nodes: list[DocumentNode] = []
    warnings: list[str] = []
    resolved: dict[str, str] = {}
    element_ids = assign_element_ids(template, registry)
    template_holes: list[str] = []
    template_protected_area = 0.0
    estimated_ablated = 0.0
    # WHY: Se guardan cajas físicas reales para advertir si un logo/imagen invade el
    # área completa de un código (incluida su quiet zone). Es una advertencia de
    # composición, no una supuesta certificación de lectura.
    code_boxes: list[tuple[str, float, float, float, float]] = []
    image_boxes: list[tuple[str, float, float, float, float]] = []

    if effective.is_negative:
        warnings.append(_marking_warning(effective))
        if effective.polarity_scope == "all" and any(el.kind == "image" for el in template.elements):
            raise ValueError(
                "Invertido + alcance 'todo' con elementos image no se exporta todavía: "
                "un SVG vector subido puede contener geometría que no puede fundirse de forma segura como hueco. "
                "Use alcance 'codes' o retire la imagen del trabajo negativo."
            )
        if effective.negative_field == "template" and effective.field_margin_mm:
            warnings.append("field_margin_mm no se aplica al campo 'template': el campo es exactamente el lienzo de la plantilla.")
        if effective.polarity_scope == "codes" and effective.negative_field == "template":
            warnings.append(
                "MODO INVERTIDO 2 ETAPAS: el fondo de plantilla deja los códigos en relieve y texto/geometría permanecen en capas positivas. "
                "Para que el texto quede hundido debe asignarse una segunda operación/pasada en el software de la máquina; Marking Studio no la ejecuta automáticamente."
            )
        if effective.polarity_scope == "all" and effective.negative_field == "template":
            rotated = [el.name or el.kind for el in template.elements if float(el.rotation_deg or 0) % 360]
            if rotated:
                raise ValueError(
                    "Invertido + todo + campo de plantilla no admite todavía elementos rotados porque al fundir la geometría "
                    "se perderían sus transforms individuales. Use islands o quite la rotación."
                )

    for field_name in template.expected_fields:
        value = str(data.get(field_name, "")).strip()
        resolved[field_name] = value
        if not value:
            warnings.append(f"Campo esperado vacío: {field_name}")

    for i, el in enumerate(template.elements):
        element_id = element_ids[i]
        layer = el.layer or DEFAULT_LAYER_BY_KIND.get(el.kind, "layer_geometry")
        value = resolve_value(data, el.source, el.literal)
        if el.source:
            resolved[el.source] = value
        if el.kind in {"text", "code128", "code39", "qr", "datamatrix"} and not value:
            warnings.append(f"Elemento {i} ({el.kind}) quedó vacío")
            continue

        # Compatibility with v0.7.1 custom templates: a legacy per-code negative flag
        # is honored only when no v0.8 negative template mode is active.
        legacy_negative = (
            not effective.is_negative
            and getattr(el, "engraving_mode", "positive") == "negative_background"
            and el.kind in CODE_KINDS
        )
        invert_element = effective.is_negative and (
            effective.polarity_scope == "all" or el.kind in CODE_KINDS
        )
        island_mode = effective.is_negative and effective.negative_field == "islands" and invert_element
        template_mode = effective.is_negative and effective.negative_field == "template" and effective.polarity_scope == "all"
        template_codes_mode = effective.is_negative and effective.negative_field == "template" and effective.polarity_scope == "codes" and el.kind in CODE_KINDS

        if el.kind == "text":
            box_w = el.width_mm or max(el.font_size_mm * 0.6, len(value) * el.font_size_mm * 0.6)
            box_x = el.x_mm
            box_y = el.y_mm - el.font_size_mm
            outline_path = ""
            if island_mode or template_mode or text_as_paths:
                try:
                    outline_path, advance = text_to_path_data(
                        value, el.x_mm, el.y_mm, el.font_size_mm, el.width_mm, el.align, bold=True
                    )
                    if el.width_mm is None:
                        box_w = max(box_w, advance)
                except OutlineUnavailable as exc:
                    if island_mode or template_mode:
                        raise ValueError(f"Texto negativo requiere contorno de glifo: {exc}") from exc
                    warnings.append(f"Texto '{value}' no se convirtió a curvas ({exc}); se exporta como texto editable")

            if template_mode:
                template_holes.append(outline_path)
                continue
            if island_mode:
                field_rect = bounds_with_margin(box_x, box_y, box_w, el.font_size_mm, effective.field_margin_mm)
                _warn_negative_field_bounds(field_rect, template, "texto", warnings)
                svg = _negative_island_svg(field_rect, outline_path)
                estimated_ablated += max(0.0, field_rect[2] * field_rect[3])
            elif outline_path and text_as_paths:
                svg = f'<path d="{outline_path}" fill="#000" fill-rule="nonzero"/>'
            else:
                svg = text_fragment(value, el.x_mm, el.y_mm, el.font_size_mm, el.width_mm, el.align).svg
            cx = el.x_mm + box_w / 2
            cy = el.y_mm - el.font_size_mm / 2
            nodes.append(DocumentNode(element_id, layer, svg, title=value,
                                      transform=rotation_transform(el.rotation_deg, cx, cy)))

        elif el.kind in {"code128", "code39"}:
            module = el.module_mm or quality.code128_module_mm
            bar_height = el.height_mm or quality.code128_bar_height_mm
            label = "Code128" if el.kind == "code128" else "Code39"
            if module < quality.code128_module_mm:
                warnings.append(f"{label} '{value}' usa módulo {module:.2f} mm menor al perfil conservador {quality.code128_module_mm:.2f} mm")
            if el.kind == "code128" and bar_height < quality.code128_bar_height_mm * 0.8:
                warnings.append(f"Code128 '{value}' usa barras bajas ({bar_height:.1f} mm) frente al perfil {quality.code128_bar_height_mm:.1f} mm")
            quiet = el.quiet_modules if el.quiet_modules is not None else quality.code128_quiet_modules
            if el.quiet_modules is not None and el.quiet_modules < quality.code128_quiet_modules:
                warnings.append(f"{label} '{value}' usa quiet zone de {el.quiet_modules} módulos, por debajo de los {quality.code128_quiet_modules} del perfil {quality.id}; verifique la lectura con el lector real")
            maker = code128_fragment if el.kind == "code128" else code39_fragment
            probe = maker(value, 0, el.y_mm, module, bar_height, quiet)
            px = el.x_mm
            if el.width_mm and el.align == "center" and probe.width_mm <= el.width_mm:
                px = el.x_mm + (el.width_mm - probe.width_mm) / 2
            elif el.width_mm and el.align == "right" and probe.width_mm <= el.width_mm:
                px = el.x_mm + el.width_mm - probe.width_mm
            frag = reposition_fragment(probe, px, el.y_mm)
            if template_mode or template_codes_mode:
                template_holes.append(code_hole_path(probe.rects, px, el.y_mm, effective.kerf_compensation_mm, compensate_y=False))
                template_protected_area += area_of_rects(probe.rects)
                continue
            if island_mode:
                frag = negative_background_fragment(
                    probe, px, el.y_mm, effective.field_margin_mm, effective.kerf_compensation_mm, kerf_compensate_y=False
                )
                _warn_negative_field_bounds((px-effective.field_margin_mm, el.y_mm-effective.field_margin_mm, frag.width_mm, frag.height_mm), template, label, warnings)
                field_area = (probe.width_mm + 2*effective.field_margin_mm) * (probe.height_mm + 2*effective.field_margin_mm)
                protected = area_of_rects(probe.rects)
                estimated_ablated += max(0.0, field_area - protected)
            elif legacy_negative:
                frag = negative_background_fragment(probe, px, el.y_mm)
                warnings.append(f"{label} '{value}' usa el modo negativo legado v0.7.1; migre la plantilla a marking_mode")
            nodes.append(DocumentNode(
                element_id, layer, frag.svg, title=value,
                transform=rotation_transform(el.rotation_deg, px + probe.width_mm / 2, el.y_mm + probe.height_mm / 2),
            ))
            code_boxes.append((element_id, px, el.y_mm, probe.width_mm, probe.height_mm))
            if el.kind == "code128" and el.width_mm and probe.width_mm > el.width_mm:
                warnings.append(f"Code128 '{value}' mide {probe.width_mm:.1f} mm y excede la caja de {el.width_mm:.1f} mm")
            if px + probe.width_mm > template.width_mm + 0.01:
                warnings.append(f"{label} '{value}' sale del ancho de la plantilla")

        elif el.kind == "qr":
            module = el.module_mm or quality.qr_module_mm
            quiet = el.quiet_modules if el.quiet_modules is not None else quality.qr_quiet_modules
            if module < quality.qr_module_mm:
                warnings.append(f"QR '{value}' usa módulo {module:.2f} mm menor al perfil conservador {quality.qr_module_mm:.2f} mm")
            if el.quiet_modules is not None and el.quiet_modules < quality.qr_quiet_modules:
                warnings.append(f"QR '{value}' usa quiet zone de {el.quiet_modules} módulos, por debajo de los {quality.qr_quiet_modules} del perfil; verifique con el lector real")
            probe = qr_fragment(value, el.x_mm, el.y_mm, module, quiet, el.error_correction)
            frag = probe
            if template_mode or template_codes_mode:
                template_holes.append(code_hole_path(probe.rects, el.x_mm, el.y_mm, effective.kerf_compensation_mm))
                template_protected_area += area_of_rects(probe.rects)
                continue
            if island_mode:
                frag = negative_background_fragment(probe, el.x_mm, el.y_mm, effective.field_margin_mm, effective.kerf_compensation_mm)
                _warn_negative_field_bounds((el.x_mm-effective.field_margin_mm, el.y_mm-effective.field_margin_mm, frag.width_mm, frag.height_mm), template, "QR", warnings)
                field_area = (probe.width_mm + 2*effective.field_margin_mm) * (probe.height_mm + 2*effective.field_margin_mm)
                estimated_ablated += max(0.0, field_area - area_of_rects(probe.rects))
            elif legacy_negative:
                frag = negative_background_fragment(probe, el.x_mm, el.y_mm)
            nodes.append(DocumentNode(element_id, layer, frag.svg, title=value,
                                      transform=rotation_transform(el.rotation_deg, el.x_mm + probe.width_mm/2, el.y_mm + probe.height_mm/2)))
            code_boxes.append((element_id, el.x_mm, el.y_mm, probe.width_mm, probe.height_mm))
            if el.x_mm + probe.width_mm > template.width_mm + 0.01 or el.y_mm + probe.height_mm > template.height_mm + 0.01:
                warnings.append(f"QR '{value}' sale de los límites de la plantilla")

        elif el.kind == "datamatrix":
            module = el.module_mm or quality.datamatrix_module_mm
            quiet = el.quiet_modules if el.quiet_modules is not None else quality.datamatrix_quiet_modules
            probe = datamatrix_fragment(value, el.x_mm, el.y_mm, module, quiet)
            frag = probe
            if template_mode or template_codes_mode:
                template_holes.append(code_hole_path(probe.rects, el.x_mm, el.y_mm, effective.kerf_compensation_mm))
                template_protected_area += area_of_rects(probe.rects)
                continue
            if island_mode:
                frag = negative_background_fragment(probe, el.x_mm, el.y_mm, effective.field_margin_mm, effective.kerf_compensation_mm)
                _warn_negative_field_bounds((el.x_mm-effective.field_margin_mm, el.y_mm-effective.field_margin_mm, frag.width_mm, frag.height_mm), template, "DataMatrix", warnings)
                field_area = (probe.width_mm + 2*effective.field_margin_mm) * (probe.height_mm + 2*effective.field_margin_mm)
                estimated_ablated += max(0.0, field_area - area_of_rects(probe.rects))
            elif legacy_negative:
                frag = negative_background_fragment(probe, el.x_mm, el.y_mm)
            nodes.append(DocumentNode(element_id, layer, frag.svg, title=value,
                                      transform=rotation_transform(el.rotation_deg, el.x_mm + probe.width_mm/2, el.y_mm + probe.height_mm/2)))
            code_boxes.append((element_id, el.x_mm, el.y_mm, probe.width_mm, probe.height_mm))
            if el.x_mm + probe.width_mm > template.width_mm + 0.01 or el.y_mm + probe.height_mm > template.height_mm + 0.01:
                warnings.append(f"DataMatrix '{value}' sale de los límites de la plantilla")

        elif el.kind == "image":
            prepared = prepare_image_element(
                data_uri=el.image_data_uri or "", x_mm=el.x_mm, y_mm=el.y_mm,
                width_mm=el.width_mm or 1.0, height_mm=el.height_mm or 1.0,
                processing=el.image_processing, threshold=el.image_threshold,
                dpi=el.image_dpi, preserve_aspect=el.image_preserve_aspect,
            )
            warnings.extend(prepared.warnings)
            warnings.append(
                f"Imagen '{el.label or element_id}': no participa en el preflight de QR/barcode; "
                "su calidad física queda PENDIENTE DE ACEPTACIÓN sobre material/máquina real."
            )
            image_boxes.append((element_id, prepared.x_mm, prepared.y_mm, prepared.width_mm, prepared.height_mm))
            nodes.append(DocumentNode(
                element_id, layer, prepared.svg, title=el.image_source_name or el.label or "image",
                transform=rotation_transform(
                    el.rotation_deg, prepared.x_mm + prepared.width_mm/2, prepared.y_mm + prepared.height_mm/2
                ),
            ))
            if prepared.x_mm < -0.01 or prepared.y_mm < -0.01 or prepared.x_mm + prepared.width_mm > template.width_mm + 0.01 or prepared.y_mm + prepared.height_mm > template.height_mm + 0.01:
                warnings.append(f"Imagen '{el.label or element_id}' sale de los límites de la plantilla")

        elif el.kind == "rect":
            rw, rh = el.width_mm or 1.0, el.height_mm or 1.0
            hole = rect_stroke_path(el.x_mm, el.y_mm, rw, rh, el.stroke_mm)
            if template_mode:
                template_holes.append(hole)
                continue
            if island_mode:
                field_rect = bounds_with_margin(el.x_mm-el.stroke_mm/2, el.y_mm-el.stroke_mm/2,
                                                rw+el.stroke_mm, rh+el.stroke_mm, effective.field_margin_mm)
                _warn_negative_field_bounds(field_rect, template, "rectángulo", warnings)
                svg = _negative_island_svg(field_rect, hole)
                estimated_ablated += field_rect[2] * field_rect[3]
            else:
                svg = (f'<rect x="{el.x_mm:.4f}" y="{el.y_mm:.4f}" width="{rw:.4f}" height="{rh:.4f}" '
                       f'fill="none" stroke="#000" stroke-width="{el.stroke_mm:.4f}"/>')
            nodes.append(DocumentNode(element_id, layer, svg,
                                      transform=rotation_transform(el.rotation_deg, el.x_mm+rw/2, el.y_mm+rh/2)))

        elif el.kind == "line":
            lw, lh = el.width_mm or 1.0, el.height_mm or 0.0
            hole = line_stroke_path(el.x_mm, el.y_mm, el.x_mm+lw, el.y_mm+lh, el.stroke_mm)
            if template_mode:
                template_holes.append(hole)
                continue
            if island_mode:
                x0, x1 = sorted((el.x_mm, el.x_mm+lw)); y0, y1 = sorted((el.y_mm, el.y_mm+lh))
                field_rect = bounds_with_margin(x0-el.stroke_mm/2, y0-el.stroke_mm/2,
                                                max(el.stroke_mm, x1-x0+el.stroke_mm),
                                                max(el.stroke_mm, y1-y0+el.stroke_mm), effective.field_margin_mm)
                _warn_negative_field_bounds(field_rect, template, "línea", warnings)
                svg = _negative_island_svg(field_rect, hole)
                estimated_ablated += field_rect[2] * field_rect[3]
            else:
                svg = (f'<line x1="{el.x_mm:.4f}" y1="{el.y_mm:.4f}" x2="{el.x_mm+lw:.4f}" y2="{el.y_mm+lh:.4f}" '
                       f'stroke="#000" stroke-width="{el.stroke_mm:.4f}"/>')
            nodes.append(DocumentNode(element_id, layer, svg,
                                      transform=rotation_transform(el.rotation_deg, el.x_mm+lw/2, el.y_mm+lh/2)))

    # WHY: La caja del símbolo incluye su quiet zone generada; si una imagen la invade
    # el código puede verse intacto pero perder el margen óptico necesario para leer.
    for image_id, ix, iy, iw, ih in image_boxes:
        for code_id, cx, cy, cw, ch in code_boxes:
            overlap = not (ix + iw <= cx or cx + cw <= ix or iy + ih <= cy or cy + ch <= iy)
            if overlap:
                warnings.append(
                    f"Imagen '{image_id}' invade el área/quiet zone del código '{code_id}'. "
                    "Sepárelos antes de considerar el diseño listo para producción."
                )

    if template_holes:
        outer = f"M 0.0000 0.0000 h {template.width_mm:.4f} v {template.height_mm:.4f} h {-template.width_mm:.4f} z"
        path = f"{outer} {' '.join(template_holes)}"
        field_node = DocumentNode(registry.reserve("negative_template_field"), "layer_background",
                                  f'<path d="{path}" fill="#000" fill-rule="evenodd"/>',
                                  title="NEGATIVE TEMPLATE FIELD")
        canvas_area = template.width_mm * template.height_mm
        if effective.polarity_scope == "all":
            # Exact hole area of outlined text/arbitrary strokes is deliberately not
            # estimated with another geometry engine.  Use canvas area as a conservative
            # upper-bound metric for heat/ablation warning, not as a material recipe.
            estimated_ablated = canvas_area
            # Deliberately one fused node: element-level structure cannot truthfully be preserved.
            nodes = [field_node]
            warnings.append("Campo negativo de plantilla: la geometría interna se fusionó en un único trazado; los IDs de elementos individuales no se conservan en este artefacto.")
        else:
            estimated_ablated = max(0.0, canvas_area - template_protected_area)
            # codes+template is a deliberate TWO-STAGE artifact.  Positive text/geometry
            # remains in semantic layers so the operator can assign a separate pass in
            # LightBurn/Sculpfun Space if desired.  One-pass engraving cannot create the
            # intended depth difference and is therefore never described as automatic.
            nodes.insert(0, field_node)
            warnings.append("Campo de plantilla + sólo códigos: archivo de DOS ETAPAS. La capa de fondo y las capas positivas requieren operaciones separadas en el software de la máquina.")

    return nodes, warnings, resolved, element_ids, (estimated_ablated if effective.is_negative else None)


# WHY: Es el único punto público que compone plantilla + datos + modo físico en un SVG trazable y reproducible.
def render_template(
    template: TemplateSpec,
    quality: QualityProfile,
    data: Mapping[str, str],
    mode: str = "production",
    text_as_paths: bool = False,
    record_id: str = "",
    marking_mode_override: MarkingMode | None = None,
) -> RenderedMark:
    effective = effective_marking_mode(template.marking_mode, marking_mode_override)
    validate_marking_mode_for_render(effective, mode)
    registry = IdRegistry()
    nodes, warnings, resolved, element_ids, estimated = build_mark_nodes(
        template, quality, data, registry,
        text_as_paths=text_as_paths,
        marking_mode=effective,
        svg_mode=mode,
    )
    metadata = {
        "template_id": template.id,
        "template_version": template.version,
        "generated_by": GENERATOR_NAME,
        "generated_version": GENERATOR_VERSION,
        "units": "mm",
        "svg_mode": mode,
        "polarity": effective.polarity,
        "polarity_scope": effective.polarity_scope,
        "negative_field": effective.negative_field,
        "field_margin_mm": f"{effective.field_margin_mm:.4f}",
        "kerf_compensation_mm": f"{effective.kerf_compensation_mm:.4f}",
        "requires_secondary_operation": "true" if (effective.is_negative and effective.polarity_scope == "codes" and effective.negative_field == "template") else "false",
    }
    if record_id:
        metadata["record_id"] = record_id
    if text_as_paths:
        metadata["text_outline_font"] = OUTLINE_FONT_NAME
    if effective.validated_on:
        metadata["validated_on"] = effective.validated_on[:300]
    builder = SvgDocumentBuilder(template.width_mm, template.height_mm, mode=mode, metadata=metadata)
    for node in nodes:
        builder.add(node)
    canvas_area = template.width_mm * template.height_mm
    ratio = (estimated / canvas_area) if estimated is not None and canvas_area > 0 else None
    if ratio is not None and ratio >= 0.45:
        warnings.append(
            f"El modo invertido estima ablación sobre ~{ratio*100:.0f}% del lienzo; puede aumentar tiempo/calor. "
            "Pruebe sobre descarte antes de producción."
        )
    return RenderedMark(
        svg=builder.build(), width_mm=template.width_mm, height_mm=template.height_mm,
        warnings=warnings, resolved=resolved, element_ids=element_ids,
        marking_mode=effective.model_dump(), estimated_ablation_mm2=estimated,
        estimated_ablation_ratio=ratio,
    )
