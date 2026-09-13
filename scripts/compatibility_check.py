#!/usr/bin/env python3
"""Portable preflight/compatibility gate for Marking Studio.

This script does not require a laser. It validates the Python runtime, imports,
SQLite write/read behavior, configuration catalog, every template renderer,
1,200-row CSV handling, SVG XML validity and the serial discovery layer.
The resulting JSON/Markdown are audit evidence for the exact host where it ran.
"""
from __future__ import annotations

import importlib
import json
import os
import platform
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.batch_engine import chunk_count, parse_csv_text
from app.config_loader import load_jigs, load_machines, load_quality_profiles, load_scanners, load_templates
from app.machine_bridge import import_configuration_bytes, lightburn_pref_roots, lasergrbl_roots, list_serial_devices
from app.material_catalog import load_material_reference
from app.template_engine import render_template
from app.calibration import jig_reference_points

OUT = ROOT / "qa" / "output"
OUT.mkdir(parents=True, exist_ok=True)


def check(name, fn):
    started = time.perf_counter()
    try:
        detail = fn()
        return {"name": name, "status": "PASS", "detail": detail, "seconds": round(time.perf_counter()-started, 4)}
    except Exception as exc:
        return {"name": name, "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}", "seconds": round(time.perf_counter()-started, 4)}


def package_versions():
    result = {}
    for module in ("fastapi", "uvicorn", "pydantic", "reportlab", "qrcode", "PIL", "cryptography"):
        m = importlib.import_module(module)
        result[module] = getattr(m, "__version__", getattr(m, "VERSION", "installed"))
    try:
        from pyzbar.pyzbar import decode as _decode  # noqa: F401
        result["pyzbar"] = "available (digital barcode/QR preflight enabled)"
    except Exception as exc:
        # Structural checks remain available; absence of native zbar is reported, not hidden.
        result["pyzbar"] = f"unavailable; structural preflight only: {exc}"
    try:
        m = importlib.import_module("serial")
        result["serial"] = getattr(m, "__version__", "installed")
    except ModuleNotFoundError:
        if os.name == "posix":
            result["serial"] = "pyserial unavailable on validation host; native POSIX read-only fallback active"
        else:
            raise
    return result


def sqlite_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)/"probe.sqlite3"
        con = sqlite3.connect(p)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE t(v TEXT)")
        con.execute("INSERT INTO t VALUES(?)", ("áéíóú/中文/test",))
        con.commit()
        value = con.execute("SELECT v FROM t").fetchone()[0]
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        con.close()
        assert value == "áéíóú/中文/test"
        return {"journal_mode": mode, "unicode": True}


def render_all():
    templates = load_templates(); qualities = load_quality_profiles()
    rendered = []
    for t in templates.values():
        example = dict(t.metadata.get("example_data") or {})
        for f in t.expected_fields:
            example.setdefault(f, f"TEST-{f.upper()}")
        mark = render_template(t, qualities[t.quality_profile], example)
        ET.fromstring(mark.svg)
        rendered.append({"template": t.id, "bytes": len(mark.svg.encode()), "warnings": mark.warnings})
    return rendered


def csv_scale():
    text = "manufacturer_id\n" + "\n".join(f"Q00{525499+i:06d}" for i in range(1200)) + "\n"
    headers, rows = parse_csv_text(text)
    assert len(rows) == 1200
    return {"headers": headers, "records": len(rows), "loads_at_12": chunk_count(len(rows), 12)}


def catalog_check():
    materials = load_material_reference()
    dangerous = {"pvc_vinyl", "abs_plastic", "polycarbonate_pc", "unknown_plastic", "phone_assembled_unknown"}
    for item in materials["materials"]:
        if item["id"] in dangerous:
            suggested = item.get("suggested") or {}
            if "speed_mm_min" in suggested and "power_percent" in suggested:
                raise RuntimeError(f"unsafe catalog entry exposes production pair: {item['id']}")
    return {
        "templates": len(load_templates()), "machines": len(load_machines()),
        "jigs": len(load_jigs()), "quality_profiles": len(load_quality_profiles()),
        "scanners": len(load_scanners()), "material_references": len(materials["materials"]),
        "phone_references": len(materials["phone_models"]),
    }


def lightburn_parser_check():
    sample = b'{"Demo":{"XParam":"Speed","XMin":1000,"XMax":3000,"MaterialCut":{"type":"Scan","speed":2200,"maxPower":25}}}'
    parsed = import_configuration_bytes("material_test_presets.lbmt", sample)
    assert parsed.source_type == "lightburn_material_test"
    assert parsed.material_presets[0]["settings"]["material_cut"]["maxPower"] == 25
    roots = {
        "windows": [str(x) for x in lightburn_pref_roots(Path.home(), "Windows", {"LOCALAPPDATA": str(Path.home()/"AppData"/"Local")})],
        "linux": [str(x) for x in lightburn_pref_roots(Path.home(), "Linux", {})],
        "macos": [str(x) for x in lightburn_pref_roots(Path.home(), "Darwin", {})],
    }
    return {"lbmt_parser": True, "platform_pref_roots": roots}


def serial_discovery():
    ports = list_serial_devices()
    return {"ports_detected": len(ports), "note": "0 is valid on hosts without attached serial hardware"}


def calibration_check():
    result = {}
    for jig in load_jigs().values():
        pts = jig_reference_points(jig)
        assert len(pts) == 3
        result[jig.id] = [p.model_dump() for p in pts]
    return result


def lasergrbl_parser_check():
    sample = b'''<?xml version="1.0"?><MaterialDB><Materials><Model>S9 Pro</Model><Material>Test</Material><Action>Engrave</Action><Power>30</Power><Speed>3000</Speed><Cycles>1</Cycles></Materials></MaterialDB>'''
    parsed = import_configuration_bytes("UserMaterials.psh", sample)
    assert parsed.material_presets[0]["settings"]["speed_mm_min"] == 3000
    roots = lasergrbl_roots(Path.home(), "Windows", {"APPDATA": str(Path.home()/"AppData"/"Roaming")})
    return {"parser": True, "windows_root": [str(x) for x in roots]}


def launcher_check():
    required = ["install_windows.bat", "run_windows.bat", "install_linux.sh", "run_linux.sh", "install_macos.sh", "run_macos.sh"]
    missing = [x for x in required if not (ROOT/x).exists()]
    if missing:
        raise RuntimeError(f"missing launchers: {missing}")
    return {"present": required}


def main():
    checks = [
        check("python_runtime", lambda: {"version": sys.version.split()[0], "supported": sys.version_info >= (3,12)} if sys.version_info >= (3,12) else (_ for _ in ()).throw(RuntimeError("Python < 3.12"))),
        check("dependencies", package_versions),
        check("sqlite_roundtrip", sqlite_roundtrip),
        check("configuration_catalog", catalog_check),
        check("render_every_template", render_all),
        check("csv_1200", csv_scale),
        check("serial_discovery", serial_discovery),
        check("lightburn_parser_and_paths", lightburn_parser_check),
        check("lasergrbl_material_parser", lasergrbl_parser_check),
        check("jig_reference_geometry", calibration_check),
        check("launchers", launcher_check),
    ]
    report = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": sys.version, "executable": sys.executable},
        "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
        "checks": checks,
        "scope_note": "Cross-platform source/packaging is checked here. Only this host OS is executed; Windows/macOS execution is delegated to CI or a real host.",
    }
    (OUT/"compatibility_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Compatibility report", "", f"Overall: **{report['status']}**", "", f"Host: `{platform.platform()}` / Python `{sys.version.split()[0]}`", ""]
    for c in checks:
        md.append(f"- **{c['name']}**: {c['status']} — `{c['detail']}`")
    md += ["", report["scope_note"]]
    (OUT/"compatibility_report.md").write_text("\n".join(md)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)

if __name__ == "__main__":
    main()
