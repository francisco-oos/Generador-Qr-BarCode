from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.batch_engine import render_batch, slot_positions
from app.calibration import calibration_target_svg
from app.config_loader import load_jigs, load_machines, load_quality_profiles, load_templates
from app.exporters import build_batch_zip, svg_to_png
from app.models import BatchAssignment
from app.template_engine import render_template

OUT = ROOT / "samples" / "output"
OUT.mkdir(parents=True, exist_ok=True)

def save_mark(name, template_id, data):
    t=load_templates()[template_id]; q=load_quality_profiles()[t.quality_profile]
    r=render_template(t,q,data)
    (OUT/f"{name}.svg").write_text(r.svg,encoding="utf-8")
    (OUT/f"{name}.png").write_bytes(svg_to_png(r.svg,r.width_mm,r.height_mm,600))
    return r

save_mark("inova_Q00525499","inova_quantum_code128_v1",{"manufacturer_id":"Q00525499"})
save_mark("inova_Q00503416","inova_quantum_code128_v1",{"manufacturer_id":"Q00503416"})
save_mark("sercel_4281847_code128","sercel_dfu_code128_v1",{"manufacturer_id":"4281847"})
save_mark("sercel_4281847_datamatrix","sercel_dfu_datamatrix_v1",{"manufacturer_id":"4281847"})
save_mark("phone_TEL-0037","phone_qr_economic_v1",{"economic_number":"TEL-0037","asset_id":"PHONE-000037"})
save_mark("radio_RADIO-000184","generic_asset_qr_v1",{"asset_id":"RADIO-000184"})

j=load_jigs()["inova_tray_3x4_estimate"]; m=load_machines()[j.machine_profile_id]
t=load_templates()[j.template_id]; q=load_quality_profiles()[t.quality_profile]
slots=slot_positions(j)
rows=[{"manufacturer_id":f"Q{525499+i:08d}"} for i in range(12)]
assign=[BatchAssignment(slot_index=slots[i]["slot_index"],row_index=i,physical_id=rows[i]["manufacturer_id"]) for i in range(12)]
b=render_batch(m,j,t,q,rows,assign,True)
png=svg_to_png(b.svg,m.bed_width_mm,m.bed_height_mm,300)
(OUT/"inova_batch_12.svg").write_text(b.svg,encoding="utf-8")
(OUT/"inova_batch_12_preview_DO_NOT_ENGRAVE.svg").write_text(b.preview_svg,encoding="utf-8")
(OUT/"inova_batch_12_300dpi.png").write_bytes(png)
meta={"demo":True,"template_id":t.id,"jig_id":j.id,"machine_id":m.id,"output_dpi":300,"warning":"Jig offsets are initial estimates and require physical calibration."}
(OUT/"inova_batch_12_demo.zip").write_bytes(build_batch_zip(b.svg,b.preview_svg,png,b.manifest,meta,300))
(OUT/"inova_tray_3x4_CALIBRATION_ONLY.svg").write_text(calibration_target_svg(m,j), encoding="utf-8")
print(json.dumps({"output":str(OUT),"files":len(list(OUT.iterdir()))},indent=2))
