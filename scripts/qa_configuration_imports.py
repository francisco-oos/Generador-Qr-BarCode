#!/usr/bin/env python3
"""Exercise real sample configuration files through the production importers."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.machine_bridge import import_configuration_bytes
OUT=ROOT/'qa'/'output'; OUT.mkdir(parents=True,exist_ok=True)
CASES=[
 ('samples/config/EXAMPLE_existing_shop_material.clb','lightburn_clb'),
 ('samples/config/EXAMPLE_material_test_presets.lbmt','lightburn_material_test'),
 ('samples/config/EXAMPLE_LaserGRBL_UserMaterials.psh','lasergrbl_material_db'),
 ('samples/config/EXAMPLE_grbl_readonly_dump.txt','grbl_text'),
]
results=[]
for rel,expected in CASES:
    p=ROOT/rel
    parsed=import_configuration_bytes(p.name,p.read_bytes())
    ok=parsed.source_type==expected
    results.append({
      'file':rel,'expected':expected,'actual':parsed.source_type,'pass':ok,
      'summary':parsed.summary,'settings_count':len(parsed.settings),
      'material_presets':len(parsed.material_presets),'warnings':parsed.warnings,
    })
report={'status':'PASS' if all(x['pass'] for x in results) else 'FAIL','cases':results}
(OUT/'configuration_import_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(0 if report['status']=='PASS' else 1)
