from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
from pyzbar.pyzbar import decode

from app.config_loader import load_quality_profiles, load_templates
from app.exporters import svg_to_png
from app.template_engine import render_template

OUT = ROOT / "qa" / "output"
OUT.mkdir(parents=True, exist_ok=True)

CASES = [
    ("inova_code128", "inova_quantum_code128_v1", {"manufacturer_id": "Q00525499"}, "Q00525499", "CODE128"),
    ("sercel_code128", "sercel_dfu_code128_v1", {"manufacturer_id": "4281847"}, "4281847", "CODE128"),
    ("phone_qr", "phone_qr_economic_v1", {"economic_number": "TEL-0037", "asset_id": "PHONE-000037"}, "PHONE-000037", "QRCODE"),
    ("generic_qr", "generic_asset_qr_v1", {"asset_id": "RADIO-000184"}, "RADIO-000184", "QRCODE"),
]


def decode_text(im: Image.Image) -> list[dict]:
    results = []
    for item in decode(im):
        try:
            text = item.data.decode("utf-8")
        except UnicodeDecodeError:
            text = item.data.decode("latin-1")
        results.append({"text": text, "type": item.type, "quality": getattr(item, "quality", None)})
    return results


def transformations(im: Image.Image):
    yield "pristine", im
    small = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.Resampling.LANCZOS)
    yield "downscale_50pct", small
    yield "blur_0_6", im.filter(ImageFilter.GaussianBlur(radius=0.6))
    yield "blur_1_0", im.filter(ImageFilter.GaussianBlur(radius=1.0))
    yield "rotation_2deg", im.rotate(2.0, expand=True, fillcolor="white", resample=Image.Resampling.BICUBIC)
    yield "low_contrast_55pct", ImageEnhance.Contrast(im).enhance(0.55)
    scratched = im.copy()
    d = ImageDraw.Draw(scratched)
    # Thin horizontal abrasion across about 1% of image height. A 1D scanner can
    # still find intact scanlines; QR error correction should tolerate the loss.
    h = max(1, im.height // 100)
    y = im.height // 2
    d.rectangle((0, y, im.width, y + h), fill="white")
    yield "thin_abrasion", scratched


def main() -> int:
    templates = load_templates()
    qualities = load_quality_profiles()
    report = {"generated_at_epoch": time.time(), "dpi": 600, "cases": []}
    total = passed = 0
    for name, tid, data, expected, expected_type in CASES:
        t = templates[tid]
        q = qualities[t.quality_profile]
        rendered = render_template(t, q, data)
        png = svg_to_png(rendered.svg, rendered.width_mm, rendered.height_mm, 600)
        base_path = OUT / f"{name}_pristine.png"
        base_path.write_bytes(png)
        im = Image.open(base_path).convert("RGB")
        case = {"name": name, "template": tid, "expected": expected, "expected_type": expected_type, "variants": []}
        for variant_name, variant_im in transformations(im):
            dec = decode_text(variant_im)
            ok = any(d["text"] == expected and d["type"] == expected_type for d in dec)
            total += 1
            passed += int(ok)
            if variant_name != "pristine":
                variant_im.save(OUT / f"{name}_{variant_name}.png")
            case["variants"].append({"variant": variant_name, "pass": ok, "decoded": dec})
        report["cases"].append(case)
    report["summary"] = {"passed": passed, "total": total, "pass_rate": passed / total if total else 0}
    (OUT / "scan_simulation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Simulación de lectura de códigos",
        "",
        f"Resultado global: **{passed}/{total} ({passed/total:.1%})** de variantes decodificadas correctamente.",
        "",
        "Esta prueba valida el pipeline digital (render → rasterización → decodificación) y tolerancia a degradaciones ópticas simples. No sustituye una verificación ISO/IEC ni una prueba física sobre la carcasa grabada.",
        "",
        "| Caso | Plantilla | Variante | Resultado |",
        "|---|---|---|---|",
    ]
    for case in report["cases"]:
        for v in case["variants"]:
            lines.append(f"| {case['name']} | {case['template']} | {v['variant']} | {'PASS' if v['pass'] else 'FAIL'} |")
    (OUT / "scan_simulation_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0 if passed == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
