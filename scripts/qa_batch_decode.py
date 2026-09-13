#!/usr/bin/env python3
"""Decode the generated 3x4 INOVA bed image as one image.

This verifies that a complete physical-load layout remains machine-readable after
composition, not only when marks are tested individually.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from PIL import Image
from pyzbar.pyzbar import decode

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'qa'/'output'; OUT.mkdir(parents=True,exist_ok=True)
SAMPLE=ROOT/'samples'/'output'/'inova_batch_12_300dpi.png'
EXPECTED=[f"Q00{525499+i:06d}" for i in range(12)]

def main():
    if not SAMPLE.exists():
        raise SystemExit(f"Missing {SAMPLE}; run scripts/generate_demo_assets.py first")
    found=[]
    for x in decode(Image.open(SAMPLE)):
        if x.type == 'CODE128':
            found.append(x.data.decode('utf-8',errors='replace'))
    report={"expected":EXPECTED,"decoded":sorted(found),"missing":sorted(set(EXPECTED)-set(found)),"unexpected":sorted(set(found)-set(EXPECTED))}
    report['status']='PASS' if set(found)==set(EXPECTED) and len(found)==12 else 'FAIL'
    (OUT/'batch_decode_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
