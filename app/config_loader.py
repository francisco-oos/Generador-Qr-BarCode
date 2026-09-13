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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_templates() -> dict[str, TemplateSpec]:
    items: dict[str, TemplateSpec] = {}
    for p in sorted((CONFIG / "templates").glob("*.json")):
        item = TemplateSpec.model_validate(_read_json(p))
        items[item.id] = item
    return items


@lru_cache(maxsize=1)
def load_machines() -> dict[str, MachineProfile]:
    items: dict[str, MachineProfile] = {}
    for p in sorted((CONFIG / "machines").glob("*.json")):
        item = MachineProfile.model_validate(_read_json(p))
        items[item.id] = item
    return items


@lru_cache(maxsize=1)
def load_scanners() -> dict[str, ScannerProfile]:
    items: dict[str, ScannerProfile] = {}
    for p in sorted((CONFIG / "scanners").glob("*.json")):
        item = ScannerProfile.model_validate(_read_json(p))
        items[item.id] = item
    return items


@lru_cache(maxsize=1)
def load_jigs() -> dict[str, JigProfile]:
    items: dict[str, JigProfile] = {}
    for p in sorted((CONFIG / "jigs").glob("*.json")):
        item = JigProfile.model_validate(_read_json(p))
        items[item.id] = item
    return items


@lru_cache(maxsize=1)
def load_quality_profiles() -> dict[str, QualityProfile]:
    items: dict[str, QualityProfile] = {}
    for p in sorted((CONFIG / "quality").glob("*.json")):
        item = QualityProfile.model_validate(_read_json(p))
        items[item.id] = item
    return items


def save_template(template: TemplateSpec) -> Path:
    path = CONFIG / "templates" / f"{template.id}.json"
    path.write_text(json.dumps(template.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    load_templates.cache_clear()
    return path


def save_jig(jig: JigProfile) -> Path:
    path = CONFIG / "jigs" / f"{jig.id}.json"
    path.write_text(json.dumps(jig.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    load_jigs.cache_clear()
    return path
