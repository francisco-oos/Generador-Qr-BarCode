"""Legibility preflight for generated QR/barcodes.

The goal is not to replace the physical acceptance test with the shop scanner.
Instead, this module catches preventable digital/layout mistakes before a mark is
sent to LightBurn/Sculpfun Space: unsupported symbology, undersized modules,
missing margins, codes outside the canvas, and codes that fail a small optical
stress simulation after rasterization.

WHY: a visually plausible code can still be unscannable.  The preflight keeps
production geometry and scan-readiness connected without taking control of the
laser itself.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from .barcode_engine import (
    code128_fragment,
    code39_fragment,
    datamatrix_fragment,
    qr_fragment,
    resolve_value,
)
from .exporters import svg_to_png
from .models import QualityProfile, ScannerProfile, TemplateSpec
from .template_engine import apply_input_rules


# WHY: Encapsula las medidas físicas reales del símbolo para evaluar lo que efectivamente se exportará.
@dataclass(frozen=True)
class SymbolGeometry:
    kind: str
    value: str
    module_mm: float
    width_mm: float
    height_mm: float
    quiet_modules: int
    svg: str


# WHY: Mantiene el mapeo de nombres del motor a nomenclatura habitual de lectores en un único punto.
_SYMBOLOGY_LABELS = {
    "code128": "Code 128",
    "code39": "Code 39",
    "qr": "QR",
    "datamatrix": "Data Matrix",
}

# WHY: Nombres que devuelve zbar/pyzbar cuando el decodificador opcional está disponible.
_PYZBAR_TYPES = {
    "code128": "CODE128",
    "code39": "CODE39",
    "qr": "QRCODE",
}


# WHY: Reutiliza exactamente los generadores de producción y evita un cálculo de calidad desconectado del SVG real.
def _fragment_for_element(el, quality: QualityProfile, value: str) -> SymbolGeometry:
    if el.kind == "code128":
        module = el.module_mm or quality.code128_module_mm
        quiet = quality.code128_quiet_modules
        height = el.height_mm or quality.code128_bar_height_mm
        f = code128_fragment(value, 0, 0, module, height, quiet)
    elif el.kind == "code39":
        module = el.module_mm or quality.code128_module_mm
        quiet = quality.code128_quiet_modules
        height = el.height_mm or quality.code128_bar_height_mm
        f = code39_fragment(value, 0, 0, module, height, quiet)
    elif el.kind == "qr":
        module = el.module_mm or quality.qr_module_mm
        quiet = quality.qr_quiet_modules
        f = qr_fragment(value, 0, 0, module, quiet, el.error_correction)
    elif el.kind == "datamatrix":
        module = el.module_mm or quality.datamatrix_module_mm
        quiet = quality.datamatrix_quiet_modules
        f = datamatrix_fragment(value, 0, 0, module, quiet)
    else:  # pragma: no cover - caller filters kinds
        raise ValueError(f"unsupported quality-check kind: {el.kind}")
    return SymbolGeometry(el.kind, value, module, f.width_mm, f.height_mm, quiet, f.svg)


# WHY: Aísla un símbolo con fondo blanco para someterlo a decodificación y degradaciones sin ruido de otros elementos.
def _standalone_svg(g: SymbolGeometry) -> str:
    # The barcode generators already include their required quiet zone inside the
    # fragment dimensions.  A white background makes rasterization deterministic.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{g.width_mm:.4f}mm" '
        f'height="{g.height_mm:.4f}mm" viewBox="0 0 {g.width_mm:.4f} {g.height_mm:.4f}">'
        f'<rect x="0" y="0" width="{g.width_mm:.4f}" height="{g.height_mm:.4f}" fill="#fff"/>'
        f'{g.svg}</svg>'
    )


def _decode_with_pyzbar(image: Image.Image) -> tuple[list[dict[str, Any]], str | None]:
    """Decode opportunistically; missing native zbar must never break Marking Studio."""
    try:
        from pyzbar.pyzbar import decode  # imported lazily for cross-platform resilience
    except Exception as exc:  # libzbar can be absent on Linux/macOS even if pyzbar is installed
        return [], f"Decodificador digital no disponible: {exc}"
    out: list[dict[str, Any]] = []
    try:
        for item in decode(image):
            try:
                text = item.data.decode("utf-8")
            except UnicodeDecodeError:
                text = item.data.decode("latin-1")
            out.append({"text": text, "type": item.type})
    except Exception as exc:
        return [], f"El decodificador digital falló: {exc}"
    return out, None


def _variants(image: Image.Image):
    """Small optical stress set: useful as a preflight, intentionally not an ISO verifier."""
    yield "original", image
    yield "reducción 75%", image.resize((max(1, image.width * 3 // 4), max(1, image.height * 3 // 4)), Image.Resampling.LANCZOS)
    yield "reducción 50%", image.resize((max(1, image.width // 2), max(1, image.height // 2)), Image.Resampling.LANCZOS)
    yield "desenfoque 0.6", image.filter(ImageFilter.GaussianBlur(radius=0.6))
    yield "contraste 70%", ImageEnhance.Contrast(image).enhance(0.70)
    yield "rotación 2°", image.rotate(2.0, expand=True, fillcolor="white", resample=Image.Resampling.BICUBIC)
    scratched = image.copy()
    d = ImageDraw.Draw(scratched)
    h = max(1, scratched.height // 100)
    y = scratched.height // 2
    d.rectangle((0, y, scratched.width, y + h), fill="white")
    yield "abrasión fina", scratched


# WHY: Compara cada simbología contra el módulo conservador declarado por el perfil de calidad elegido.
def _profile_reference_module(kind: str, quality: QualityProfile) -> float:
    if kind in {"code128", "code39"}:
        return quality.code128_module_mm
    if kind == "qr":
        return quality.qr_module_mm
    return quality.datamatrix_module_mm


# WHY: Impide recomendar una simbología que el lector seleccionado no declara soportar.
def _scanner_support(scanner: ScannerProfile | None, kind: str) -> tuple[bool | None, str]:
    if scanner is None:
        return None, "Sin lector objetivo seleccionado"
    label = _SYMBOLOGY_LABELS[kind].lower().replace(" ", "")
    supported = {s.lower().replace(" ", "") for s in scanner.symbologies}
    ok = label in supported
    if kind == "qr":
        ok = ok or scanner.supports_qr
    if kind == "datamatrix":
        ok = ok or scanner.supports_datamatrix
    return ok, f"{scanner.name}: {'compatible' if ok else 'simbología no declarada'}"


def assess_template_codes(
    template: TemplateSpec,
    quality: QualityProfile,
    data: Mapping[str, str],
    capture_mode: str = "manual",
    scanner: ScannerProfile | None = None,
    dpi: int | None = None,
    digital_stress: bool = True,
) -> dict[str, Any]:
    """Return per-code structural and optional decode robustness results.

    Classification is deliberately conservative and relative to the template's
    quality profile.  It does *not* claim ISO/IEC verification and cannot measure
    contrast of a future physical laser mark.
    """
    normalized = apply_input_rules(template, data, capture_mode=capture_mode)
    dpi = dpi or quality.render_dpi
    results: list[dict[str, Any]] = []

    for index, el in enumerate(template.elements):
        if el.kind not in _SYMBOLOGY_LABELS:
            continue
        value = resolve_value(normalized, el.source, el.literal)
        item: dict[str, Any] = {
            "index": index,
            "label": el.label or _SYMBOLOGY_LABELS[el.kind],
            "kind": el.kind,
            "value": value,
            "scanner": None,
            "checks": [],
            "digital": {"available": False, "variants": [], "passed": 0, "total": 0},
        }
        if not value:
            item["classification"] = "NO_LEGIBLE"
            item["checks"].append({"level": "bad", "message": "El valor del código está vacío."})
            results.append(item)
            continue

        g = _fragment_for_element(el, quality, value)
        ref_module = _profile_reference_module(el.kind, quality)
        ratio = g.module_mm / ref_module if ref_module else 1.0
        item.update({
            "module_mm": round(g.module_mm, 4),
            "reference_module_mm": round(ref_module, 4),
            "module_ratio": round(ratio, 3),
            "symbol_width_mm": round(g.width_mm, 3),
            "symbol_height_mm": round(g.height_mm, 3),
            "quiet_modules": g.quiet_modules,
        })

        if ratio >= 1.0:
            item["checks"].append({"level": "ok", "message": f"Módulo {g.module_mm:.2f} mm: cumple el perfil conservador {quality.name}."})
        elif ratio >= 0.80:
            item["checks"].append({"level": "warn", "message": f"Módulo {g.module_mm:.2f} mm por debajo del perfil {ref_module:.2f} mm; conserve margen antes de producción."})
        else:
            item["checks"].append({"level": "warn", "message": f"Módulo {g.module_mm:.2f} mm muy reducido frente al perfil {ref_module:.2f} mm; trátelo como frágil aunque decodifique en pantalla."})

        # Position uses actual symbol dimensions, not the editor's nominal bounding box.
        within = el.x_mm + g.width_mm <= template.width_mm + 0.01 and el.y_mm + g.height_mm <= template.height_mm + 0.01
        item["checks"].append({"level": "ok" if within else "bad", "message": "Símbolo dentro del área de la plantilla." if within else "El símbolo sale del área física de la plantilla."})
        if el.width_mm and g.width_mm > el.width_mm + 0.01:
            item["checks"].append({"level": "warn", "message": f"El símbolo real mide {g.width_mm:.1f} mm y supera la caja visual de {el.width_mm:.1f} mm."})

        support, support_text = _scanner_support(scanner, el.kind)
        item["scanner"] = {"supported": support, "message": support_text}
        if support is False:
            item["checks"].append({"level": "bad", "message": support_text})
        elif support is True:
            item["checks"].append({"level": "ok", "message": support_text})
        if scanner and scanner.minimum_print_contrast_percent is not None:
            item["checks"].append({"level": "info", "message": f"El lector declara contraste mínimo aproximado de {scanner.minimum_print_contrast_percent:g}%; debe comprobarse sobre la pieza real."})

        if digital_stress and el.kind in _PYZBAR_TYPES:
            svg = _standalone_svg(g)
            try:
                png = svg_to_png(svg, g.width_mm, g.height_mm, dpi=dpi)
                image = Image.open(io.BytesIO(png)).convert("RGB")
                expected_type = _PYZBAR_TYPES[el.kind]
                variants = []
                decoder_error = None
                for name, variant in _variants(image):
                    decoded, err = _decode_with_pyzbar(variant)
                    if err:
                        decoder_error = err
                        break
                    ok = any(d["text"] == value and d["type"] == expected_type for d in decoded)
                    variants.append({"name": name, "pass": ok, "decoded": decoded})
                if decoder_error:
                    item["digital"].update({"available": False, "note": decoder_error})
                else:
                    passed = sum(1 for v in variants if v["pass"])
                    item["digital"] = {"available": True, "variants": variants, "passed": passed, "total": len(variants)}
                    pristine = bool(variants and variants[0]["pass"])
                    item["checks"].append({
                        "level": "ok" if pristine and passed >= max(5, len(variants)-2) else ("warn" if pristine else "bad"),
                        "message": f"Prueba digital: {passed}/{len(variants)} variantes conservan exactamente '{value}'.",
                    })
            except Exception as exc:
                item["digital"].update({"available": False, "note": f"No fue posible ejecutar prueba digital: {exc}"})
        elif digital_stress:
            item["digital"].update({"available": False, "note": "Prueba digital integrada no disponible para esta simbología; use el lector físico."})

        levels = [c["level"] for c in item["checks"]]
        digital = item["digital"]
        if "bad" in levels or (digital.get("available") and digital.get("variants") and not digital["variants"][0]["pass"]):
            classification = "NO_LEGIBLE"
        elif "warn" in levels:
            classification = "FRAGIL"
        elif digital.get("available"):
            rate = digital["passed"] / max(1, digital["total"])
            if rate >= 0.85:
                classification = "ROBUSTO"
            elif rate >= 0.55:
                classification = "ACEPTABLE"
            else:
                classification = "FRAGIL"
        else:
            classification = "ACEPTABLE"
        item["classification"] = classification
        results.append(item)

    order = {"ROBUSTO": 0, "ACEPTABLE": 1, "FRAGIL": 2, "NO_LEGIBLE": 3}
    overall = max((r["classification"] for r in results), key=lambda x: order[x], default="SIN_CODIGOS")
    return {
        "overall": overall,
        "results": results,
        "notes": [
            "La prueba digital valida geometría/rasterización y degradaciones simples; no certifica el grabado físico.",
            "No permita que el software de impresión/maquetación reescale el SVG: exporte/importar a tamaño físico 100%.",
            "La aceptación final exige grabado real + lectura repetida con el lector objetivo sobre el material final.",
        ],
    }
