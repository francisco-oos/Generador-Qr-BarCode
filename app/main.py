"""FastAPI application for Server Oficina Marking Studio.

Marking Studio owns asset-identification rules, template layout, batching, physical
reconciliation and audit history.  It intentionally does not stream engraving jobs
to the laser. LightBurn/LaserGRBL remain the machine-control layer.

The only direct controller communication implemented here is an opt-in, read-only
GRBL diagnostic that sends ``$I`` and ``$$`` so the shop can capture the settings
already used by its SCULPFUN or another GRBL engraver.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .batch_engine import normalize_identifier, parse_csv_text, render_batch, slot_positions
from .config_loader import (
    load_jigs,
    load_machines,
    load_quality_profiles,
    load_scanners,
    load_templates,
    save_jig,
    save_template,
)
from .db import (
    history,
    init_db,
    machine_captures,
    material_preset_by_id,
    material_presets,
    record_job,
    record_machine_capture,
    record_shop_material_preset,
    verify_mark,
)
from .exporters import build_batch_zip, build_bulk_template_zip, svg_to_png
from .licensing import get_license_provider
from .machine_bridge import (
    compare_grbl_to_profile,
    discover_lightburn_artifacts,
    discover_lasergrbl_artifacts,
    import_configuration_bytes,
    import_discovered_lightburn_artifact,
    import_discovered_lasergrbl_artifact,
    list_serial_devices,
    parse_grbl_dump,
    probe_grbl_readonly,
    sha256_bytes,
)
from .models import (
    BatchExportRequest,
    GrblParseRequest,
    GrblProbeRequest,
    InputRule,
    LocalArtifactImportRequest,
    CalibrationEvaluationRequest,
    ShopMaterialPresetRequest,
    JigSaveRequest,
    RenderRequest,
    SeriesGenerateRequest,
    ScanVerifyRequest,
    TemplateInputRuleUpdateRequest,
    TemplateSaveRequest,
    TemplatePreviewRequest,
    BulkTemplateExportRequest,
    CodeQualityCheckRequest,
)
from .template_engine import apply_input_rules, render_template
from .calibration import calibration_target_svg, evaluate_reference_points, jig_reference_points
from .material_catalog import phone_reference, search_material_reference
from .code_quality import assess_template_codes

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
VERSION = "0.6.2"


# WHY: Inicializa almacenamiento y recursos una sola vez al arrancar/cerrar la aplicación.
@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Server Oficina Marking Studio",
    version=VERSION,
    description="Generador de identificación física para nodos, teléfonos y activos.",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# WHY: Centraliza lectura de licencia para no repetir lógica de autorización en cada ruta.
def _license_status() -> dict[str, Any]:
    return get_license_provider().status()


# WHY: Bloquea rutas operativas cuando la autorización no es válida, antes de ejecutar lógica o escribir histórico.
def _require_license() -> dict[str, Any]:
    status = _license_status()
    if not status.get("valid"):
        raise HTTPException(status_code=403, detail={"error": "license_invalid", "license": status})
    return status


# WHY: Sirve la interfaz local desde el mismo proceso para simplificar instalación en Windows/Linux/macOS.
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


# WHY: Expone versión, capacidades y límites de seguridad para diagnóstico/automatización.
@app.get("/api/health")
def health() -> dict[str, Any]:
    license_status = _license_status()
    return {
        "ok": True,
        "app": "Server Oficina Marking Studio",
        "version": VERSION,
        "license_valid": bool(license_status.get("valid")),
        "license_mode": license_status.get("mode"),
        "templates": len(load_templates()),
        "machines": len(load_machines()),
        "jigs": len(load_jigs()),
        "scanners": len(load_scanners()),
        "direct_laser_job_streaming": False,
        "grbl_read_only_probe": True,
    }


# WHY: Permite a la UI mostrar estado de licencia sin acceder directamente a archivos de firma.
@app.get("/api/license")
def license_status() -> dict[str, Any]:
    return _license_status()


# WHY: Entrega plantillas, jigs, máquinas, lectores y calidad desde configuración, evitando catálogos duplicados en JavaScript.
@app.get("/api/catalog")
def catalog() -> dict[str, Any]:
    _require_license()
    templates = [t.model_dump() for t in load_templates().values()]
    machines = [m.model_dump() for m in load_machines().values()]
    jigs = []
    for j in load_jigs().values():
        item = j.model_dump()
        item["capacity"] = j.capacity
        item["slots"] = slot_positions(j)
        jigs.append(item)
    quality = [q.model_dump() for q in load_quality_profiles().values()]
    scanners = [s.model_dump() for s in load_scanners().values()]
    return {
        "templates": templates,
        "machines": machines,
        "jigs": jigs,
        "quality_profiles": quality,
        "scanners": scanners,
    }


# WHY: Renderiza una marca individual usando la ruta autoritativa del template engine.
@app.post("/api/render")
def render(req: RenderRequest):
    _require_license()
    templates = load_templates()
    if req.template_id not in templates:
        raise HTTPException(404, f"Plantilla no encontrada: {req.template_id}")
    template = templates[req.template_id]
    quality = load_quality_profiles().get(template.quality_profile)
    if not quality:
        raise HTTPException(500, f"Perfil de calidad no encontrado: {template.quality_profile}")
    try:
        normalized = apply_input_rules(template, req.data, capture_mode=req.capture_mode)
        mark = render_template(template, quality, normalized)
    except Exception as exc:
        raise HTTPException(400, f"No fue posible renderizar: {exc}") from exc

    if req.output == "png":
        dpi = req.dpi or quality.render_dpi
        png = svg_to_png(mark.svg, mark.width_mm, mark.height_mm, dpi=dpi)
        return Response(
            content=png,
            media_type="image/png",
            headers={"X-Mark-Warnings": str(len(mark.warnings))},
        )
    return {
        "svg": mark.svg,
        "width_mm": mark.width_mm,
        "height_mm": mark.height_mm,
        "warnings": mark.warnings,
        "resolved": mark.resolved,
        "calibration_required": template.calibration_required,
    }


# WHY: Prevalida legibilidad de códigos antes de exportar sin sustituir la prueba física con el lector real.
@app.post("/api/quality/check")
def code_quality_check(req: CodeQualityCheckRequest) -> dict[str, Any]:
    _require_license()
    qualities = load_quality_profiles()
    quality = qualities.get(req.template.quality_profile)
    if not quality:
        raise HTTPException(400, f"Perfil de calidad no encontrado: {req.template.quality_profile}")
    scanner = None
    if req.scanner_profile_id:
        scanner = load_scanners().get(req.scanner_profile_id)
        if not scanner:
            raise HTTPException(400, f"Lector no encontrado: {req.scanner_profile_id}")
    try:
        return assess_template_codes(
            req.template, quality, req.data, capture_mode=req.capture_mode,
            scanner=scanner, dpi=req.dpi, digital_stress=req.digital_stress,
        )
    except Exception as exc:
        raise HTTPException(400, f"No fue posible evaluar legibilidad: {exc}") from exc


# WHY: Analiza CSV/listas y devuelve columnas/filas para que el usuario mapee datos sin formato rígido.
@app.post("/api/csv/inspect")
async def csv_inspect(file: UploadFile = File(...), header_mode: str = "auto") -> dict[str, Any]:
    _require_license()
    raw = await file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "CSV demasiado grande (>15 MB)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    try:
        mode = {"yes": True, "no": False, "auto": None}.get(header_mode)
        if header_mode not in {"yes", "no", "auto"}:
            raise ValueError("header_mode debe ser auto, yes o no")
        headers, rows = parse_csv_text(text, has_header=mode)
    except Exception as exc:
        raise HTTPException(400, f"CSV inválido: {exc}") from exc
    return {
        "filename": file.filename,
        "headers": headers,
        "count": len(rows),
        "rows": rows,
        "preview": rows[:20],
        "header_mode": header_mode,
    }


# WHY: Genera secuencias explícitas y limitadas cuando la regla de numeración es conocida.
@app.post("/api/series/generate")
def series_generate(req: SeriesGenerateRequest) -> dict[str, Any]:
    _require_license()
    rows: list[dict[str, str]] = []
    for index in range(req.count):
        number = req.start + index
        numeric = str(number).zfill(req.width) if req.width else str(number)
        rows.append({req.field: f"{req.prefix}{numeric}{req.suffix}"})
    return {
        "field": req.field,
        "count": len(rows),
        "rows": rows,
        "first": rows[0][req.field],
        "last": rows[-1][req.field],
        "warning": (
            "Use series generation only for identifiers whose numbering rule is controlled and known; "
            "do not infer missing manufacturer IDs."
        ),
    }


# WHY: Valida un lote, renderiza el jig, registra auditoría y entrega un ZIP listo para handoff.
@app.post("/api/batch/export")
def batch_export(req: BatchExportRequest):
    license_info = _require_license()
    templates = load_templates()
    jigs = load_jigs()
    machines = load_machines()
    qualities = load_quality_profiles()

    template = templates.get(req.template_id)
    jig = jigs.get(req.jig_id)
    if not template:
        raise HTTPException(404, f"Plantilla no encontrada: {req.template_id}")
    if not jig:
        raise HTTPException(404, f"Jig no encontrado: {req.jig_id}")
    machine = machines.get(jig.machine_profile_id)
    if not machine:
        raise HTTPException(500, f"Máquina del jig no encontrada: {jig.machine_profile_id}")
    quality = qualities.get(template.quality_profile)
    if not quality:
        raise HTTPException(500, f"Perfil de calidad no encontrado: {template.quality_profile}")
    if len(req.assignments) > jig.capacity:
        raise HTTPException(400, f"El jig admite {jig.capacity} posiciones y se recibieron {len(req.assignments)}")

    selected_material = None
    if req.material_preset_id is not None:
        selected_material = material_preset_by_id(req.material_preset_id)
        if not selected_material:
            raise HTTPException(404, "Preset de material no encontrado")

    try:
        batch = render_batch(
            machine=machine,
            jig=jig,
            template=template,
            quality=quality,
            rows=req.rows,
            assignments=req.assignments,
            require_physical_confirmation=req.require_physical_confirmation,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    # Full-bed raster at 600 DPI is unnecessarily large for the current S9 bed.
    # 300 DPI still provides multiple pixels per default Code128 module and keeps
    # batch ZIPs practical. SVG remains the authoritative production format.
    dpi = req.output_dpi or min(quality.render_dpi, 300)
    dpi = min(dpi, 300)
    png = svg_to_png(batch.svg, machine.bed_width_mm, machine.bed_height_mm, dpi=dpi)
    metadata = {
        "template_id": template.id,
        "jig_id": jig.id,
        "machine_id": machine.id,
        "record_count": len(batch.manifest),
        "warnings": batch.warnings,
        "calibration_required": bool(template.calibration_required or jig.calibration_required),
        "license_id": (license_info.get("payload") or {}).get("license_id"),
        "output_dpi": dpi,
        "material_preset": selected_material,
        "safety": (
            "Archivo generado para importación en LightBurn/LaserGRBL. Marking Studio no envía "
            "movimiento, potencia ni disparo del láser. Los parámetros importados son referencia/auditoría; "
            "el operador debe verificar Frame, material y configuración en el software de máquina."
        ),
    }
    job_id = record_job(template.id, jig.id, machine.id, batch.manifest, req.rows, metadata)
    metadata["job_id"] = job_id
    zip_bytes = build_batch_zip(batch.svg, batch.preview_svg, png, batch.manifest, metadata, raster_dpi=dpi)
    filename = f"marking-job-{job_id[:8]}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Job-Id": job_id,
        },
    )


# WHY: Compara lectura real con identidad esperada y registra verificación sólo si coincide.
@app.post("/api/scan/verify")
def scan_verify(req: ScanVerifyRequest) -> dict[str, Any]:
    _require_license()
    expected = normalize_identifier(req.expected) if req.normalize else req.expected
    scanned = normalize_identifier(req.scanned) if req.normalize else req.scanned
    matched = expected == scanned
    result: dict[str, Any] = {"matched": matched, "expected": expected, "scanned": scanned}
    if matched:
        result["history_update"] = verify_mark(req.expected, req.scanned)
    return result


# WHY: Expone histórico reciente sin dar acceso directo a SQLite.
@app.get("/api/history")
def get_history(limit: int = 100) -> dict[str, Any]:
    _require_license()
    return {"items": history(max(1, min(limit, 1000)))}




# WHY: Previsualiza un borrador no guardado con el mismo motor usado en producción.
@app.post("/api/templates/preview")
def preview_template_api(req: TemplatePreviewRequest):
    """Render a visual-designer draft without saving or touching machine state."""
    _require_license()
    quality = load_quality_profiles().get(req.template.quality_profile)
    if not quality:
        raise HTTPException(400, f"Perfil de calidad no encontrado: {req.template.quality_profile}")
    try:
        normalized = apply_input_rules(req.template, req.data, capture_mode=req.capture_mode)
        mark = render_template(req.template, quality, normalized)
    except Exception as exc:
        raise HTTPException(400, f"No fue posible previsualizar la plantilla: {exc}") from exc
    if req.output == "png":
        dpi = req.dpi or quality.render_dpi
        return Response(content=svg_to_png(mark.svg, mark.width_mm, mark.height_mm, dpi=dpi), media_type="image/png")
    return {
        "svg": mark.svg, "width_mm": mark.width_mm, "height_mm": mark.height_mm,
        "warnings": mark.warnings, "resolved": mark.resolved,
    }


# WHY: Genera un SVG por fila para lotes sin jig, manteniendo nombres y manifiesto deterministas.
@app.post("/api/bulk/svg-export")
def bulk_svg_export(req: BulkTemplateExportRequest):
    """Generate up to 10k individual SVGs from one saved template and mapped rows."""
    _require_license()
    template = load_templates().get(req.template_id)
    if not template:
        raise HTTPException(404, f"Plantilla no encontrada: {req.template_id}")
    quality = load_quality_profiles().get(template.quality_profile)
    if not quality:
        raise HTTPException(500, f"Perfil de calidad no encontrado: {template.quality_profile}")

    # WHY: Aísla safe_name para que el flujo sea testeable, mantenible y fácil de auditar.
    def safe_name(value: str, index: int) -> str:
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())[:100].strip("._-")
        return base or f"mark_{index:05d}"

    items: list[dict[str, Any]] = []
    used: dict[str, int] = {}
    warnings: list[str] = []
    for index, row in enumerate(req.rows, start=1):
        normalized = apply_input_rules(template, row, capture_mode="import")
        mark = render_template(template, quality, normalized)
        if mark.warnings:
            warnings.extend([f"fila {index}: {w}" for w in mark.warnings])
        value = ""
        if req.filename_field:
            value = str(normalized.get(req.filename_field, ""))
        if not value:
            primary = str(template.metadata.get("primary_identity_field", ""))
            if primary:
                value = str(normalized.get(primary, ""))
        if not value and template.expected_fields:
            value = str(normalized.get(template.expected_fields[0], ""))
        filename = safe_name(value, index)
        count = used.get(filename, 0) + 1
        used[filename] = count
        if count > 1:
            filename = f"{filename}_{count:03d}"
        items.append({"filename": filename, "svg": mark.svg, "data": normalized})

    payload = build_bulk_template_zip(items, {
        "template_id": template.id, "record_count": len(items),
        "warning_count": len(warnings), "warnings": warnings[:500],
        "machine_control": False,
        "handoff": "Importar SVG en LightBurn/Sculpfun Space u otro software compatible.",
    })
    return Response(
        content=payload, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{template.id}-svg-bulk.zip"', "X-Record-Count": str(len(items))},
    )


# WHY: Valida y guarda plantillas del estudio visual como datos configurables.
@app.post("/api/templates/save")
def save_template_api(req: TemplateSaveRequest) -> dict[str, Any]:
    _require_license()
    path = save_template(req.template)
    return {"saved": True, "id": req.template.id, "path": str(path.relative_to(ROOT))}


# WHY: Actualiza una regla de captura específica sin obligar al frontend a reescribir a ciegas el archivo entero.
@app.post("/api/templates/input-rule")
def template_input_rule(req: TemplateInputRuleUpdateRequest) -> dict[str, Any]:
    """Friendly endpoint used by the template editor's prefix/suffix assistant."""
    _require_license()
    template = load_templates().get(req.template_id)
    if not template:
        raise HTTPException(404, "Plantilla no encontrada")
    rules = [r for r in template.input_rules if r.field != req.field]
    rules.append(InputRule(
        field=req.field,
        manual_prefix_enabled=req.manual_prefix_enabled,
        manual_prefix=req.manual_prefix,
        manual_suffix_enabled=req.manual_suffix_enabled,
        manual_suffix=req.manual_suffix,
        imported_values=req.imported_values,
        uppercase=req.uppercase,
    ))
    template.input_rules = rules
    path = save_template(template)
    return {"saved": True, "template": template.model_dump(), "path": str(path.relative_to(ROOT))}


# WHY: Valida y guarda bases físicas configurables desde modo experto.
@app.post("/api/jigs/save")
def save_jig_api(req: JigSaveRequest) -> dict[str, Any]:
    _require_license()
    path = save_jig(req.jig)
    return {"saved": True, "id": req.jig.id, "path": str(path.relative_to(ROOT))}


# ---------------------------------------------------------------------------
# Material / phone research reference
# ---------------------------------------------------------------------------

# WHY: Consulta la biblioteca de referencia y conserva sus advertencias/política de seguridad.
@app.get("/api/materials/reference")
def materials_reference(q: str = "", category: str | None = None) -> dict[str, Any]:
    _require_license()
    return search_material_reference(q, category)


# WHY: Devuelve conocimiento de superficie por modelo sin inventar material cuando no está confirmado.
@app.get("/api/materials/phone")
def materials_phone(brand: str, model: str = "") -> dict[str, Any]:
    _require_license()
    return {
        "brand": brand,
        "model": model,
        "matches": phone_reference(brand, model),
        "rule": "El modelo exacto y la superficie exacta mandan; un preset validado del taller tiene prioridad sobre una referencia web.",
    }


# ---------------------------------------------------------------------------
# Machine interoperability / settings capture
# ---------------------------------------------------------------------------

# WHY: Lista puertos seriales para diagnóstico explícito, sin abrirlos ni transmitir comandos.
@app.get("/api/machine/ports")
def machine_ports() -> dict[str, Any]:
    _require_license()
    return {"ports": list_serial_devices(), "read_only": True}


# WHY: Descubre artefactos LightBurn locales en modo lectura para rescatar conocimiento del taller.
@app.get("/api/machine/lightburn/discover")
def machine_lightburn_discover() -> dict[str, Any]:
    _require_license()
    result = discover_lightburn_artifacts()
    result["note"] = (
        "Detección local de solo lectura. Busca prefs.ini, material_test_presets.lbmt, "
        "respaldos .lbset/.lbprefs y librerías .clb en las rutas estándar de LightBurn."
    )
    return result


# WHY: Importa un artefacto previamente seleccionado y registra su procedencia/presets.
@app.post("/api/machine/lightburn/import-local")
def machine_lightburn_import_local(req: LocalArtifactImportRequest) -> dict[str, Any]:
    _require_license()
    discovered = discover_lightburn_artifacts()
    match = next((x for x in discovered["artifacts"] if str(Path(x["path"]).resolve()) == str(Path(req.path).expanduser().resolve())), None)
    if not match:
        raise HTTPException(400, "La ruta no pertenece a los artefactos LightBurn detectados")
    try:
        parsed = import_discovered_lightburn_artifact(req.path, discovered["artifacts"])
        raw = Path(match["path"]).read_bytes()
    except Exception as exc:
        raise HTTPException(400, f"No se pudo importar el artefacto local: {exc}") from exc
    digest = sha256_bytes(raw)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(match["name"]).name)[:120] or "lightburn.bin"
    archive_dir = ROOT / "data" / "machine_imports"
    archive_dir.mkdir(parents=True, exist_ok=True)
    artifact = archive_dir / f"{digest[:16]}_{safe_name}"
    if not artifact.exists():
        artifact.write_bytes(raw)
    stored = record_machine_capture(
        source_type=f"local_{parsed.source_type}", source_name=match["path"], sha256=digest,
        summary={**parsed.summary, "local_discovery": True, "archived_artifact": str(artifact.relative_to(ROOT))},
        settings=parsed.settings, material_presets=parsed.material_presets, warnings=parsed.warnings,
        machine_profile_id=req.machine_profile_id,
    )
    return {
        "imported": True, "source_type": parsed.source_type, "source_path": match["path"],
        "material_preset_count": len(parsed.material_presets), "material_presets": parsed.material_presets[:200],
        "settings": parsed.settings, "warnings": parsed.warnings, "stored": stored, "sha256": digest,
        "archived_artifact": str(artifact.relative_to(ROOT)),
    }


# WHY: Interpreta texto GRBL pegado/subido sin necesidad de conectar la grabadora.
@app.post("/api/machine/grbl/parse")
def machine_parse_grbl(req: GrblParseRequest) -> dict[str, Any]:
    _require_license()
    return parse_grbl_dump(req.text)


# WHY: Ejecuta el probe read-only limitado a $I/$$ y registra la captura.
@app.post("/api/machine/grbl/probe")
def machine_probe_grbl(req: GrblProbeRequest) -> dict[str, Any]:
    _require_license()
    try:
        result = probe_grbl_readonly(req.port, req.baud)
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer GRBL en modo seguro: {exc}") from exc
    machine = load_machines().get(req.machine_profile_id) if req.machine_profile_id else None
    result["profile_diagnostics"] = compare_grbl_to_profile(result, machine)
    capture = record_machine_capture(
        source_type="grbl_readonly_probe",
        source_name=f"{req.port}@{req.baud}",
        sha256=sha256_bytes("\n".join(result.get("raw_lines", [])).encode("utf-8")),
        summary={
            "port": req.port,
            "baud": req.baud,
            "settings_count": len(result.get("settings", {})),
            "read_only": True,
        },
        settings=result.get("settings", {}),
        material_presets=[],
        warnings=[],
        machine_profile_id=req.machine_profile_id,
    )
    result["capture"] = capture
    return result


# WHY: Importa configuraciones subidas de LightBurn/LaserGRBL/GRBL a través del parser unificado.
@app.post("/api/machine/import")
async def machine_import(file: UploadFile = File(...), machine_profile_id: str | None = None) -> dict[str, Any]:
    """Import shop-owned LightBurn/GRBL exports without changing the controller."""
    _require_license()
    raw = await file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "Archivo de configuración demasiado grande (>50 MB)")
    filename = file.filename or "import.bin"
    # Keep an immutable local copy of the shop-owned export used for this capture.
    # The hash + sanitized filename gives repeatable provenance without trusting paths
    # supplied by the browser.
    digest = sha256_bytes(raw)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)[:120] or "import.bin"
    archive_dir = ROOT / "data" / "machine_imports"
    archive_dir.mkdir(parents=True, exist_ok=True)
    artifact = archive_dir / f"{digest[:16]}_{safe_name}"
    if not artifact.exists():
        artifact.write_bytes(raw)
    try:
        parsed = import_configuration_bytes(filename, raw)
    except Exception as exc:
        raise HTTPException(400, f"No se pudo interpretar {filename}: {exc}") from exc
    stored = record_machine_capture(
        source_type=parsed.source_type,
        source_name=filename,
        sha256=digest,
        summary={**parsed.summary, "archived_artifact": str(artifact.relative_to(ROOT))},
        settings=parsed.settings,
        material_presets=parsed.material_presets,
        warnings=parsed.warnings,
        machine_profile_id=machine_profile_id,
    )
    return {
        "imported": True,
        "source_type": parsed.source_type,
        "summary": parsed.summary,
        "settings": parsed.settings,
        "material_presets": parsed.material_presets[:200],
        "material_preset_count": len(parsed.material_presets),
        "warnings": parsed.warnings,
        "stored": stored,
        "sha256": digest,
        "archived_artifact": str(artifact.relative_to(ROOT)),
    }


# WHY: Devuelve capturas y presets para selección/auditoría en la UI.
@app.get("/api/machine/captures")
def machine_capture_history(limit: int = 100) -> dict[str, Any]:
    _require_license()
    return {
        "captures": machine_captures(max(1, min(limit, 500))),
        "material_presets": material_presets(2000),
    }

# ---------------------------------------------------------------------------
# Jig calibration / reference geometry
# ---------------------------------------------------------------------------

# WHY: Genera referencias/archivo de calibración de un jig sin mezclarlas con grabado productivo.
@app.get("/api/calibration/jig/{jig_id}")
def calibration_jig(jig_id: str) -> dict[str, Any]:
    _require_license()
    jig = load_jigs().get(jig_id)
    if not jig:
        raise HTTPException(404, "Jig no encontrado")
    machine = load_machines().get(jig.machine_profile_id)
    if not machine:
        raise HTTPException(500, "Perfil de máquina del jig no encontrado")
    points = jig_reference_points(jig)
    return {
        "jig": jig.model_dump(),
        "machine": machine.model_dump(),
        "reference_points": [p.model_dump() for p in points],
        "svg": calibration_target_svg(machine, jig),
        "instructions": [
            "Use una placa/material de sacrificio; nunca calibre sobre un activo bueno.",
            "Alinee P0 con el datum físico del jig y use Frame antes de marcar referencias.",
            "Mida P0/PX/PY y capture los valores; Marking Studio sólo diagnostica, no mueve ni corrige la máquina.",
        ],
    }


# WHY: Evalúa mediciones de P0/PX/PY y devuelve errores geométricos para decisión humana.
@app.post("/api/calibration/evaluate")
def calibration_evaluate(req: CalibrationEvaluationRequest) -> dict[str, Any]:
    _require_license()
    jig = load_jigs().get(req.jig_id)
    if not jig:
        raise HTTPException(404, "Jig no encontrado")
    try:
        result = evaluate_reference_points(jig_reference_points(jig), req.measured)
    except Exception as exc:
        raise HTTPException(400, f"No se pudo evaluar la calibración: {exc}") from exc
    return {"jig_id": jig.id, **result}


# ---------------------------------------------------------------------------
# Locally proven workshop presets
# ---------------------------------------------------------------------------

# WHY: Guarda un ajuste del área y sólo lo marca validado si el operador confirma misma máquina/superficie.
@app.post("/api/materials/shop-preset")
def save_shop_material_preset(req: ShopMaterialPresetRequest) -> dict[str, Any]:
    _require_license()
    machine = load_machines().get(req.machine_profile_id)
    if not machine:
        raise HTTPException(404, "Perfil de máquina no encontrado")
    stored = record_shop_material_preset(**req.model_dump())
    return {
        "saved": True,
        "stored": stored,
        "status": "validated" if req.validated_on_exact_machine_surface else "draft",
        "warning": None if req.validated_on_exact_machine_surface else "Queda como borrador hasta validarlo en la misma máquina y superficie.",
    }


# ---------------------------------------------------------------------------
# LaserGRBL local material database discovery (Windows workstation)
# ---------------------------------------------------------------------------

# WHY: Descubre bibliotecas LaserGRBL locales sin importarlas ni cambiarlas.
@app.get("/api/machine/lasergrbl/discover")
def machine_lasergrbl_discover() -> dict[str, Any]:
    _require_license()
    result = discover_lasergrbl_artifacts()
    result["note"] = "Detección local y de solo lectura de UserMaterials.psh/StandardMaterials.psh de LaserGRBL."
    return result


# WHY: Importa una biblioteca LaserGRBL seleccionada en modo sólo lectura y registra sus presets.
@app.post("/api/machine/lasergrbl/import-local")
def machine_lasergrbl_import_local(req: LocalArtifactImportRequest) -> dict[str, Any]:
    _require_license()
    discovered = discover_lasergrbl_artifacts()
    match = next((x for x in discovered["artifacts"] if str(Path(x["path"]).resolve()) == str(Path(req.path).expanduser().resolve())), None)
    if not match:
        raise HTTPException(400, "La ruta no pertenece a los artefactos LaserGRBL detectados")
    try:
        parsed = import_discovered_lasergrbl_artifact(req.path, discovered["artifacts"])
        raw = Path(match["path"]).read_bytes()
    except Exception as exc:
        raise HTTPException(400, f"No se pudo importar la base LaserGRBL: {exc}") from exc
    digest = sha256_bytes(raw)
    stored = record_machine_capture(
        source_type=f"local_{parsed.source_type}", source_name=match["path"], sha256=digest,
        summary={**parsed.summary, "local_discovery": True}, settings=parsed.settings,
        material_presets=parsed.material_presets, warnings=parsed.warnings,
        machine_profile_id=req.machine_profile_id,
    )
    return {
        "imported": True, "source_type": parsed.source_type, "source_path": match["path"],
        "material_preset_count": len(parsed.material_presets), "material_presets": parsed.material_presets[:200],
        "warnings": parsed.warnings, "stored": stored, "sha256": digest,
    }
