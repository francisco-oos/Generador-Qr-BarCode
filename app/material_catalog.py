"""Curated material/phone reference catalog for a blue-diode marking workflow.

The catalog deliberately separates *researched starting ranges* from production
presets captured from the workshop.  A value from the web must never silently
replace a setting already validated on the exact SCULPFUN/material combination.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "config" / "materials" / "material_reference_v1.json"


def load_material_reference() -> dict[str, Any]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data.get("materials"), list) or not isinstance(data.get("phone_models"), list):
        raise ValueError("Material reference catalog is malformed")
    material_ids = [str(x.get("id")) for x in data["materials"]]
    phone_ids = [str(x.get("id")) for x in data["phone_models"]]
    if len(material_ids) != len(set(material_ids)) or len(phone_ids) != len(set(phone_ids)):
        raise ValueError("Duplicate material/phone IDs in reference catalog")
    return data


def search_material_reference(query: str = "", category: str | None = None) -> dict[str, Any]:
    data = load_material_reference()
    q = query.strip().lower()
    materials = data["materials"]
    phones = data["phone_models"]
    if category:
        materials = [m for m in materials if str(m.get("category", "")).lower() == category.lower()]
    if q:
        def match(obj: dict[str, Any]) -> bool:
            hay = json.dumps(obj, ensure_ascii=False).lower()
            return q in hay
        materials = [m for m in materials if match(m)]
        phones = [p for p in phones if match(p)]
    return {
        "version": data["version"],
        "generated_for": data.get("generated_for"),
        "policy": data.get("policy", {}),
        "materials": materials,
        "phone_models": phones,
    }


def phone_reference(brand: str, model: str = "") -> list[dict[str, Any]]:
    data = load_material_reference()
    b = brand.strip().lower()
    m = model.strip().lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in data["phone_models"]:
        ib = str(item.get("brand", "")).lower()
        im = str(item.get("model", "")).lower()
        aliases = [str(x).lower() for x in (item.get("aliases") or [])]
        score = 0
        if b and (b in ib or ib in b):
            score += 4
        if m and (m == im or m in im or im in m):
            score += 6
        if m and any(m == a or m in a or a in m for a in aliases):
            score += 5
        if score:
            scored.append((score, item))
    return [item for _, item in sorted(scored, key=lambda x: x[0], reverse=True)]
