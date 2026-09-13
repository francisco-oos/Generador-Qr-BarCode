#!/usr/bin/env python3
"""UI smoke test with a deterministic API/static fallback.

The main goal is to catch broken HTML/JS/API contracts.  In some CI/sandbox
runtimes Chromium is installed but local navigation is blocked by policy
(`ERR_BLOCKED_BY_ADMINISTRATOR`).  That situation is reported as a browser
SKIP, never as a false application failure; API/static checks still run and
must pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "qa" / "output"
OUT.mkdir(parents=True, exist_ok=True)
PORT = 8797


def api_static_fallback() -> dict:
    """Exercise the same app without a browser using FastAPI TestClient."""
    from fastapi.testclient import TestClient
    from app.main import app

    result: dict[str, object] = {}
    with TestClient(app) as client:
        health = client.get("/api/health")
        result["health"] = health.status_code == 200 and health.json().get("version") == "0.6.2"
        index = client.get("/")
        text = index.text
        result["index"] = index.status_code == 200
        result["guided_controls"] = all(x in text for x in ("guidedModeBtn", "expertModeBtn", "calibration", "designerCanvas", "saveVisualTemplateBtn"))
        catalog = client.get("/api/catalog")
        result["catalog"] = catalog.status_code == 200 and len(catalog.json().get("templates", [])) >= 5
        calib = client.get("/api/calibration/jig/inova_tray_3x4_estimate")
        result["calibration_svg"] = calib.status_code == 200 and "<svg" in calib.json().get("svg", "")
        template = next(x for x in catalog.json()["templates"] if x["id"] == "inova_quantum_code128_v1")
        quality = client.post("/api/quality/check", json={
            "template": template,
            "data": {"manufacturer_id": "Q00525499"},
            "scanner_profile_id": "steren_com_597",
            "digital_stress": True,
        })
        result["quality_preflight"] = quality.status_code == 200 and quality.json().get("overall") in {"ROBUSTO", "ACEPTABLE"}
    return result


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    errors: list[str] = []
    results: dict[str, object] = {"api_static_fallback": api_static_fallback()}
    browser_status = "NOT_RUN"
    try:
        import urllib.request
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=.5) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(.15)
        else:
            raise RuntimeError("server did not start")

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page_errors: list[str] = []
                page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
                browser_results: dict[str, object] = {}
                browser_results["title"] = page.title()
                browser_results["guided_default"] = not page.locator("body").evaluate("e=>e.classList.contains('expert-mode')")
                browser_results["preview_has_svg"] = page.locator("#preview svg").count() > 0
                page.click("#individualQualityBtn")
                page.wait_for_timeout(450)
                browser_results["quality_preflight"] = page.locator("#individualQualityResult .quality-card").count() > 0
                page.click("#expertModeBtn")
                browser_results["expert_mode"] = page.locator("body").evaluate("e=>e.classList.contains('expert-mode')")
                page.click('[data-tab="calibration"]')
                page.click("#loadCalibrationBtn")
                page.wait_for_timeout(300)
                browser_results["calibration_svg"] = page.locator("#calibrationPreview svg").count() > 0
                page.click('[data-tab="materials"]')
                page.fill("#phoneBrand", "CUBOT")
                page.fill("#phoneModel", "KingKong 9")
                page.click("#searchPhoneBtn")
                page.wait_for_timeout(250)
                browser_results["phone_reference"] = page.locator("#phoneResults .material-card").count() > 0
                page.click('[data-tab="batch"]')
                page.set_input_files("#csvFile", str(ROOT / "samples/input/inova_1200.csv"))
                page.wait_for_timeout(300)
                browser_results["csv_1200"] = "1200 registros" in page.locator("#csvInfo").inner_text()
                browser_results["batch_preview"] = page.locator("#batchRecordPreview svg").count() > 0
                page.click('[data-tab="config"]')
                page.click("#newTemplateBtn")
                page.click('[data-add-kind="code128"]')
                page.wait_for_timeout(250)
                browser_results["visual_designer_object"] = page.locator("#designerCanvas .design-object").count() == 1
                browser_results["visual_designer_svg"] = page.locator("#designerPreview svg").count() > 0
                page.screenshot(path=str(OUT / "ui_smoke_expert.png"), full_page=True)
                page.click("#guidedModeBtn")
                page.click('[data-tab="individual"]')
                page.screenshot(path=str(OUT / "ui_smoke_guided.png"), full_page=True)
                browser.close()
                results["browser"] = browser_results
                if page_errors:
                    errors.extend(page_errors)
                    browser_status = "FAIL"
                elif all(v for k, v in browser_results.items() if k != "title"):
                    browser_status = "PASS"
                else:
                    browser_status = "FAIL"
        except Exception as exc:
            message = repr(exc)
            if "ERR_BLOCKED_BY_ADMINISTRATOR" in message:
                browser_status = "SKIP_POLICY"
                results["browser_skip_reason"] = "El runtime bloquea navegación Chromium a localhost por política; se ejecutó fallback API/HTML."
            elif "Executable doesn't exist" in message or "playwright" in message.lower() and "not found" in message.lower():
                browser_status = "SKIP_UNAVAILABLE"
                results["browser_skip_reason"] = "Playwright/Chromium no disponible en el host; se ejecutó fallback API/HTML."
            else:
                browser_status = "FAIL"
                errors.append(message)
    except Exception as exc:
        errors.append(repr(exc))
        browser_status = "FAIL"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    fallback_ok = all(bool(v) for v in results["api_static_fallback"].values())
    overall = "PASS" if fallback_ok and browser_status in {"PASS", "SKIP_POLICY", "SKIP_UNAVAILABLE"} and not errors else "FAIL"
    report = {
        "status": overall,
        "browser_status": browser_status,
        "results": results,
        "errors": errors,
        "interpretation": "PASS with browser SKIP means app/API/static contract passed but true browser E2E was not executable in this host.",
    }
    (OUT / "browser_smoke_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
