#!/usr/bin/env python3
"""Generate audit evidence for the in-app barcode/QR legibility preflight."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.code_quality import assess_template_codes
from app.config_loader import load_quality_profiles, load_scanners, load_templates

OUT = ROOT / "qa" / "output"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    templates = load_templates()
    qualities = load_quality_profiles()
    scanner = load_scanners()["steren_com_597"]
    cases = [
        ("INOVA Code128", templates["inova_quantum_code128_v1"], {"manufacturer_id": "Q00525499"}),
        ("Sercel Code128", templates["sercel_dfu_code128_v1"], {"manufacturer_id": "4281847"}),
        ("Teléfono QR", templates["phone_qr_economic_v1"], {"economic_number": "TEL-0037"}),
    ]
    report = {"scanner": scanner.id, "cases": []}
    ok = True
    for name, template, data in cases:
        result = assess_template_codes(template, qualities[template.quality_profile], data, scanner=scanner)
        report["cases"].append({"name": name, "template": template.id, "result": result})
        ok = ok and result["overall"] in {"ROBUSTO", "ACEPTABLE"}

    fragile = deepcopy(templates["inova_quantum_code128_v1"])
    fragile.elements[0].module_mm = 0.12
    fragile_result = assess_template_codes(
        fragile,
        qualities[fragile.quality_profile],
        {"manufacturer_id": "Q00525499"},
        scanner=scanner,
        digital_stress=False,
    )
    report["deliberately_undersized"] = fragile_result
    ok = ok and fragile_result["overall"] == "FRAGIL"
    report["status"] = "PASS" if ok else "FAIL"

    (OUT / "quality_preflight_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# QA — preflight de legibilidad",
        "",
        f"Estado: **{report['status']}** · lector: `{scanner.id}`",
        "",
        "| Caso | Clasificación | Resultado digital |",
        "|---|---|---|",
    ]
    for case in report["cases"]:
        result = case["result"]
        symbol = result["results"][0]
        digital = symbol["digital"]
        digital_text = f"{digital.get('passed', 0)}/{digital.get('total', 0)}" if digital.get("available") else "no disponible"
        lines.append(f"| {case['name']} | {result['overall']} | {digital_text} |")
    lines += [
        f"| Control módulo 0.12 mm | {fragile_result['overall']} | estructural |",
        "",
        "La prueba digital no sustituye grabado real + lector físico.",
    ]
    (OUT / "quality_preflight_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "cases": [
            {
                "name": c["name"],
                "overall": c["result"]["overall"],
                "digital": [
                    c["result"]["results"][0]["digital"].get("passed", 0),
                    c["result"]["results"][0]["digital"].get("total", 0),
                ],
            }
            for c in report["cases"]
        ],
        "undersized": fragile_result["overall"],
    }, indent=2, ensure_ascii=False))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
