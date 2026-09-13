#!/usr/bin/env python3
"""Validate production SVGs with independent parsers and Inkscape when available."""
from __future__ import annotations
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.config_loader import load_templates, load_quality_profiles, load_machines, load_jigs
from app.template_engine import render_template
from app.batch_engine import render_batch
from app.models import BatchAssignment
from app.exporters import svg_to_png
from app.calibration import calibration_target_svg
OUT=ROOT/'qa'/'output'; OUT.mkdir(parents=True,exist_ok=True)

def main():
    templates=load_templates(); q=load_quality_profiles(); checks=[]
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); ink=shutil.which('inkscape')
        for t in templates.values():
            data=dict(t.metadata.get('example_data') or {})
            for f in t.expected_fields: data.setdefault(f, f'TEST-{f.upper()}')
            mark=render_template(t,q[t.quality_profile],data)
            ET.fromstring(mark.svg); svg_to_png(mark.svg,mark.width_mm,mark.height_mm,300)
            item={'template':t.id,'xml':'PASS','svglib':'PASS','inkscape':'SKIP' if not ink else 'PASS'}
            if ink:
                src=td/f'{t.id}.svg'; png=td/f'{t.id}.png'; src.write_text(mark.svg,encoding='utf-8')
                cp=subprocess.run([ink,str(src),'--export-type=png',f'--export-filename={png}'],capture_output=True,text=True,timeout=30)
                if cp.returncode or not png.exists() or png.stat().st_size<100: item['inkscape']='FAIL'; item['inkscape_error']=cp.stderr[-500:]
            checks.append(item)
        # Full 12-position production SVG.
        t=templates['inova_quantum_code128_v1']; jig=load_jigs()['inova_tray_3x4_estimate']; m=load_machines()[jig.machine_profile_id]
        rows=[{'manufacturer_id':f'Q00{525499+i:06d}'} for i in range(12)]
        assignments=[BatchAssignment(slot_index=i,row_index=i,physical_id=rows[i]['manufacturer_id']) for i in range(12)]
        b=render_batch(m,jig,t,q[t.quality_profile],rows,assignments,True); ET.fromstring(b.svg); svg_to_png(b.svg,m.bed_width_mm,m.bed_height_mm,150)
        checks.append({'batch_12':'PASS','marks':len(b.manifest),'guide_in_production': 'GUIDES_DO_NOT_ENGRAVE' in b.svg})
        # Calibration target: must remain parseable and explicitly non-production.
        cal=calibration_target_svg(m,jig); ET.fromstring(cal)
        cal_item={'calibration_svg':'PASS','contains_warning':'CALIBRATION ONLY' in cal,'inkscape':'SKIP' if not ink else 'PASS'}
        if ink:
            src=td/'calibration.svg'; png=td/'calibration.png'; src.write_text(cal,encoding='utf-8')
            cp=subprocess.run([ink,str(src),'--export-type=png',f'--export-filename={png}'],capture_output=True,text=True,timeout=30)
            if cp.returncode or not png.exists() or png.stat().st_size<100:
                cal_item['inkscape']='FAIL'; cal_item['inkscape_error']=cp.stderr[-500:]
        checks.append(cal_item)
    fail=any(x.get('inkscape')=='FAIL' or x.get('guide_in_production') is True for x in checks)
    report={'status':'FAIL' if fail else 'PASS','inkscape':shutil.which('inkscape'),'checks':checks}
    (OUT/'svg_interop_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2)); raise SystemExit(1 if fail else 0)
if __name__=='__main__': main()
