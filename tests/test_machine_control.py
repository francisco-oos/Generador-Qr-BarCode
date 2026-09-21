from __future__ import annotations

import re
import time

import pytest
from fastapi.testclient import TestClient

from app.config_loader import load_machines
from app.db import record_shop_material_preset
from app.machine_control import (
    GrblControlService,
    build_grbl_gcode,
    extract_linear_svg_paths,
    generate_process_template,
    prepare_machine_job,
)
from app.main import app


# WHY: Crea presets locales explícitamente validados para que las pruebas de control nunca dependan de rangos web o fixtures ambiguos.
def validated_preset(operation: str, *, power: float = 30, interval: float | None = 0.4, laser_mode: str = "M4") -> int:
    stored = record_shop_material_preset(
        name=f"CI {operation} {time.time_ns()}",
        machine_profile_id="sculpfun_s9_pro_10w",
        material="material sacrificial CI",
        surface_or_model="fixture",
        operation=operation,
        speed_mm_min=1200,
        power_percent=power,
        passes=1,
        interval_mm=interval,
        focus_reference_mm=50,
        laser_mode=laser_mode,
        validated_on_exact_machine_surface=True,
        notes="test fixture",
    )
    return stored["material_preset_ids"][0]


# WHY: Verifica líneas y Bézier aplanadas, pero mantiene bloqueados transforms y arcos aún no auditados.
def test_svg_parser_accepts_lines_and_flattens_bezier_but_rejects_unsafe_constructs():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><g data-operation="cut"><path d="M 1 1 L 9 1 L 9 9 L 1 9 Z"/></g></svg>'
    paths, closed = extract_linear_svg_paths(svg)
    assert closed == [True]
    assert paths[0][0] == (1.0, 1.0)
    assert paths[0][-1] == (1.0, 1.0)

    cubic, _ = extract_linear_svg_paths('<svg xmlns="http://www.w3.org/2000/svg"><path d="M 0 0 C 0 5 5 5 5 0"/></svg>')
    assert len(cubic[0]) > 2
    assert cubic[0][0] == (0.0, 0.0)
    assert cubic[0][-1] == (5.0, 0.0)

    quadratic, _ = extract_linear_svg_paths('<svg xmlns="http://www.w3.org/2000/svg"><path d="M 0 0 Q 2.5 5 5 0"/></svg>')
    assert len(quadratic[0]) > 2
    assert quadratic[0][-1] == (5.0, 0.0)

    with pytest.raises(ValueError, match="Arcos SVG"):
        extract_linear_svg_paths('<svg xmlns="http://www.w3.org/2000/svg"><path d="M 0 0 A 5 5 0 0 1 10 10"/></svg>')
    with pytest.raises(ValueError, match="Transformaciones"):
        extract_linear_svg_paths('<svg xmlns="http://www.w3.org/2000/svg"><g transform="translate(1 1)"><path d="M 0 0 L 2 2"/></g></svg>')


# WHY: Garantiza que cada plantilla de proceso sea geometría pura y pueda pasar por el compilador lineal.
def test_process_templates_are_parameter_free_and_compilable():
    for template_id in ("line_engrave_card", "fill_engrave_patch", "cut_geometry_coupon", "cut_papercut_panel"):
        item = generate_process_template(template_id, 80, 60)
        assert item["contains_machine_parameters"] is False
        assert item["requires_validated_material_preset"] is True
        paths, _ = extract_linear_svg_paths(item["svg"])
        assert paths


# WHY: Comprueba que un preset validado de la máquina exacta produce un job opaco y G-code con potencia escalada por $30 real.
def test_prepare_job_uses_validated_preset_and_builds_safe_relative_gcode():
    preset_id = validated_preset("engrave", power=25, interval=1.0, laser_mode="M4")
    machine = load_machines()["sculpfun_s9_pro_10w"]
    svg = generate_process_template("line_engrave_card", 60, 40)["svg"]
    result = prepare_machine_job(
        svg=svg,
        machine=machine,
        material_preset_id=preset_id,
        operation="line_engrave",
    )
    from app.machine_control import JOB_STORE
    job = JOB_STORE.get(result["job_id"])
    gcode = build_grbl_gcode(job, 1000)
    assert gcode[:3] == ["G21", "G91", "M5"]
    assert "M4 S250" in gcode
    assert gcode[-2:] == ["M5", "G90"]
    assert not any(line.startswith("$32=") or line.startswith("$30=") for line in gcode)


# WHY: Demuestra que fill no inventa hatch; usa exclusivamente interval_mm del preset validado y genera líneas abiertas.
def test_fill_engrave_uses_validated_interval():
    preset_id = validated_preset("engrave", interval=2.0)
    machine = load_machines()["sculpfun_s9_pro_10w"]
    svg = generate_process_template("fill_engrave_patch", 40, 30)["svg"]
    result = prepare_machine_job(
        svg=svg,
        machine=machine,
        material_preset_id=preset_id,
        operation="fill_engrave",
    )
    assert result["path_count"] > 5
    assert result["interval_mm"] == 2.0


# WHY: Rechaza presets borrador antes de producir un job que pudiera energizar la máquina.
def test_direct_control_rejects_unvalidated_material_preset():
    stored = record_shop_material_preset(
        name=f"CI draft {time.time_ns()}",
        machine_profile_id="sculpfun_s9_pro_10w",
        material="draft",
        surface_or_model="fixture",
        operation="cut",
        speed_mm_min=500,
        power_percent=70,
        passes=1,
        interval_mm=None,
        focus_reference_mm=50,
        laser_mode="M3",
        validated_on_exact_machine_surface=False,
        notes="must not run",
    )
    machine = load_machines()["sculpfun_s9_pro_10w"]
    svg = generate_process_template("cut_geometry_coupon", 50, 40)["svg"]
    with pytest.raises(ValueError, match="validado"):
        prepare_machine_job(
            svg=svg,
            machine=machine,
            material_preset_id=stored["material_preset_ids"][0],
            operation="cut",
        )


# WHY: Simula un GRBL completo para validar frame, streaming y retorno a origen sin necesitar hardware durante CI.
def test_control_service_frames_then_streams_generated_job_only():
    class FakeTransport:
        instances = []

        def __init__(self, port, baud):
            self.port = port
            self.baud = baud
            self.lines = []
            self.realtime = []
            FakeTransport.instances.append(self)

        def query_controller(self):
            return {"laser_mode": 1, "s_value_max": 1000, "settings": {"$30": 1000, "$32": 1}}

        def send_line(self, line):
            self.lines.append(line)
            return "ok"

        def send_realtime(self, payload):
            self.realtime.append(payload)

        def query_status(self):
            return {"raw": "<Idle|MPos:0,0,0>", "state": "Idle"}

        def close(self):
            pass

    preset_id = validated_preset("cut", power=60, interval=None, laser_mode="M3")
    machine = load_machines()["sculpfun_s9_pro_10w"]
    svg = generate_process_template("cut_geometry_coupon", 45, 35)["svg"]
    result = prepare_machine_job(svg=svg, machine=machine, material_preset_id=preset_id, operation="cut")
    from app.machine_control import JOB_STORE
    job = JOB_STORE.get(result["job_id"])
    service = GrblControlService(transport_factory=FakeTransport)
    frame = service.frame(job, "FAKE", 115200, 1000)
    assert frame["laser_enabled"] is False
    assert all(not line.startswith(("M3", "M4")) for line in FakeTransport.instances[-1].lines)
    service.start(job, "FAKE", 115200)
    deadline = time.monotonic() + 2
    while service.status()["state"] not in {"COMPLETE", "ERROR", "ABORTED"} and time.monotonic() < deadline:
        time.sleep(0.01)
    status = service.status()
    assert status["state"] == "COMPLETE"
    streamed = FakeTransport.instances[-1].lines
    assert "M3 S600" in streamed
    assert streamed[-2:] == ["M5", "G90"]


# WHY: Valida el contrato HTTP: plantillas y compile están disponibles, pero Start exige confirmaciones físicas.
def test_machine_control_api_contract_and_confirmation_gate():
    preset_id = validated_preset("engrave", power=20, interval=1.0, laser_mode="M4")
    with TestClient(app) as client:
        caps = client.get("/api/machine/control/capabilities")
        assert caps.status_code == 200
        assert caps.json()["validated_preset_required"] is True
        template = client.post("/api/machine/control/process-template", json={
            "template_id": "line_engrave_card", "width_mm": 50, "height_mm": 30
        })
        assert template.status_code == 200
        compiled = client.post("/api/machine/control/compile", json={
            "svg": template.json()["svg"],
            "machine_profile_id": "sculpfun_s9_pro_10w",
            "material_preset_id": preset_id,
            "operation": "line_engrave",
        })
        assert compiled.status_code == 200, compiled.text
        job_id = compiled.json()["job_id"]
        start = client.post("/api/machine/control/start", json={
            "job_id": job_id,
            "port": "FAKE",
            "confirm_workspace_clear": False,
            "confirm_material_matches_preset": True,
            "confirm_protective_measures": True,
        })
        assert start.status_code == 400


# WHY: Exige que todas las rutas directas existan realmente en FastAPI para evitar decoradores comentados o integración parcial.
def test_direct_control_routes_are_registered():
    paths = {route.path for route in app.routes}
    expected = {
        "/api/machine/control/capabilities",
        "/api/machine/control/status",
        "/api/machine/control/process-template",
        "/api/machine/control/compile",
        "/api/machine/control/frame",
        "/api/machine/control/start",
        "/api/machine/control/pause",
        "/api/machine/control/resume",
        "/api/machine/control/abort",
        "/api/machine/control/jog",
    }
    assert expected <= paths, sorted(expected - paths)


# WHY: Un path compuesto de barcode/QR debe producir trayectorias independientes y nunca unir módulos con un movimiento energizado.
def test_compound_barcode_path_is_split_into_independent_subpaths():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M 1 1 h 2 v 5 h -2 z M 5 1 h 1 v 5 h -1 z"/></svg>'
    paths, closed = extract_linear_svg_paths(svg)
    assert len(paths) == 2
    assert closed == [True, True]
    assert paths[0][0] == paths[0][-1] == (1.0, 1.0)
    assert paths[1][0] == paths[1][-1] == (5.0, 1.0)


# WHY: Demuestra que la evolución controla también los SVG de identificación existentes y no sólo los nuevos diseños decorativos.
def test_existing_code128_production_svg_can_compile_for_direct_engraving():
    preset_id = validated_preset("engrave", power=18, interval=0.8, laser_mode="M4")
    with TestClient(app) as client:
        rendered = client.post("/api/render", json={
            "template_id": "inova_quantum_code128_v1",
            "data": {"manufacturer_id": "525499"},
            "capture_mode": "manual",
            "output": "svg",
            "svg_mode": "production",
            "text_as_paths": True,
        })
        assert rendered.status_code == 200, rendered.text
        svg = rendered.json()["svg"]
        paths, _ = extract_linear_svg_paths(svg)
        assert len(paths) > 10
        compiled = client.post("/api/machine/control/compile", json={
            "svg": svg,
            "machine_profile_id": "sculpfun_s9_pro_10w",
            "material_preset_id": preset_id,
            "operation": "line_engrave",
        })
        assert compiled.status_code == 200, compiled.text
        assert compiled.json()["path_count"] >= len(paths)


# WHY: Los controles críticos real-time deben usar exactamente los bytes definidos por GRBL y no convertirse en líneas G-code.
def test_realtime_pause_resume_abort_bytes_are_exact():
    class RealtimeOnly:
        def __init__(self):
            self.payloads = []
        def send_realtime(self, payload):
            self.payloads.append(payload)

    transport = RealtimeOnly()
    service = GrblControlService()
    service._transport = transport
    service._state = "RUNNING"
    paused = service.pause()
    assert paused["state"] == "HOLD"
    assert transport.payloads == [b"!"]

    resumed = service.resume()
    assert resumed["state"] == "RUNNING"
    assert transport.payloads == [b"!", b"~"]

    aborted = service.abort()
    assert aborted["state"] == "ABORTED"
    assert transport.payloads == [b"!", b"~", b"!", b"\x18"]


# WHY: Frame y jog son movimientos de posicionamiento y deben permanecer incapaces de energizar el láser.
def test_frame_and_jog_never_emit_laser_power_commands():
    from app.machine_control import JOB_STORE, build_frame_gcode

    preset_id = validated_preset("cut", power=60, interval=None, laser_mode="M3")
    machine = load_machines()["sculpfun_s9_pro_10w"]
    svg = generate_process_template("cut_geometry_coupon", 45, 35)["svg"]
    result = prepare_machine_job(svg=svg, machine=machine, material_preset_id=preset_id, operation="cut")
    job = JOB_STORE.get(result["job_id"])
    frame_lines = build_frame_gcode(job, 1000)
    joined = "\n".join(frame_lines)
    assert "M3" not in joined and "M4" not in joined
    assert not re.search(r"\bS\d", joined)

    class JogTransport:
        instances = []
        def __init__(self, port, baud):
            self.lines = []
            JogTransport.instances.append(self)
        def query_controller(self):
            return {"laser_mode": 1, "s_value_max": 1000}
        def send_line(self, line):
            self.lines.append(line)
            return "ok"
        def close(self):
            pass

    service = GrblControlService(transport_factory=JogTransport)
    moved = service.jog("FAKE", 115200, 10, -5, 1200)
    assert moved["laser_enabled"] is False
    assert JogTransport.instances[-1].lines == ["$J=G91 X10 Y-5 F1200"]
    assert not any(token in moved["command"] for token in ("M3", "M4", " S"))
