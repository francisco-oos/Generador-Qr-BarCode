#!/usr/bin/env python3
"""Decode a freshly generated 3x4 bed SVG, not a stored image.

WHY (v0.7.0):
La version anterior decodificaba ``samples/output/inova_batch_12_300dpi.png``,
un archivo precompilado en el repositorio.  Esa prueba podia seguir en PASS
aunque el motor se hubiera roto, porque nunca ejercitaba la cadena productiva.

Ahora la cadena es completa y ocurre dentro de la prueba:
    plantilla + datos -> render_batch -> SVG -> renderizador -> PNG -> decoder.
Los archivos de ``samples/`` quedan como material de apoyo, no como evidencia.
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.config_loader import load_templates, load_quality_profiles, load_jigs, load_machines
from app.batch_engine import render_batch
from app.exporters import svg_to_png
from app.models import BatchAssignment

OUT = ROOT / 'qa' / 'output'; OUT.mkdir(parents=True, exist_ok=True)

# WHY: Se mezclan longitudes cortas, medias y extremas porque el defecto de
# recursos compartidos solo se manifiesta cuando las geometrias divergen.
EXPECTED = [f"Q00{525499 + i:06d}" for i in range(9)] + ["A1", "Q1", "LONGVALUE-0000001"]


# WHY: Compone el alfa sobre blanco; de lo contrario un PNG RGBA se lee como negro.
def _flatten(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    if im.mode == 'RGBA':
        bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
    return im.convert('L')


def main() -> int:
    from pyzbar.pyzbar import decode

    templates = load_templates(); q = load_quality_profiles()
    template = templates['inova_quantum_code128_v1']
    jig = load_jigs()['inova_tray_3x4_estimate']
    machine = load_machines()[jig.machine_profile_id]
    rows = [{'manufacturer_id': v} for v in EXPECTED]
    assignments = [BatchAssignment(slot_index=i, row_index=i, physical_id=v)
                   for i, v in enumerate(EXPECTED)]

    batch = render_batch(machine, jig, template, q[template.quality_profile],
                         rows, assignments, True)

    results: dict[str, dict] = {}
    renderers = {'svglib': lambda svg: svg_to_png(svg, machine.bed_width_mm, machine.bed_height_mm, dpi=400)}
    try:
        import cairosvg
        renderers['cairosvg'] = lambda svg: cairosvg.svg2png(bytestring=svg.encode(), dpi=400)
    except ImportError:
        pass

    for name, render in renderers.items():
        im = _flatten(render(batch.svg))
        found = [x.data.decode('utf-8', errors='replace') for x in decode(im) if x.type == 'CODE128']
        results[name] = {
            'decoded': sorted(found),
            'missing': sorted(set(EXPECTED) - set(found)),
            'unexpected': sorted(set(found) - set(EXPECTED)),
            'status': 'PASS' if set(found) == set(EXPECTED) and len(found) == len(EXPECTED) else 'FAIL',
        }

    report = {
        'source': 'regenerated in this run (no precompiled sample used)',
        'expected': EXPECTED,
        'renderers': results,
        'status': 'PASS' if all(r['status'] == 'PASS' for r in results.values()) else 'FAIL',
    }
    (OUT / 'batch_decode_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
