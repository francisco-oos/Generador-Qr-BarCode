from __future__ import annotations

import json
import sys
import time
import resource
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.batch_engine import parse_csv_text, render_batch, slot_positions
from app.config_loader import load_jigs, load_machines, load_quality_profiles, load_templates
from app.exporters import svg_to_png
from app.models import BatchAssignment
from app.template_engine import render_template

OUT = ROOT / "qa" / "output"
OUT.mkdir(parents=True, exist_ok=True)


def timed(name, fn):
    t0 = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - t0


def main():
    templates = load_templates(); qualities = load_quality_profiles(); jigs=load_jigs(); machines=load_machines()
    t = templates["inova_quantum_code128_v1"]; q=qualities[t.quality_profile]
    j = jigs["inova_tray_3x4_estimate"]; m=machines[j.machine_profile_id]
    _, rows = parse_csv_text((ROOT/"samples/input/inova_1200.csv").read_text(encoding="utf-8-sig"))

    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    def render_2500():
        checksum=0
        for i in range(2500):
            value=f"Q{5000000+i:08d}"
            r=render_template(t,q,{"manufacturer_id":value})
            checksum += len(r.svg)
        return checksum
    checksum, sec5000 = timed("2500", render_2500)
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_delta_mib=max(0,(rss_after-rss_before)/1024)

    slots=slot_positions(j)
    def render_all_batches():
        produced=0
        last=None
        for start in range(0,len(rows),j.capacity):
            chunk=rows[start:start+j.capacity]
            assigns=[BatchAssignment(slot_index=slots[i]["slot_index"], row_index=i, physical_id=chunk[i]["manufacturer_id"]) for i in range(len(chunk))]
            last=render_batch(m,j,t,q,chunk,assigns,True)
            produced += len(last.manifest)
        return produced,last
    (produced,last), sec_batches=timed("batches", render_all_batches)

    png, sec_png = timed("png", lambda: svg_to_png(last.svg,m.bed_width_mm,m.bed_height_mm,300))
    (OUT/"benchmark_last_batch_300dpi.png").write_bytes(png)

    report={
        "records_input":len(rows),
        "jig_capacity":j.capacity,
        "batches_for_1200":(len(rows)+j.capacity-1)//j.capacity,
        "individual_render_2500_seconds":round(sec5000,3),
        "individual_render_2500_per_second":round(2500/sec5000,1),
        "process_peak_rss_delta_mib":round(peak_delta_mib,2),
        "checksum":checksum,
        "batch_vector_render_1200_seconds":round(sec_batches,3),
        "batch_records_produced":produced,
        "last_full_bed_png_300dpi_seconds":round(sec_png,3),
        "last_full_bed_png_bytes":len(png),
        "status":"PASS" if produced==1200 else "FAIL"
    }
    (OUT/"scalability_benchmark.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    md=["# Benchmark de escalabilidad","",f"Estado: **{report['status']}**","", "```json", json.dumps(report,indent=2), "```", ""]
    (OUT/"scalability_benchmark.md").write_text("\n".join(md),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if report["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
