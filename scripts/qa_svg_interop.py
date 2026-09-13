#!/usr/bin/env python3
"""Validate production SVGs with independent renderers, checking image content.

WHY (v0.7.0):
La version anterior consideraba PASS que Inkscape saliera con codigo 0 y dejara
un PNG de mas de 100 bytes.  Una lamina completamente negra cumplia ese criterio,
de modo que el informe podia declarar interoperabilidad sin haberla comprobado.

Ahora cada renderizador disponible debe producir una imagen con tinta real, con
las dimensiones fisicas esperadas y, cuando la simbologia lo permite, el dato
original debe recuperarse con un decodificador independiente.
"""
from __future__ import annotations
import io, json, shutil, subprocess, sys, tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.config_loader import load_templates, load_quality_profiles, load_machines, load_jigs
from app.template_engine import render_template
from app.batch_engine import render_batch
from app.models import BatchAssignment
from app.exporters import svg_to_png
from app.calibration import calibration_target_svg

OUT = ROOT / 'qa' / 'output'; OUT.mkdir(parents=True, exist_ok=True)
MM_PER_INCH = 25.4


# WHY: Sin componer el alfa sobre blanco, un PNG RGBA se convierte en una imagen
# negra y la prueba fallaria por un motivo inexistente.
def _flatten(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    if im.mode == 'RGBA':
        bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
    return im.convert('L')


# WHY: Criterio explicito de "la imagen contiene el dibujo", que es lo que faltaba.
def inspect_image(im: Image.Image, width_mm: float, height_mm: float, dpi: int) -> dict:
    a = np.array(im)
    ink = float((a < 128).mean())
    exp_w = width_mm / MM_PER_INCH * dpi
    exp_h = height_mm / MM_PER_INCH * dpi
    checks = {
        'size_px': list(im.size),
        'ink_ratio': round(ink, 6),
        'has_dark': bool(a.min() < 64),
        'has_light': bool(a.max() > 192),
        'width_within_2pct': abs(im.size[0] - exp_w) <= max(2.0, exp_w * 0.02),
        'height_within_2pct': abs(im.size[1] - exp_h) <= max(2.0, exp_h * 0.02),
    }
    checks['content_ok'] = bool(
        checks['has_dark'] and checks['has_light'] and 0.0005 < ink < 0.9
        and checks['width_within_2pct'] and checks['height_within_2pct']
    )
    return checks


# WHY: Decodificacion opcional; su ausencia se declara, no se disfraza de PASS.
def decode(im: Image.Image) -> list[str] | None:
    try:
        from pyzbar import pyzbar
    except Exception:
        return None
    try:
        return sorted(d.data.decode('utf-8', errors='replace') for d in pyzbar.decode(im))
    except Exception:
        return None


def renderers():
    out = {'svglib': lambda svg, w, h, dpi: svg_to_png(svg, w, h, dpi=dpi)}
    try:
        import cairosvg
        out['cairosvg'] = lambda svg, w, h, dpi: cairosvg.svg2png(bytestring=svg.encode(), dpi=dpi)
    except ImportError:
        pass
    return out


# WHY: Inkscape se ejecuta como proceso externo; su salida se inspecciona igual
# que la de cualquier otro renderizador en lugar de confiar en el codigo de salida.
def render_with_inkscape(svg: str, dpi: int) -> bytes | None:
    ink = shutil.which('inkscape')
    if not ink:
        return None
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / 'in.svg'; dst = Path(td) / 'out.png'
        src.write_text(svg, encoding='utf-8')
        cp = subprocess.run([ink, str(src), '--export-type=png', f'--export-dpi={dpi}',
                             f'--export-filename={dst}'], capture_output=True, text=True, timeout=60)
        if cp.returncode or not dst.exists():
            return None
        return dst.read_bytes()


def main() -> int:
    templates = load_templates(); q = load_quality_profiles()
    engines = renderers()
    inkscape_path = shutil.which('inkscape')
    checks: list[dict] = []
    failures: list[str] = []

    for t in templates.values():
        data = dict(t.metadata.get('example_data') or {})
        for f in t.expected_fields:
            data.setdefault(f, f'TEST-{f.upper()}')
        for mode in ('production', 'editable'):
            mark = render_template(t, q[t.quality_profile], data, mode=mode)
            item: dict = {'template': t.id, 'mode': mode}
            try:
                ET.fromstring(mark.svg); item['xml'] = 'PASS'
            except Exception as exc:
                item['xml'] = 'FAIL'; item['xml_error'] = str(exc); failures.append(f'{t.id}/{mode}: XML')
            import collections, re
            ids = re.findall(r'\bid="([^"]+)"', mark.svg)
            dup = {k: v for k, v in collections.Counter(ids).items() if v > 1}
            item['unique_ids'] = 'PASS' if not dup else 'FAIL'
            if dup:
                item['duplicate_ids'] = dup; failures.append(f'{t.id}/{mode}: ids duplicados')
            item['shared_resources'] = 'PASS' if 'url(#' not in mark.svg else 'FAIL'
            item['nested_svg'] = 'PASS' if mark.svg.count('<svg') == 1 else 'FAIL'
            for name, render in engines.items():
                try:
                    im = _flatten(render(mark.svg, mark.width_mm, mark.height_mm, 600))
                    insp = inspect_image(im, mark.width_mm, mark.height_mm, 600)
                    item[name] = 'PASS' if insp['content_ok'] else 'FAIL'
                    item[f'{name}_detail'] = insp
                    if not insp['content_ok']:
                        failures.append(f'{t.id}/{mode}: {name} sin contenido valido')
                except Exception as exc:
                    item[name] = 'FAIL'; item[f'{name}_error'] = str(exc)
                    failures.append(f'{t.id}/{mode}: {name} excepcion')
            png = render_with_inkscape(mark.svg, 600)
            if png is None:
                item['inkscape'] = 'NOT_TESTED' if not inkscape_path else 'FAIL'
                if inkscape_path:
                    failures.append(f'{t.id}/{mode}: inkscape no produjo imagen')
            else:
                insp = inspect_image(_flatten(png), mark.width_mm, mark.height_mm, 600)
                item['inkscape'] = 'PASS' if insp['content_ok'] else 'FAIL'
                item['inkscape_detail'] = insp
                if not insp['content_ok']:
                    failures.append(f'{t.id}/{mode}: inkscape sin contenido valido')
            checks.append(item)

    # Lote real de 12 posiciones con valores de longitud dispar.
    t = templates['inova_quantum_code128_v1']; jig = load_jigs()['inova_tray_3x4_estimate']
    m = load_machines()[jig.machine_profile_id]
    values = ['A1', 'Q00525499', 'Q00000000000000000012345', '4281847', 'Q1', 'Q00525500',
              'Q00525501', 'ABC-123', 'Q00525502', 'LONGVALUE-0000001', 'Q00525503', 'X9']
    rows = [{'manufacturer_id': v} for v in values]
    assignments = [BatchAssignment(slot_index=i, row_index=i, physical_id=v) for i, v in enumerate(values)]
    b = render_batch(m, jig, t, q[t.quality_profile], rows, assignments, True)
    ET.fromstring(b.svg)
    import collections, re
    ids = re.findall(r'\bid="([^"]+)"', b.svg)
    dup = {k: v for k, v in collections.Counter(ids).items() if v > 1}
    batch_item = {
        'batch_12_divergent_lengths': 'PASS' if not dup else 'FAIL',
        'marks': len(b.manifest),
        'duplicate_ids': dup,
        'guide_in_production': 'GUIDES_DO_NOT_ENGRAVE' in b.svg,
        'namespaces': len(set(re.findall(r'id="(mark_\d{4})"', b.svg))),
    }
    if dup:
        failures.append('lote: ids duplicados')
    if 'GUIDES_DO_NOT_ENGRAVE' in b.svg:
        failures.append('lote: guias visuales dentro del archivo productivo')
    for name, render in engines.items():
        im = _flatten(render(b.svg, m.bed_width_mm, m.bed_height_mm, 400))
        insp = inspect_image(im, m.bed_width_mm, m.bed_height_mm, 400)
        decoded = decode(im)
        batch_item[f'{name}_content'] = 'PASS' if insp['content_ok'] else 'FAIL'
        if decoded is None:
            batch_item[f'{name}_decode'] = 'NOT_TESTED (pyzbar/libzbar ausente)'
        else:
            missing = sorted(set(values) - set(decoded))
            batch_item[f'{name}_decode'] = 'PASS' if not missing else 'FAIL'
            batch_item[f'{name}_missing'] = missing
            if missing:
                failures.append(f'lote: {name} no decodifico {missing}')
        if not insp['content_ok']:
            failures.append(f'lote: {name} sin contenido valido')
    checks.append(batch_item)

    cal = calibration_target_svg(m, jig); ET.fromstring(cal)
    checks.append({'calibration_svg': 'PASS', 'contains_warning': 'CALIBRATION ONLY' in cal})

    report = {
        'status': 'FAIL' if failures else 'PASS',
        'inkscape': inkscape_path or 'NOT_AVAILABLE_ON_THIS_HOST',
        'renderers': sorted(engines),
        'failures': failures,
        'checks': checks,
        'criteria': (
            'Un renderizador se considera PASS solo si la imagen tiene tinta, no es '
            'uniformemente oscura o clara y conserva las dimensiones fisicas dentro del 2%. '
            'El codigo de salida del proceso no es criterio suficiente.'
        ),
    }
    (OUT / 'svg_interop_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
