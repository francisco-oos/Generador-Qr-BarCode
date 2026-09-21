"""Experimental direct GRBL control and machine-job compilation.

This module is intentionally narrow: it accepts only linear SVG geometry generated
or sanitized by Marking Studio, binds it to a locally validated material preset,
frames with the laser disabled, and streams GRBL 1.1 only after explicit physical
confirmations.  It does not auto-discover cutting power from the Internet and it
never rewrites GRBL firmware settings.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon

from . import machine_bridge
from .db import material_preset_control_context

MAX_SVG_PATHS = 10000
MAX_POINTS = 250000
MAX_GCODE_LINES = 500000
FRAME_VALID_SECONDS = 900
_ALLOWED_TAGS = {"svg", "g", "path", "metadata", "title", "desc"}
_TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


# WHY: Representa un plan ya validado semánticamente antes de convertirlo a órdenes específicas del controlador.
@dataclass
class PreparedMachineJob:
    job_id: str
    machine_profile_id: str
    material_preset_id: int
    operation: str
    paths: list[list[tuple[float, float]]]
    closed: list[bool]
    speed_mm_min: float
    power_percent: float
    passes: int
    interval_mm: float | None
    laser_mode: str
    offset_x_mm: float
    offset_y_mm: float
    bounds_mm: tuple[float, float, float, float]
    source_sha256: str
    frame_verified_at: float | None = None
    frame_verified_port: str | None = None


# WHY: Mantiene jobs compilados en memoria para que el endpoint de arranque no acepte G-code arbitrario enviado por el navegador.
class MachineJobStore:
    # WHY: Inicializa un almacén pequeño y bloqueado; no pretende sustituir una cola persistente de producción.
    def __init__(self, max_jobs: int = 50):
        self.max_jobs = max_jobs
        self._lock = threading.RLock()
        self._jobs: dict[str, PreparedMachineJob] = {}

    # WHY: Guarda únicamente planes creados por el compilador interno y limita crecimiento de memoria.
    def put(self, job: PreparedMachineJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            while len(self._jobs) > self.max_jobs:
                self._jobs.pop(next(iter(self._jobs)))

    # WHY: Recupera un plan por identificador opaco sin permitir al cliente redefinir su geometría o parámetros.
    def get(self, job_id: str) -> PreparedMachineJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ValueError("Job compilado no encontrado o expirado")
            return job

    # WHY: Registra que el mismo job fue enmarcado con láser apagado en el puerto que luego podrá ejecutarlo.
    def mark_framed(self, job_id: str, port: str) -> None:
        with self._lock:
            job = self.get(job_id)
            job.frame_verified_at = time.time()
            job.frame_verified_port = port


JOB_STORE = MachineJobStore()


# WHY: Extrae el nombre local de una etiqueta XML sin depender del namespace SVG.
def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# WHY: Mide separación perpendicular punto-línea para decidir cuándo una curva ya puede representarse físicamente por un segmento.
def _point_line_distance(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx-ax, by-ay
    denom = math.hypot(dx, dy)
    if denom <= 1e-12:
        return math.hypot(px-ax, py-ay)
    return abs(dy*px - dx*py + bx*ay - by*ax) / denom


# WHY: Aplana Bézier cuadrática adaptativamente a una tolerancia física en milímetros sin depender del zoom o DPI.
def _flatten_quadratic(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float],
                       tolerance_mm: float = 0.05, depth: int = 0) -> list[tuple[float, float]]:
    if depth >= 12 or _point_line_distance(p1, p0, p2) <= tolerance_mm:
        return [p2]
    p01=((p0[0]+p1[0])/2,(p0[1]+p1[1])/2)
    p12=((p1[0]+p2[0])/2,(p1[1]+p2[1])/2)
    mid=((p01[0]+p12[0])/2,(p01[1]+p12[1])/2)
    return _flatten_quadratic(p0,p01,mid,tolerance_mm,depth+1)+_flatten_quadratic(mid,p12,p2,tolerance_mm,depth+1)


# WHY: Aplana Bézier cúbica adaptativamente para conservar texto/logos vectoriales sin entregar curvas opacas al streamer GRBL.
def _flatten_cubic(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float],
                   p3: tuple[float, float], tolerance_mm: float = 0.05, depth: int = 0) -> list[tuple[float, float]]:
    flat=max(_point_line_distance(p1,p0,p3),_point_line_distance(p2,p0,p3))
    if depth >= 12 or flat <= tolerance_mm:
        return [p3]
    p01=((p0[0]+p1[0])/2,(p0[1]+p1[1])/2)
    p12=((p1[0]+p2[0])/2,(p1[1]+p2[1])/2)
    p23=((p2[0]+p3[0])/2,(p2[1]+p3[1])/2)
    p012=((p01[0]+p12[0])/2,(p01[1]+p12[1])/2)
    p123=((p12[0]+p23[0])/2,(p12[1]+p23[1])/2)
    mid=((p012[0]+p123[0])/2,(p012[1]+p123[1])/2)
    return _flatten_cubic(p0,p01,p012,mid,tolerance_mm,depth+1)+_flatten_cubic(mid,p123,p23,p3,tolerance_mm,depth+1)


# WHY: Convierte paths SVG en subpaths lineales independientes y aplana Bézier para conservar texto/QR/barcodes completos.
def _parse_linear_path(d: str) -> list[tuple[list[tuple[float, float]], bool]]:
    tokens = _TOKEN_RE.findall(d or "")
    if not tokens:
        raise ValueError("Path SVG vacío")
    result: list[tuple[list[tuple[float, float]], bool]] = []
    points: list[tuple[float, float]] = []
    i = 0
    cmd = ""
    x = y = 0.0
    start: tuple[float, float] | None = None
    previous_cmd = ""
    last_control: tuple[float, float] | None = None

    # WHY: Consume un número del token stream con mensaje de error uniforme.
    def number() -> float:
        nonlocal i
        if i >= len(tokens) or tokens[i].isalpha():
            raise ValueError("Path SVG incompleto")
        value = float(tokens[i])
        if not math.isfinite(value):
            raise ValueError("Coordenada SVG no finita")
        i += 1
        return value

    # WHY: Resuelve una coordenada absoluta/relativa contra el punto actual antes de modificarlo.
    def pair(relative: bool, base_x: float, base_y: float) -> tuple[float, float]:
        nx, ny = number(), number()
        return (base_x + nx, base_y + ny) if relative else (nx, ny)

    # WHY: Finaliza el subpath actual sin unirlo accidentalmente al siguiente movimiento M.
    def finish(closed: bool) -> None:
        nonlocal points, start
        if points:
            if len(points) < 2:
                raise ValueError("Subpath SVG necesita al menos dos puntos")
            result.append((points, closed))
        points = []
        start = None

    while i < len(tokens):
        if tokens[i].isalpha():
            next_cmd = tokens[i]
            i += 1
            if next_cmd in {"M", "m"} and points:
                finish(False)
            cmd = next_cmd
        if not cmd:
            raise ValueError("Path SVG sin comando inicial")
        if cmd in {"A", "a"}:
            raise ValueError("Arcos SVG A/a no están habilitados para control directo; conviértalos a curvas/segmentos")
        if cmd in {"Z", "z"}:
            if start is not None and points and points[-1] != start:
                points.append(start)
            if start is not None:
                x, y = start
            finish(True)
            previous_cmd, last_control, cmd = cmd, None, ""
            continue
        if cmd in {"M", "m", "L", "l"}:
            nx, ny = pair(cmd.islower(), x, y)
            x, y = nx, ny
            if not points:
                start = (x, y)
            points.append((x, y))
            previous_cmd, last_control = cmd, None
            if cmd in {"M", "m"}:
                cmd = "L" if cmd == "M" else "l"
            continue
        if cmd in {"H", "h"}:
            nx = number()
            x = x + nx if cmd == "h" else nx
            if not points: start = (x, y)
            points.append((x, y)); previous_cmd, last_control = cmd, None
            continue
        if cmd in {"V", "v"}:
            ny = number()
            y = y + ny if cmd == "v" else ny
            if not points: start = (x, y)
            points.append((x, y)); previous_cmd, last_control = cmd, None
            continue
        if cmd in {"Q", "q"}:
            p0=(x,y); p1=pair(cmd.islower(),x,y); p2=pair(cmd.islower(),x,y)
            points.extend(_flatten_quadratic(p0,p1,p2))
            x,y=p2; previous_cmd, last_control=cmd,p1
            continue
        if cmd in {"T", "t"}:
            p0=(x,y)
            p1=(2*x-last_control[0],2*y-last_control[1]) if previous_cmd in {"Q","q","T","t"} and last_control else p0
            p2=pair(cmd.islower(),x,y)
            points.extend(_flatten_quadratic(p0,p1,p2))
            x,y=p2; previous_cmd, last_control=cmd,p1
            continue
        if cmd in {"C", "c"}:
            p0=(x,y); p1=pair(cmd.islower(),x,y); p2=pair(cmd.islower(),x,y); p3=pair(cmd.islower(),x,y)
            points.extend(_flatten_cubic(p0,p1,p2,p3))
            x,y=p3; previous_cmd, last_control=cmd,p2
            continue
        if cmd in {"S", "s"}:
            p0=(x,y)
            p1=(2*x-last_control[0],2*y-last_control[1]) if previous_cmd in {"C","c","S","s"} and last_control else p0
            p2=pair(cmd.islower(),x,y); p3=pair(cmd.islower(),x,y)
            points.extend(_flatten_cubic(p0,p1,p2,p3))
            x,y=p3; previous_cmd, last_control=cmd,p2
            continue
        raise ValueError(f"Comando SVG no soportado: {cmd}")
    if points:
        finish(False)
    if not result:
        raise ValueError("Path SVG sin geometría")
    return result


# WHY: Recorre SVG saneado, ignora capas de guía y rechaza construcciones que impedirían conocer la geometría física exacta.
def extract_linear_svg_paths(svg: str) -> tuple[list[list[tuple[float, float]]], list[bool]]:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ValueError(f"SVG inválido: {exc}") from exc
    paths: list[list[tuple[float, float]]] = []
    closed: list[bool] = []

    # WHY: Propaga la semántica de capa para excluir guías de preview del trabajo productivo.
    def visit(node: ET.Element, inherited_operation: str | None = None) -> None:
        name = _local_name(node.tag)
        if name not in _ALLOWED_TAGS:
            raise ValueError(f"Elemento SVG no permitido para control directo: {name}")
        if name == "metadata":
            return
        if "transform" in node.attrib:
            raise ValueError("Transformaciones SVG deben aplanarse antes del control directo")
        operation = node.attrib.get("data-operation", inherited_operation)
        if operation == "guide":
            return
        if name == "path":
            d = node.attrib.get("d", "")
            for pts, is_closed in _parse_linear_path(d):
                paths.append(pts)
                closed.append(is_closed)
                if len(paths) > MAX_SVG_PATHS:
                    raise ValueError("Demasiados paths SVG para control directo")
        for child in list(node):
            visit(child, operation)

    visit(root)
    total_points = sum(len(p) for p in paths)
    if not paths:
        raise ValueError("SVG sin paths productivos")
    if total_points > MAX_POINTS:
        raise ValueError("SVG demasiado complejo para control directo")
    return paths, closed


# WHY: Calcula límites físicos de todos los paths para impedir que un job exceda el área declarada de la máquina.
def _bounds(paths: list[list[tuple[float, float]]]) -> tuple[float, float, float, float]:
    xs = [x for path in paths for x, _ in path]
    ys = [y for path in paths for _, y in path]
    return min(xs), min(ys), max(xs), max(ys)


# WHY: Convierte contornos cerrados en barrido lineal para grabado fill manteniendo el intervalo validado del preset.
def _hatch_paths(paths: list[list[tuple[float, float]]], closed: list[bool], interval_mm: float) -> tuple[list[list[tuple[float, float]]], list[bool]]:
    if interval_mm <= 0:
        raise ValueError("fill_engrave requiere interval_mm > 0")
    out: list[list[tuple[float, float]]] = []
    direction = False
    for pts, is_closed in zip(paths, closed):
        if not is_closed:
            continue
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        polygons = [poly] if isinstance(poly, Polygon) else list(poly.geoms) if isinstance(poly, MultiPolygon) else []
        for shape in polygons:
            if shape.is_empty or shape.area <= 1e-9:
                continue
            minx, miny, maxx, maxy = shape.bounds
            y = miny + interval_mm / 2.0
            while y < maxy:
                probe = LineString([(minx - 1.0, y), (maxx + 1.0, y)])
                inter = shape.intersection(probe)
                segments = [inter] if isinstance(inter, LineString) else list(inter.geoms) if isinstance(inter, MultiLineString) else []
                for seg in segments:
                    coords = [(float(x), float(y0)) for x, y0 in seg.coords]
                    if len(coords) >= 2:
                        if direction:
                            coords.reverse()
                        out.append(coords)
                        direction = not direction
                y += interval_mm
                if len(out) > MAX_SVG_PATHS * 20:
                    raise ValueError("El hatch generaría demasiadas líneas")
    if not out:
        raise ValueError("No hay contornos cerrados aptos para fill_engrave")
    return out, [False] * len(out)


# WHY: Normaliza campos de presets importados/manuales sin asumir una única nomenclatura de LightBurn/LaserGRBL.
def _preset_number(settings: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in settings and settings[key] is not None:
            return settings[key]
    return default


# WHY: Compila sólo con presets validados en la misma máquina/superficie, evitando transformar referencias web en órdenes de producción.
def prepare_machine_job(
    *,
    svg: str,
    machine: Any,
    material_preset_id: int,
    operation: str,
    offset_x_mm: float = 0.0,
    offset_y_mm: float = 0.0,
    current_position_origin: bool = True,
) -> dict[str, Any]:
    if not current_position_origin:
        raise ValueError("v0.10 experimental admite únicamente origen en posición actual + Frame")
    if str(getattr(machine, "controller", "")).upper() != "GRBL":
        raise ValueError("El controlador directo experimental sólo admite GRBL 1.1")
    if not bool(getattr(machine, "direct_machine_output_enabled", False)):
        raise ValueError("El perfil de máquina no tiene control directo habilitado")
    preset = material_preset_control_context(material_preset_id)
    if not preset:
        raise ValueError("Preset de material no encontrado")
    if preset.get("machine_profile_id") != machine.id:
        raise ValueError("El preset fue capturado para otra máquina")
    settings = preset.get("settings") or {}
    if settings.get("validated_on_exact_machine_surface") is not True:
        raise ValueError("Control directo exige preset validado en la misma máquina y superficie")
    speed = float(_preset_number(settings, "speed_mm_min", "speed", default=0) or 0)
    power = float(_preset_number(settings, "power_percent", "maxPower", "power", default=0) or 0)
    passes = int(_preset_number(settings, "passes", "numPasses", "passCount", default=1) or 1)
    interval = _preset_number(settings, "interval_mm", "interval", default=None)
    interval = None if interval is None else float(interval)
    laser_mode = str(_preset_number(settings, "laser_mode", default="unknown")).upper()
    if speed <= 0 or speed > 200000:
        raise ValueError("Preset sin velocidad válida")
    if power <= 0 or power > 100:
        raise ValueError("Preset sin potencia porcentual válida")
    if passes < 1 or passes > 100:
        raise ValueError("Preset con número de pasadas inválido")
    if laser_mode not in {"M3", "M4"}:
        raise ValueError("Preset debe declarar laser_mode M3 o M4 antes de control directo")
    preset_operation = str(preset.get("operation") or "").lower()
    if operation == "cut" and "cut" not in preset_operation and "corte" not in preset_operation:
        raise ValueError("El preset validado no está marcado como operación de corte")
    if operation in {"line_engrave", "fill_engrave"} and not any(k in preset_operation for k in ("engrave", "grab", "scan", "line", "mark")):
        raise ValueError("El preset validado no está marcado como grabado")
    paths, closed = extract_linear_svg_paths(svg)
    if operation == "fill_engrave":
        paths, closed = _hatch_paths(paths, closed, interval or 0.0)
    shifted = [[(x + offset_x_mm, y + offset_y_mm) for x, y in path] for path in paths]
    b = _bounds(shifted)
    if b[0] < -1e-6 or b[1] < -1e-6:
        raise ValueError("El job contiene coordenadas negativas")
    if b[2] > float(machine.bed_width_mm) + 1e-6 or b[3] > float(machine.bed_height_mm) + 1e-6:
        raise ValueError("El job excede el área declarada de la máquina")
    source_sha = hashlib.sha256(svg.encode("utf-8")).hexdigest()
    identity = {
        "machine": machine.id,
        "preset": material_preset_id,
        "operation": operation,
        "speed": speed,
        "power": power,
        "passes": passes,
        "interval": interval,
        "laser_mode": laser_mode,
        "offset": [offset_x_mm, offset_y_mm],
        "bounds": [round(v, 4) for v in b],
        "source_sha256": source_sha,
    }
    job_id = "LJOB-" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()[:16].upper()
    job = PreparedMachineJob(
        job_id=job_id,
        machine_profile_id=machine.id,
        material_preset_id=material_preset_id,
        operation=operation,
        paths=shifted,
        closed=closed,
        speed_mm_min=speed,
        power_percent=power,
        passes=passes,
        interval_mm=interval,
        laser_mode=laser_mode,
        offset_x_mm=offset_x_mm,
        offset_y_mm=offset_y_mm,
        bounds_mm=b,
        source_sha256=source_sha,
    )
    JOB_STORE.put(job)
    return {
        "job_id": job_id,
        "machine_profile_id": machine.id,
        "material_preset_id": material_preset_id,
        "operation": operation,
        "path_count": len(shifted),
        "point_count": sum(len(p) for p in shifted),
        "bounds_mm": [round(v, 4) for v in b],
        "speed_mm_min": speed,
        "power_percent": power,
        "passes": passes,
        "interval_mm": interval,
        "laser_mode": laser_mode,
        "source_sha256": source_sha,
        "frame_required": True,
        "current_position_origin": True,
        "machine_control": True,
        "warnings": [
            "Experimental: requiere Frame con láser apagado antes de Start.",
            "Potencia/velocidad provienen exclusivamente del preset local validado seleccionado.",
        ],
    }


# WHY: Formatea números compactos para G-code reproducible sin ruido decimal innecesario.
def _fmt(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"


# WHY: Convierte un plan validado a G-code relativo, manteniendo M5 en todos los movimientos rápidos y regresando al origen del job.
def build_grbl_gcode(job: PreparedMachineJob, s_value_max: float) -> list[str]:
    if not isinstance(s_value_max, (int, float)) or s_value_max <= 0:
        raise ValueError("GRBL $30 inválido; no se puede escalar potencia")
    s_value = max(1, min(int(round(s_value_max)), int(round(s_value_max * job.power_percent / 100.0))))
    lines = ["G21", "G91", "M5"]
    current_x = current_y = 0.0
    for _pass in range(job.passes):
        for path in job.paths:
            if len(path) < 2:
                continue
            sx, sy = path[0]
            dx, dy = sx - current_x, sy - current_y
            lines.extend(["M5", f"G0 X{_fmt(dx)} Y{_fmt(dy)}"])
            current_x, current_y = sx, sy
            lines.append(f"{job.laser_mode} S{s_value}")
            first = True
            for x, y in path[1:]:
                dx, dy = x - current_x, y - current_y
                feed = f" F{_fmt(job.speed_mm_min)}" if first else ""
                lines.append(f"G1 X{_fmt(dx)} Y{_fmt(dy)}{feed}")
                current_x, current_y = x, y
                first = False
            lines.append("M5")
    if abs(current_x) > 1e-9 or abs(current_y) > 1e-9:
        lines.append(f"G0 X{_fmt(-current_x)} Y{_fmt(-current_y)}")
    lines.extend(["M5", "G90"])
    if len(lines) > MAX_GCODE_LINES:
        raise ValueError("Job genera demasiado G-code para el controlador experimental")
    return lines


# WHY: Produce un recorrido rectangular a potencia cero para validar colocación y límites antes de permitir un trabajo energizado.
def build_frame_gcode(job: PreparedMachineJob, feed_mm_min: float) -> list[str]:
    minx, miny, maxx, maxy = job.bounds_mm
    w, h = maxx - minx, maxy - miny
    return [
        "G21", "G91", "M5",
        f"G1 X{_fmt(minx)} Y{_fmt(miny)} F{_fmt(feed_mm_min)}",
        f"G1 X{_fmt(w)} Y0",
        f"G1 X0 Y{_fmt(h)}",
        f"G1 X{_fmt(-w)} Y0",
        f"G1 X0 Y{_fmt(-h)}",
        f"G1 X{_fmt(-minx)} Y{_fmt(-miny)}",
        "M5", "G90",
    ]


# WHY: Encapsula pyserial para control productivo; a diferencia del probe read-only no usa fallback POSIX implícito.
class SerialGrblTransport:
    # WHY: Abre un puerto con timeouts finitos para que un controlador desconectado no congele el servidor.
    def __init__(self, port: str, baud: int = 115200, timeout: float = 1.0):
        if machine_bridge.serial is None:
            raise RuntimeError("pyserial es obligatorio para control directo")
        self.ser = machine_bridge.serial.Serial(port=port, baudrate=baud, timeout=timeout, write_timeout=timeout)
        self.timeout = timeout
        self._write_lock = threading.Lock()

    # WHY: Cierra el puerto serial de forma explícita al terminar, abortar o fallar un job.
    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass

    # WHY: Escribe una línea GRBL ASCII y espera confirmación ok/error antes de avanzar, priorizando determinismo sobre throughput.
    def send_line(self, line: str) -> str:
        payload = (line.strip() + "\n").encode("ascii")
        with self._write_lock:
            self.ser.write(payload)
            self.ser.flush()
        deadline = time.monotonic() + max(2.0, self.timeout * 5)
        while time.monotonic() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            low = text.lower()
            if low == "ok":
                return text
            if low.startswith("error") or low.startswith("alarm"):
                raise RuntimeError(f"GRBL rechazó '{line}': {text}")
        raise TimeoutError(f"GRBL no confirmó '{line}'")

    # WHY: Envía comandos real-time GRBL sin newline para pausa, reanudación, status o reset.
    def send_realtime(self, payload: bytes) -> None:
        with self._write_lock:
            self.ser.write(payload)
            self.ser.flush()

    # WHY: Consulta el estado real GRBL para distinguir líneas aceptadas de movimiento físicamente terminado.
    def query_status(self) -> dict[str, Any]:
        self.send_realtime(b"?")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            if text.startswith("<") and text.endswith(">"):
                state = text[1:-1].split("|", 1)[0]
                return {"raw": text, "state": state}
        raise TimeoutError("GRBL no respondió al status '?'")

    # WHY: Lee $I/$ en la misma conexión que ejecutará el job para evitar usar un diagnóstico obsoleto.
    def query_controller(self) -> dict[str, Any]:
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass
        lines: list[str] = []
        for command in ("$I", "$$"):
            with self._write_lock:
                self.ser.write((command + "\n").encode("ascii"))
                self.ser.flush()
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                raw = self.ser.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="replace").strip()
                if text:
                    lines.append(text)
                if text.lower() == "ok":
                    break
            else:
                raise TimeoutError(f"Sin respuesta a {command}")
        return machine_bridge.parse_grbl_dump("\n".join(lines))


# WHY: Coordina una única máquina local y expone estado/pause/abort sin permitir ejecución paralela sobre el mismo USB.
class GrblControlService:
    # WHY: Inicializa estado seguro desconectado y permite inyectar transporte simulado en pruebas.
    def __init__(self, transport_factory=SerialGrblTransport):
        self.transport_factory = transport_factory
        self._lock = threading.RLock()
        self._transport: SerialGrblTransport | Any | None = None
        self._thread: threading.Thread | None = None
        self._state = "IDLE"
        self._job_id: str | None = None
        self._progress = 0.0
        self._line_index = 0
        self._line_total = 0
        self._error: str | None = None
        self._abort = threading.Event()

    # WHY: Devuelve snapshot serializable para UI y auditoría sin exponer el objeto puerto.
    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "job_id": self._job_id,
                "progress": round(self._progress, 4),
                "line_index": self._line_index,
                "line_total": self._line_total,
                "error": self._error,
                "machine_control": True,
            }

    # WHY: Ejecuta una secuencia corta con láser apagado y marca el job como framed sólo tras confirmación completa de GRBL.
    def frame(self, job: PreparedMachineJob, port: str, baud: int, feed_mm_min: float) -> dict[str, Any]:
        with self._lock:
            if self._state not in {"IDLE", "COMPLETE", "ERROR", "ABORTED"}:
                raise ValueError("La máquina está ocupada")
            self._state = "FRAMING"
        transport = self.transport_factory(port, baud)
        try:
            controller = transport.query_controller()
            for line in build_frame_gcode(job, feed_mm_min):
                transport.send_line(line)
            JOB_STORE.mark_framed(job.job_id, port)
            with self._lock:
                self._state = "IDLE"
            return {"framed": True, "job_id": job.job_id, "port": port, "laser_enabled": False, "controller": controller}
        except Exception:
            with self._lock:
                self._state = "ERROR"
            raise
        finally:
            transport.close()

    # WHY: Inicia en background sólo después de Frame reciente y conserva el puerto abierto para hold/resume/abort real-time.
    def start(self, job: PreparedMachineJob, port: str, baud: int) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ValueError("Ya existe un trabajo en ejecución")
            if not job.frame_verified_at or job.frame_verified_port != port or time.time() - job.frame_verified_at > FRAME_VALID_SECONDS:
                raise ValueError("Debe ejecutar Frame exitoso en este mismo puerto antes de Start")
            self._state = "STARTING"
            self._job_id = job.job_id
            self._progress = 0.0
            self._line_index = 0
            self._line_total = 0
            self._error = None
            self._abort.clear()
            self._thread = threading.Thread(target=self._run_job, args=(job, port, baud), daemon=True)
            self._thread.start()
            return self.status()

    # WHY: Ejecuta internamente el stream línea por línea y valida $32/$30 justo antes de energizar.
    def _run_job(self, job: PreparedMachineJob, port: str, baud: int) -> None:
        transport = None
        try:
            transport = self.transport_factory(port, baud)
            with self._lock:
                self._transport = transport
            controller = transport.query_controller()
            if controller.get("laser_mode") != 1:
                raise RuntimeError("GRBL $32 debe estar en 1 antes de control láser directo")
            smax = controller.get("s_value_max")
            if not isinstance(smax, (int, float)) or smax <= 0:
                raise RuntimeError("GRBL $30 no es válido")
            lines = build_grbl_gcode(job, float(smax))
            with self._lock:
                self._line_total = len(lines)
                self._state = "RUNNING"
            for idx, line in enumerate(lines, start=1):
                if self._abort.is_set():
                    raise InterruptedError("Trabajo abortado por operador")
                transport.send_line(line)
                with self._lock:
                    self._line_index = idx
                    # 99 % significa transmitido; 100 % se reserva para GRBL Idle real.
                    self._progress = min(0.99, (idx / max(1, len(lines))) * 0.99)
            with self._lock:
                self._state = "DRAINING"
            deadline = time.monotonic() + 6 * 60 * 60
            while time.monotonic() < deadline:
                if self._abort.is_set():
                    raise InterruptedError("Trabajo abortado por operador")
                machine_status = transport.query_status()
                state = str(machine_status.get("state") or "")
                if state == "Idle":
                    break
                if state.startswith("Alarm"):
                    raise RuntimeError(f"GRBL terminó en estado {state}")
                with self._lock:
                    if state == "Hold":
                        self._state = "HOLD"
                    elif self._state != "HOLD":
                        self._state = "DRAINING"
                time.sleep(0.15)
            else:
                raise TimeoutError("El job fue transmitido pero GRBL no regresó a Idle")
            with self._lock:
                self._state = "COMPLETE"
                self._progress = 1.0
        except InterruptedError:
            with self._lock:
                self._state = "ABORTED"
        except Exception as exc:
            with self._lock:
                if self._abort.is_set():
                    self._state = "ABORTED"
                else:
                    self._state = "ERROR"
                    self._error = str(exc)
            if transport is not None:
                try:
                    transport.send_realtime(b"!")
                    transport.send_realtime(b"\x18")
                except Exception:
                    pass
        finally:
            if transport is not None:
                transport.close()
            with self._lock:
                self._transport = None

    # WHY: Usa feed-hold real-time de GRBL para detener movimiento planificado sin perder inmediatamente el job.
    def pause(self) -> dict[str, Any]:
        with self._lock:
            if self._state != "RUNNING" or self._transport is None:
                raise ValueError("No hay trabajo RUNNING para pausar")
            self._transport.send_realtime(b"!")
            self._state = "HOLD"
            return self.status()

    # WHY: Usa cycle-start real-time para continuar un trabajo previamente puesto en hold por el operador.
    def resume(self) -> dict[str, Any]:
        with self._lock:
            if self._state != "HOLD" or self._transport is None:
                raise ValueError("No hay trabajo HOLD para reanudar")
            self._transport.send_realtime(b"~")
            self._state = "RUNNING"
            return self.status()

    # WHY: Prioriza apagar/detener inmediatamente mediante hold + soft-reset y marca el job como abortado.
    def abort(self) -> dict[str, Any]:
        with self._lock:
            if self._transport is None or self._state not in {"RUNNING", "HOLD", "STARTING"}:
                raise ValueError("No hay trabajo activo para abortar")
            self._abort.set()
            self._transport.send_realtime(b"!")
            self._transport.send_realtime(b"\x18")
            self._state = "ABORTED"
            return self.status()

    # WHY: Ejecuta un jog incremental sin láser y sólo cuando no hay trabajo activo.
    def jog(self, port: str, baud: int, x_mm: float, y_mm: float, feed_mm_min: float) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ValueError("No se permite jog durante un trabajo")
        transport = self.transport_factory(port, baud)
        try:
            controller = transport.query_controller()
            cmd = f"$J=G91 X{_fmt(x_mm)} Y{_fmt(y_mm)} F{_fmt(feed_mm_min)}"
            transport.send_line(cmd)
            return {"jogged": True, "command": cmd, "laser_enabled": False, "controller": controller}
        finally:
            transport.close()


CONTROL_SERVICE = GrblControlService()


# WHY: Genera SVGs geométricos de proceso sin potencia/velocidad para probar corte, línea y relleno con un preset validado aparte.
def generate_process_template(template_id: str, width_mm: float, height_mm: float) -> dict[str, Any]:
    inset = max(3.0, min(width_mm, height_mm) * 0.08)
    w, h = width_mm, height_mm
    if template_id == "line_engrave_card":
        operation = "line_engrave"
        paths = [
            f"M {inset} {inset} L {w-inset} {inset} L {w-inset} {h-inset} L {inset} {h-inset} Z",
            f"M {inset} {inset} L {w-inset} {h-inset}",
            f"M {w-inset} {inset} L {inset} {h-inset}",
        ]
        purpose = "Verificar trazo vectorial, alineación y contraste sin relleno."
    elif template_id == "fill_engrave_patch":
        operation = "fill_engrave"
        paths = [f"M {inset} {inset} L {w-inset} {inset} L {w-inset} {h-inset} L {inset} {h-inset} Z"]
        purpose = "Parche cerrado que el compilador convierte a hatch usando interval_mm del preset."
    elif template_id == "cut_geometry_coupon":
        operation = "cut"
        paths = []
        size = min((w - 2*inset) / 4.0, (h - 2*inset) / 2.0)
        for row in range(2):
            for col in range(4):
                x = inset + col * size
                y = inset + row * size
                m = size * 0.18
                paths.append(f"M {x+m} {y+m} L {x+size-m} {y+m} L {x+size-m} {y+size-m} L {x+m} {y+size-m} Z")
        purpose = "Cupón de geometría repetida para comprobar corte, kerf observado y repetibilidad."
    elif template_id == "cut_papercut_panel":
        operation = "cut"
        paths = [f"M 0 0 L {w} 0 L {w} {h} L 0 {h} Z"]
        cols, rows = 6, 8
        cw, ch = (w-2*inset)/cols, (h-2*inset)/rows
        for r in range(rows):
            for c in range(cols):
                cx, cy = inset+(c+.5)*cw, inset+(r+.5)*ch
                rx, ry = cw*.22, ch*.22
                paths.append(f"M {cx} {cy-ry} L {cx+rx} {cy} L {cx} {cy+ry} L {cx-rx} {cy} Z")
        purpose = "Panel de papel picado simple para comprobar puentes y corte repetido."
    else:
        raise ValueError("Plantilla de proceso no reconocida")
    body = "".join(f'<path id="p{i:03d}" d="{d}"/>' for i, d in enumerate(paths))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.4f}mm" height="{h:.4f}mm" viewBox="0 0 {w:.4f} {h:.4f}">'
        f'<metadata>{{"template_id":"{template_id}","machine_control":false}}</metadata>'
        f'<g id="layer_process" data-operation="cut" fill="none" stroke="#000" stroke-width="0.1">{body}</g></svg>'
    )
    return {
        "template_id": template_id,
        "operation": operation,
        "width_mm": w,
        "height_mm": h,
        "svg": svg,
        "purpose": purpose,
        "requires_validated_material_preset": True,
        "contains_machine_parameters": False,
    }


# WHY: Publica capacidades y límites de esta fase para que UI/operador no confundan GRBL experimental con soporte universal de controladores.
def control_capabilities() -> dict[str, Any]:
    return {
        "version": "0.10.0-experimental",
        "direct_control": True,
        "controllers": ["GRBL 1.1"],
        "unsupported_controllers": ["Ruida", "Trocen", "TopWisdom", "Galvo proprietary"],
        "operations": ["line_engrave", "fill_engrave", "cut"],
        "source_geometry": "linear SVG paths only",
        "origin_mode": "current_position + mandatory laser-off frame",
        "realtime_controls": ["pause", "resume", "abort"],
        "jog": "incremental $J, laser off",
        "automatic_firmware_writes": False,
        "automatic_material_parameters": False,
        "validated_preset_required": True,
        "frame_required": True,
    }
