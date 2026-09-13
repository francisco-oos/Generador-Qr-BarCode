"""Safe interoperability helpers for LightBurn/LaserGRBL and GRBL controllers.

This module intentionally does **not** stream jobs, move axes, set power, or fire the
laser.  It only discovers serial ports, performs read-only GRBL identification/
configuration queries (``$I`` and ``$$``), and parses configuration files exported
by the software already used in the workshop.

Keeping this bridge read-only lets Marking Studio learn the shop's existing machine
and material settings without becoming a second laser controller.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

try:  # pyserial is optional for offline rendering but packaged in production deps.
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover - exercised when dependency intentionally absent
    serial = None
    list_ports = None


# WHY: Fallback serial POSIX mínimo para diagnóstico read-only cuando pyserial no esté disponible.
class _NativePosixSerial:
    """Tiny POSIX fallback used only for the read-only diagnostic.

    Production installations should use pyserial (declared in requirements). This
    fallback keeps Linux/macOS diagnostics available in offline environments and
    is deliberately too small to become a general machine-control transport.
    """
    # WHY: Abre/configura el puerto POSIX con timeout explícito para no bloquear indefinidamente la estación.
    def __init__(self, port: str, baudrate: int, timeout: float, write_timeout: float):
        import os, termios
        self._os = os
        self._termios = termios
        self.timeout = timeout
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(self.fd)
        speed_name = f"B{baudrate}"
        speed = getattr(termios, speed_name, None)
        if speed is None:
            os.close(self.fd)
            raise ValueError(f"Baud {baudrate} no soportado por fallback POSIX")
        attrs[0] = 0  # iflag - raw
        attrs[1] = 0  # oflag
        attrs[2] = attrs[2] | termios.CLOCAL | termios.CREAD
        attrs[3] = 0  # lflag - raw
        attrs[4] = speed
        attrs[5] = speed
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = max(1, min(255, int(round(timeout * 10))))
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        os.set_blocking(self.fd, True)
        self._buffer = bytearray()
    # WHY: Permite usar el puerto como context manager y garantizar cierre incluso ante errores.
    def __enter__(self): return self
    # WHY: Cierra siempre el descriptor al salir del contexto para liberar la controladora a LightBurn/LaserGRBL.
    def __exit__(self, *args): self.close(); return False
    # WHY: Libera el descriptor nativo de forma idempotente.
    def close(self):
        if getattr(self, "fd", None) is not None:
            self._os.close(self.fd); self.fd = None
    # WHY: Envía bytes exclusivamente a través de la capa que filtra los comandos seguros.
    def write(self, payload: bytes): return self._os.write(self.fd, payload)
    # WHY: Mantiene compatibilidad con la interfaz serial usada por el probe sin añadir comportamiento de máquina.
    def flush(self): return None
    # WHY: Descarta respuesta vieja antes del diagnóstico para no atribuirla al comando actual.
    def reset_input_buffer(self):
        self._termios.tcflush(self.fd, self._termios.TCIFLUSH)
    # WHY: Lee una línea con timeout para recopilar respuestas GRBL sin dejar la UI bloqueada.
    def readline(self) -> bytes:
        import select, time
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            nl = self._buffer.find(b"\n")
            if nl >= 0:
                line = bytes(self._buffer[:nl+1]); del self._buffer[:nl+1]; return line
            wait = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([self.fd], [], [], wait)
            if not ready: break
            chunk = self._os.read(self.fd, 1024)
            if chunk: self._buffer.extend(chunk)
        if self._buffer:
            data = bytes(self._buffer); self._buffer.clear(); return data
        return b""


# WHY: Selecciona pyserial o fallback POSIX manteniendo una interfaz común y testeable.
def _serial_context(port: str, baud: int, timeout: float):
    if serial is not None:
        return serial.Serial(port=port, baudrate=baud, timeout=timeout, write_timeout=timeout)
    import os
    if os.name == "posix":
        return _NativePosixSerial(port=port, baudrate=baud, timeout=timeout, write_timeout=timeout)
    raise RuntimeError("pyserial no está disponible; instale requirements.txt")


SAFE_GRBL_COMMANDS = ("$I", "$$")


# WHY: Resultado normalizado de cualquier importador, con fuente, hash y presets detectados.
@dataclass(frozen=True)
class ImportedConfiguration:
    source_type: str
    summary: dict[str, Any]
    settings: dict[str, Any]
    material_presets: list[dict[str, Any]]
    warnings: list[str]


# WHY: Calcula huella de origen para auditar que un ajuste proviene exactamente del archivo importado.
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# WHY: Interpreta parámetros $n=v sin escribirlos, permitiendo documentar la controladora existente.
def parse_grbl_dump(text: str) -> dict[str, Any]:
    """Parse a GRBL ``$$`` / ``$I`` transcript without applying any changes."""
    settings: dict[str, str] = {}
    info: list[str] = []
    raw_lines: list[str] = []
    for raw in text.replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        raw_lines.append(line)
        match = re.match(r"^\$(\d+)=(.+)$", line)
        if match:
            settings[f"${match.group(1)}"] = match.group(2).strip()
        elif line.lower() not in {"ok", "$$", "$i"}:
            info.append(line)
    numeric: dict[str, float | int | str] = {}
    for key, value in settings.items():
        try:
            number = float(value)
            numeric[key] = int(number) if number.is_integer() else number
        except ValueError:
            numeric[key] = value
    return {
        "settings": numeric,
        "info": info,
        "raw_lines": raw_lines,
        "laser_mode": numeric.get("$32"),
        "s_value_max": numeric.get("$30"),
        "travel_x_mm": numeric.get("$130"),
        "travel_y_mm": numeric.get("$131"),
    }


# WHY: Descubre puertos candidatos; no abre ni opera ninguno hasta acción explícita del usuario.
def list_serial_devices() -> list[dict[str, Any]]:
    """Return serial-port metadata on Windows/Linux/macOS without opening ports."""
    if list_ports is None:
        # Conservative POSIX discovery fallback. Do not open devices here.
        import glob, os
        if os.name != "posix":
            return []
        candidates = sorted(set(
            glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*") +
            glob.glob("/dev/cu.*") + glob.glob("/dev/tty.usb*")
        ))
        return [{"device": d, "name": Path(d).name, "description": "Serial (POSIX fallback)",
                 "hwid": None, "vid": None, "pid": None, "manufacturer": None,
                 "product": None, "serial_number": None} for d in candidates]
    result = []
    for port in list_ports.comports():
        result.append({
            "device": port.device,
            "name": port.name,
            "description": port.description,
            "hwid": port.hwid,
            "vid": port.vid,
            "pid": port.pid,
            "manufacturer": port.manufacturer,
            "product": port.product,
            "serial_number": port.serial_number,
        })
    return result


# WHY: Consulta únicamente $I y $$, invariantes de seguridad que impiden movimiento o activación del láser.
def probe_grbl_readonly(port: str, baud: int = 115200, timeout: float = 1.2) -> dict[str, Any]:
    """Open one serial port and issue only the safe read-only GRBL queries.

    ``$I`` reads build information and ``$$`` reads controller settings.  No motion,
    spindle/laser, reset, homing, or setting-write commands are ever sent.
    """
    if not port or len(port) > 256:
        raise ValueError("Puerto serial inválido")
    if baud not in {9600, 19200, 38400, 57600, 115200, 230400, 250000}:
        raise ValueError("Baud no permitido para diagnóstico")

    transcript: list[str] = []
    with _serial_context(port, baud, timeout) as ser:
        # A newline is sufficient to wake common GRBL boards and is not an action.
        ser.write(b"\r\n")
        ser.flush()
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        for command in SAFE_GRBL_COMMANDS:
            ser.write((command + "\n").encode("ascii"))
            ser.flush()
            empty_reads = 0
            while empty_reads < 2:
                raw = ser.readline()
                if not raw:
                    empty_reads += 1
                    continue
                empty_reads = 0
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    transcript.append(line)
                if line.lower() == "ok":
                    break
    parsed = parse_grbl_dump("\n".join(transcript))
    parsed.update({"port": port, "baud": baud, "commands_sent": list(SAFE_GRBL_COMMANDS), "read_only": True})
    return parsed


# WHY: Compara parámetros reales contra perfil para advertir diferencias sin corregirlas automáticamente.
def compare_grbl_to_profile(parsed: dict[str, Any], machine: Any | None) -> list[str]:
    """Return non-destructive diagnostic notes comparing GRBL limits to a profile.

    The controller values are not rewritten. Differences can be legitimate because
    a configured usable bed may intentionally be smaller than firmware travel.
    """
    notes: list[str] = []
    if machine is None:
        return notes
    if str(getattr(machine, "controller", "")).upper() != "GRBL":
        notes.append("El perfil seleccionado no declara controlador GRBL; la comparación es solo informativa.")
        return notes
    pairs = (("travel_x_mm", "bed_width_mm", "X"), ("travel_y_mm", "bed_height_mm", "Y"))
    for actual_key, configured_key, axis in pairs:
        actual = parsed.get(actual_key)
        configured = getattr(machine, configured_key, None)
        if isinstance(actual, (int, float)) and isinstance(configured, (int, float)):
            delta = float(actual) - float(configured)
            if abs(delta) > 0.5:
                notes.append(
                    f"GRBL {axis} reporta {actual:g} mm y el perfil usa {configured:g} mm "
                    f"(diferencia {delta:+.1f} mm). No se modifica automáticamente."
                )
    if parsed.get("laser_mode") not in (None, 1):
        notes.append("GRBL $32 no está en 1 (Laser Mode); revisar en LightBurn/LaserGRBL antes de producción.")
    return notes


# WHY: Lee atributos heterogéneos de objetos LightBurn de forma tolerante a versiones.
def _value_attr(parent: ET.Element, name: str) -> str | None:
    node = parent.find(name)
    if node is None:
        return None
    return node.attrib.get("Value") or (node.text.strip() if node.text else None)


# WHY: Convierte valores textuales importados a tipos simples conservando lo desconocido como texto.
def _coerce(value: str | None) -> Any:
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return ""
    try:
        n = float(v)
        return int(n) if n.is_integer() else n
    except ValueError:
        return v


# WHY: Normaliza un ajuste de corte/grabado de LightBurn a campos auditables del dominio.
def _cut_setting_to_dict(node: ET.Element) -> dict[str, Any]:
    keys = [
        "index", "name", "minPower", "maxPower", "speed", "interval", "numPasses",
        "passCount", "overscanPercent", "bidir", "crossHatch", "angle", "runBlower",
        "frequency", "PPI", "dotTime", "dotSpacing", "scanOpt",
    ]
    data: dict[str, Any] = {"type": node.attrib.get("type")}
    for key in keys:
        value = _value_attr(node, key)
        if value is not None:
            data[key] = _coerce(value)
    return data


# WHY: Extrae presets de una Material Library de LightBurn sin modificarla.
def parse_lightburn_clb(data: bytes, source_name: str = "library.clb") -> ImportedConfiguration:
    """Read LightBurn's XML material library (.clb) into portable presets."""
    root = ET.fromstring(data)
    presets: list[dict[str, Any]] = []
    for material in root.findall(".//Material"):
        material_name = material.attrib.get("name", "")
        for entry in material.findall("./Entry"):
            thickness = entry.attrib.get("Thickness")
            desc = entry.attrib.get("Desc", "")
            cuts = [_cut_setting_to_dict(c) for c in entry.findall("./CutSetting")]
            for cut in cuts:
                presets.append({
                    "source": source_name,
                    "material": material_name,
                    "thickness_mm": _coerce(thickness),
                    "description": desc,
                    "operation": cut.get("type"),
                    "settings": cut,
                })
    return ImportedConfiguration(
        source_type="lightburn_clb",
        summary={"source_name": source_name, "material_presets": len(presets)},
        settings={}, material_presets=presets, warnings=[]
    )


# WHY: Inspecciona proyectos LightBurn para rescatar parámetros ya usados por el área.
def parse_lightburn_project(data: bytes, source_name: str = "project.lbrn2") -> ImportedConfiguration:
    """Extract cut-layer settings from a LightBurn .lbrn/.lbrn2 project."""
    root = ET.fromstring(data)
    cuts = [_cut_setting_to_dict(node) for node in root.findall(".//CutSetting")]
    presets = [{
        "source": source_name,
        "material": "Proyecto LightBurn",
        "thickness_mm": None,
        "description": str(c.get("name") or f"Capa {c.get('index', '?')}") ,
        "operation": c.get("type"),
        "settings": c,
    } for c in cuts]
    return ImportedConfiguration(
        source_type="lightburn_project",
        summary={"source_name": source_name, "cut_settings": len(cuts)},
        settings={}, material_presets=presets, warnings=[]
    )


# WHY: Recorre estructuras JSON anidadas para localizar ajustes en variantes de formato de LightBurn.
def _walk_json(obj: Any, out: dict[str, Any], prefix: str = "") -> None:
    """Flatten useful Desc/Value records from LightBurn .lbset variants."""
    if isinstance(obj, dict):
        if "Desc" in obj and "Value" in obj:
            key = str(obj.get("Desc") or obj.get("ID") or prefix or "setting")
            out[key] = obj.get("Value")
        for key, value in obj.items():
            _walk_json(value, out, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _walk_json(value, out, f"{prefix}[{i}]")


# WHY: Extrae preferencias/ajustes legibles de archivos de configuración LightBurn.
def parse_lightburn_lbset(data: bytes, source_name: str = "machine.lbset") -> ImportedConfiguration:
    """Read a LightBurn Machine Settings backup.

    GRBL .lbset files commonly contain JSON-like Desc/Value records.  If the file is
    a plain-text GRBL transcript, that format is accepted as well.
    """
    text = data.decode("utf-8-sig", errors="replace")
    warnings: list[str] = []
    settings: dict[str, Any] = {}
    try:
        obj = json.loads(text)
        _walk_json(obj, settings)
        if not settings and isinstance(obj, dict):
            settings = obj
    except json.JSONDecodeError:
        parsed = parse_grbl_dump(text)
        settings = parsed["settings"]
        if not settings:
            warnings.append("Formato .lbset no reconocido completamente; se conserva el hash/origen para revisión manual.")
    return ImportedConfiguration(
        source_type="lightburn_lbset",
        summary={"source_name": source_name, "settings_count": len(settings)},
        settings=settings, material_presets=[], warnings=warnings,
    )


# WHY: Inspecciona respaldos/ZIP de LightBurn y agrega artefactos reconocibles en modo sólo lectura.
def parse_lightburn_bundle(data: bytes, source_name: str = "bundle.lbzip") -> ImportedConfiguration:
    """Inspect a LightBurn User Bundle and extract readable material/device data."""
    warnings: list[str] = []
    settings: dict[str, Any] = {}
    presets: list[dict[str, Any]] = []
    entries: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            entries.append(name)
            lower = name.lower()
            payload = zf.read(name)
            try:
                if lower.endswith(".clb"):
                    parsed = parse_lightburn_clb(payload, name)
                    presets.extend(parsed.material_presets)
                elif lower.endswith(".lbset"):
                    parsed = parse_lightburn_lbset(payload, name)
                    settings.update({f"{name}:{k}": v for k, v in parsed.settings.items()})
                elif lower.endswith(".lbmt"):
                    parsed = parse_lightburn_lbmt(payload, name)
                    presets.extend(parsed.material_presets)
                elif lower.endswith(".lbprefs"):
                    parsed = parse_lightburn_prefs(payload, name)
                    settings.update({f"{name}:{k}": v for k, v in parsed.settings.items()})
                elif lower.endswith((".lbrn", ".lbrn2")):
                    parsed = parse_lightburn_project(payload, name)
                    presets.extend(parsed.material_presets)
                elif lower.endswith(".lbdev"):
                    # Device files are LightBurn-owned and their schema may change.
                    # Preserve text metadata when JSON/XML is obvious but do not edit it.
                    snippet = payload.decode("utf-8", errors="replace")[:2000]
                    settings[f"device_file:{name}"] = snippet
            except Exception as exc:  # one malformed entry must not discard the bundle
                warnings.append(f"No se pudo interpretar {name}: {exc}")
    return ImportedConfiguration(
        source_type="lightburn_bundle",
        summary={"source_name": source_name, "entries": len(entries), "material_presets": len(presets)},
        settings=settings, material_presets=presets, warnings=warnings,
    )



# WHY: Extrae presets de Material Test para conservar pruebas que el taller ya realizó.
def parse_lightburn_lbmt(data: bytes, source_name: str = "material_test_presets.lbmt") -> ImportedConfiguration:
    """Parse LightBurn Material Test preset files (.lbmt).

    Current LightBurn exports are JSON objects keyed by preset name.  Each preset
    contains the test-grid bounds plus MaterialCut/TextCut/BorderCut cut settings.
    We retain both the test range and the material cut settings so a workshop can
    recover the exact experiments it already ran instead of re-entering them.
    """
    text = data.decode("utf-8-sig", errors="replace")
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError(".lbmt root must be a JSON object")
    presets: list[dict[str, Any]] = []
    for name, body in obj.items():
        if not isinstance(body, dict):
            continue
        grid = {k: body.get(k) for k in (
            "XCenter", "XCount", "XMax", "XMin", "XParam", "XSize",
            "YCenter", "YCount", "YMax", "YMin", "YParam", "YSize"
        ) if k in body}
        material_cut = body.get("MaterialCut") if isinstance(body.get("MaterialCut"), dict) else {}
        text_cut = body.get("TextCut") if isinstance(body.get("TextCut"), dict) else {}
        border_cut = body.get("BorderCut") if isinstance(body.get("BorderCut"), dict) else {}
        presets.append({
            "source": source_name,
            "material": "LightBurn Material Test",
            "thickness_mm": None,
            "description": str(name),
            "operation": str(material_cut.get("type") or "material_test"),
            "settings": {
                "grid": grid,
                "material_cut": material_cut,
                "text_cut": text_cut,
                "border_cut": border_cut,
            },
        })
    return ImportedConfiguration(
        source_type="lightburn_material_test",
        summary={"source_name": source_name, "material_test_presets": len(presets)},
        settings={}, material_presets=presets, warnings=[]
    )


# WHY: Recupera campos útiles de preferencias LightBurn sin asumir que son parámetros productivos.
def parse_lightburn_prefs(data: bytes, source_name: str = "prefs.ini") -> ImportedConfiguration:
    """Read LightBurn user preferences conservatively.

    LightBurn preferences are JSON in current/legacy desktop releases, but the
    schema is internal and can change.  We therefore preserve a shallow portable
    snapshot and expose useful paths/device hints without rewriting any preference.
    """
    text = data.decode("utf-8-sig", errors="replace")
    warnings: list[str] = []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"prefs.ini is not JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("LightBurn prefs root must be an object")
    # Keep values that are simple enough for audit; avoid serializing huge blobs.
    simple: dict[str, Any] = {}
    for key, value in obj.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            simple[str(key)] = value
        elif key in {"Devices", "deviceList", "DeviceList"} and isinstance(value, (list, dict)):
            simple[str(key)] = value
    paths = {}
    for key in ("LastLibraryPath", "LastProjectPath", "LastExportPath"):
        if key in obj and isinstance(obj[key], str):
            paths[key] = obj[key]
    if not paths:
        warnings.append("No se detectaron rutas de librería/proyecto conocidas; el esquema de preferencias puede variar por versión.")
    return ImportedConfiguration(
        source_type="lightburn_prefs",
        summary={"source_name": source_name, "top_level_keys": len(obj), "known_paths": paths},
        settings=simple, material_presets=[], warnings=warnings
    )


# WHY: Enumera rutas conocidas por sistema operativo para descubrimiento local no destructivo.
def lightburn_pref_roots(home: Path | None = None, system: str | None = None, env: dict[str, str] | None = None) -> list[Path]:
    """Return documented/conventional LightBurn preference roots for one host.

    The result is only used for read-only discovery.  Callers may supply ``home``,
    ``system`` and ``env`` to exercise Windows/Linux/macOS behavior in tests.
    """
    home = Path(home or Path.home())
    system = (system or platform.system()).lower()
    env = dict(os.environ if env is None else env)
    roots: list[Path] = []
    if system.startswith("win"):
        local = env.get("LOCALAPPDATA")
        if local:
            roots.append(Path(local) / "LightBurn")
        else:
            roots.append(home / "AppData" / "Local" / "LightBurn")
    elif system == "darwin":
        roots.append(home / "Library" / "Preferences" / "LightBurn")
    else:
        roots.append(home / ".config" / "LightBurn")
    # Preserve order while deduplicating lexical aliases.
    out: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        k = str(r.expanduser())
        if k not in seen:
            seen.add(k); out.append(r.expanduser())
    return out


# WHY: Busca artefactos candidatos y devuelve metadatos; no los importa automáticamente para mantener consentimiento explícito.
def discover_lightburn_artifacts(roots: list[Path] | None = None, max_files: int = 250) -> dict[str, Any]:
    """Discover existing LightBurn settings without modifying or opening the laser.

    Standard preference roots are scanned to a small bounded depth. ``prefs.ini`` is
    inspected for ``LastLibraryPath`` so a user-created .clb outside the preferences
    directory can also be offered.  Only metadata/path/hash is returned here.
    """
    roots = [Path(r).expanduser() for r in (roots or lightburn_pref_roots())]
    supported = {".clb", ".lbset", ".lbrn", ".lbrn2", ".lbzip", ".lbmt", ".lbprefs"}
    found: dict[str, dict[str, Any]] = {}
    extra_paths: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        # Explicitly include prefs.ini even though it has .ini extension.
        prefs = root / "prefs.ini"
        candidates: list[Path] = []
        if prefs.is_file():
            candidates.append(prefs)
            try:
                parsed = parse_lightburn_prefs(prefs.read_bytes(), str(prefs))
                path = (parsed.summary.get("known_paths") or {}).get("LastLibraryPath")
                if path:
                    lp = Path(str(path)).expanduser()
                    if lp.is_file():
                        extra_paths.append(lp)
            except Exception:
                pass
        # Preference trees can contain backup machine settings and material tests.
        for path in root.rglob("*"):
            if len(candidates) >= max_files:
                break
            try:
                rel_parts = path.relative_to(root).parts
            except ValueError:
                continue
            if len(rel_parts) > 5 or not path.is_file():
                continue
            if path.suffix.lower() in supported:
                candidates.append(path)
        for path in candidates:
            if len(found) >= max_files:
                break
            try:
                raw = path.read_bytes()
                stat = path.stat()
            except OSError:
                continue
            key = str(path.resolve())
            found[key] = {
                "path": key, "name": path.name, "suffix": path.suffix.lower(),
                "size": len(raw), "mtime": stat.st_mtime, "sha256": sha256_bytes(raw),
                "root": str(root),
            }
    for path in extra_paths:
        try:
            raw = path.read_bytes(); stat = path.stat(); key = str(path.resolve())
        except OSError:
            continue
        found.setdefault(key, {"path": key, "name": path.name, "suffix": path.suffix.lower(), "size": len(raw), "mtime": stat.st_mtime, "sha256": sha256_bytes(raw), "root": "LastLibraryPath"})
    return {"roots": [str(r) for r in roots], "artifacts": sorted(found.values(), key=lambda x: (x["name"].lower(), x["path"])), "read_only": True}


# WHY: Importa sólo un artefacto elegido previamente por el operador y conserva su hash/origen.
def import_discovered_lightburn_artifact(path: str, allowed: list[dict[str, Any]] | None = None) -> ImportedConfiguration:
    """Import exactly one artifact previously returned by discovery.

    Restricting to a previously discovered absolute path prevents arbitrary local
    file reads through the localhost API.
    """
    discovered = allowed if allowed is not None else discover_lightburn_artifacts()["artifacts"]
    allowed_paths = {str(Path(x["path"]).resolve()) for x in discovered}
    resolved = str(Path(path).expanduser().resolve())
    if resolved not in allowed_paths:
        raise ValueError("El archivo no pertenece al conjunto detectado de LightBurn")
    p = Path(resolved)
    raw = p.read_bytes()
    if p.name.lower() == "prefs.ini":
        return parse_lightburn_prefs(raw, p.name)
    return import_configuration_bytes(p.name, raw)

# WHY: Despacha bytes al parser correcto por extensión/contenido y unifica su resultado.
def import_configuration_bytes(filename: str, data: bytes) -> ImportedConfiguration:
    """Dispatch a supported workshop-export file to the safest parser."""
    path = Path(filename)
    suffix = path.suffix.lower()
    if path.name.lower() == "prefs.ini":
        return parse_lightburn_prefs(data, filename)
    if suffix == ".clb":
        return parse_lightburn_clb(data, filename)
    if suffix in {".lbrn", ".lbrn2"}:
        return parse_lightburn_project(data, filename)
    if suffix == ".lbset":
        return parse_lightburn_lbset(data, filename)
    if suffix == ".lbmt":
        return parse_lightburn_lbmt(data, filename)
    if suffix == ".lbprefs":
        return parse_lightburn_prefs(data, filename)
    if suffix in {".lbzip", ".zip"}:
        return parse_lightburn_bundle(data, filename)
    if suffix == ".psh":
        return parse_lasergrbl_psh(data, filename)
    if suffix in {".txt", ".log"}:
        parsed = parse_grbl_dump(data.decode("utf-8-sig", errors="replace"))
        return ImportedConfiguration(
            source_type="grbl_text",
            summary={"source_name": filename, "settings_count": len(parsed["settings"])},
            settings=parsed["settings"], material_presets=[], warnings=[]
        )
    raise ValueError("Formato no soportado. Use .clb, .lbset, .lbmt, .lbprefs, .lbrn/.lbrn2, .lbzip/.zip, LaserGRBL .psh o texto de $$.")

# ---------------------------------------------------------------------------
# LaserGRBL material database interoperability
# ---------------------------------------------------------------------------

# WHY: Extrae nombre local de etiquetas XML para tolerar namespaces en LaserGRBL.
def _local_tag(tag: str) -> str:
    return tag.split('}', 1)[-1] if '}' in tag else tag


# WHY: Extrae biblioteca de materiales LaserGRBL como referencia reproducible.
def parse_lasergrbl_psh(data: bytes, source_name: str = "UserMaterials.psh") -> ImportedConfiguration:
    """Parse LaserGRBL's XML material database (.psh) read-only.

    LaserGRBL stores its user material database in an XML ``UserMaterials.psh``.
    Schema revisions may add columns, therefore this parser deliberately collects
    all child fields while mapping common Material/Power/Speed/Cycles fields into
    Marking Studio's portable material-preset shape.
    """
    root = ET.fromstring(data)
    records: list[dict[str, Any]] = []
    for node in root.iter():
        if _local_tag(node.tag).lower() != "materials":
            continue
        row: dict[str, Any] = {}
        for child in list(node):
            key = _local_tag(child.tag)
            value = (child.text or "").strip()
            row[key] = _coerce(value)
        if not row:
            continue
        material = str(row.get("Material") or row.get("material") or "LaserGRBL material")
        model = str(row.get("Model") or row.get("model") or "")
        action = str(row.get("Action") or row.get("action") or "")
        remarks = str(row.get("Remarks") or row.get("remarks") or "")
        description = " · ".join(x for x in (model, action, remarks) if x)
        settings = dict(row)
        # Portable aliases make imported settings easier to compare with LightBurn.
        if row.get("Speed") is not None:
            settings["speed_mm_min"] = row.get("Speed")
        if row.get("Power") is not None:
            settings["power_percent"] = row.get("Power")
        if row.get("Cycles") is not None:
            settings["passes"] = row.get("Cycles")
        records.append({
            "source": source_name,
            "material": material,
            "thickness_mm": row.get("Thickness"),
            "description": description,
            "operation": action or "LaserGRBL",
            "settings": settings,
        })
    return ImportedConfiguration(
        source_type="lasergrbl_material_db",
        summary={"source_name": source_name, "material_presets": len(records)},
        settings={}, material_presets=records, warnings=[] if records else ["El XML no contenía registros <Materials> reconocibles."],
    )


# WHY: Calcula rutas conocidas de LaserGRBL, principalmente en Windows, sin asumir que la app está instalada.
def lasergrbl_roots(home: Path | None = None, system: str | None = None, env: dict[str, str] | None = None) -> list[Path]:
    """Return the conventional LaserGRBL per-user data root.

    LaserGRBL is Windows software.  Test hooks accept a synthetic platform so the
    path logic can still be regression-tested on Linux CI.
    """
    home = Path(home or Path.home())
    system = (system or platform.system()).lower()
    env = dict(os.environ if env is None else env)
    if not system.startswith("win"):
        return []
    appdata = env.get("APPDATA")
    return [Path(appdata) / "LaserGRBL"] if appdata else [home / "AppData" / "Roaming" / "LaserGRBL"]


# WHY: Busca bases de materiales y devuelve candidatos para selección humana.
def discover_lasergrbl_artifacts(roots: list[Path] | None = None) -> dict[str, Any]:
    roots = [Path(x).expanduser() for x in (roots if roots is not None else lasergrbl_roots())]
    artifacts: list[dict[str, Any]] = []
    for root in roots:
        for name in ("UserMaterials.psh", "UserMaterial.psh", "StandardMaterials.psh"):
            path = root / name
            if not path.is_file():
                continue
            try:
                raw = path.read_bytes(); stat = path.stat()
            except OSError:
                continue
            artifacts.append({
                "path": str(path.resolve()), "name": path.name, "suffix": ".psh",
                "size": len(raw), "mtime": stat.st_mtime, "sha256": sha256_bytes(raw), "root": str(root),
            })
    return {"roots": [str(x) for x in roots], "artifacts": artifacts, "read_only": True}


# WHY: Importa la base LaserGRBL seleccionada manteniendo el mismo contrato de procedencia/hashes.
def import_discovered_lasergrbl_artifact(path: str, allowed: list[dict[str, Any]] | None = None) -> ImportedConfiguration:
    discovered = allowed if allowed is not None else discover_lasergrbl_artifacts()["artifacts"]
    allowed_paths = {str(Path(x["path"]).resolve()) for x in discovered}
    resolved = str(Path(path).expanduser().resolve())
    if resolved not in allowed_paths:
        raise ValueError("El archivo no pertenece al conjunto detectado de LaserGRBL")
    p = Path(resolved)
    return parse_lasergrbl_psh(p.read_bytes(), p.name)
