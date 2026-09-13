"""Load and persist versionable JSON profiles used by the marking engine.

The loaders are cached for normal operation; save operations invalidate only the
relevant cache so configuration edits become available without changing core code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import JigProfile, MachineProfile, QualityProfile, ScannerProfile, TemplateSpec

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


# WHY: Lee JSON UTF-8 de forma centralizada para mantener una ruta de carga consistente y testeable.
def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# WHY: Descubre plantillas desde disco para que nuevas configuraciones aparezcan sin modificar Python.
@lru_cache(maxsize=1)
def load_templates() -> dict[str, TemplateSpec]:
    items: dict[str, TemplateSpec] = {}
    for p in sorted((CONFIG / "templates").glob("*.json")):
        item = TemplateSpec.model_validate(_read_json(p))
        items[item.id] = item
    return items


# WHY: Carga perfiles de máquina declarativos y separados del código de producción.
@lru_cache(maxsize=1)
def load_machines() -> dict[str, MachineProfile]:
    items: dict[str, MachineProfile] = {}
    for p in sorted((CONFIG / "machines").glob("*.json")):
        item = MachineProfile.model_validate(_read_json(p))
        items[item.id] = item
    return items


# WHY: Carga capacidades de lectores para comprobaciones y documentación operativa.
@lru_cache(maxsize=1)
def load_scanners() -> dict[str, ScannerProfile]:
    items: dict[str, ScannerProfile] = {}
    for p in sorted((CONFIG / "scanners").glob("*.json")):
        item = ScannerProfile.model_validate(_read_json(p))
        items[item.id] = item
    return items


# WHY: Carga bases físicas configurables y sus slots/calibración.
@lru_cache(maxsize=1)
def load_jigs() -> dict[str, JigProfile]:
    items: dict[str, JigProfile] = {}
    for p in sorted((CONFIG / "jigs").glob("*.json")):
        item = JigProfile.model_validate(_read_json(p))
        items[item.id] = item
    return items


# WHY: Carga criterios de legibilidad reutilizables por plantillas.
@lru_cache(maxsize=1)
def load_quality_profiles() -> dict[str, QualityProfile]:
    items: dict[str, QualityProfile] = {}
    for p in sorted((CONFIG / "quality").glob("*.json")):
        item = QualityProfile.model_validate(_read_json(p))
        items[item.id] = item
    return items


# WHY: Persiste una plantilla validada de forma atómica y legible para revisión humana.
def _bump_template_minor(version: str) -> str:
    """Bump the human-facing template version when physical output semantics change."""
    parts = str(version or "1.0").split(".")
    try:
        major = int(parts[0]) if parts else 1
        minor = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return "1.1"
    return f"{major}.{minor + 1}"


# WHY: Persistir una estrategia física distinta bajo la misma versión volvería ambiguo el histórico de lotes.
def save_template(template: TemplateSpec) -> Path:
    path = CONFIG / "templates" / f"{template.id}.json"
    # WHY (v0.8.0): changing polarity/scope/field/kerf changes the physical piece.
    # If the caller did not already advance the template version, do it here so an
    # old and a new lot cannot share the same version while engraving differently.
    if path.exists():
        try:
            previous = TemplateSpec.model_validate(_read_json(path))
            if previous.marking_mode.physical_fingerprint() != template.marking_mode.physical_fingerprint():
                if template.version == previous.version:
                    template.version = _bump_template_minor(previous.version)
        except Exception:
            # Validation errors are handled by the normal save path; an unreadable
            # previous file must not make the new valid template impossible to save.
            pass
    path.write_text(json.dumps(template.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    load_templates.cache_clear()
    return path


# WHY: Persiste un jig validado fuera del código para permitir calibración/reemplazo en campo.
def save_jig(jig: JigProfile) -> Path:
    path = CONFIG / "jigs" / f"{jig.id}.json"
    path.write_text(json.dumps(jig.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    load_jigs.cache_clear()
    return path
