"""Local SQLite journal for engraving jobs, marks and scan-verification events.

This database is an offline operational history, not the future system-of-record;
Server Oficina integration should synchronize events rather than share this file.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "marking_studio.sqlite3"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db() -> None:
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS engraving_jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                template_id TEXT NOT NULL,
                jig_id TEXT,
                machine_id TEXT,
                record_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS engraving_marks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES engraving_jobs(id) ON DELETE CASCADE,
                slot_index INTEGER,
                asset_key TEXT NOT NULL,
                physical_id TEXT,
                status TEXT NOT NULL,
                template_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                verified_at TEXT,
                verified_scan TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_marks_asset_key ON engraving_marks(asset_key);
            CREATE INDEX IF NOT EXISTS idx_marks_job_id ON engraving_marks(job_id);
            CREATE TABLE IF NOT EXISTS machine_captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                machine_profile_id TEXT,
                sha256 TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                settings_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_machine_captures_sha256 ON machine_captures(sha256);
            CREATE TABLE IF NOT EXISTS material_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capture_id INTEGER NOT NULL REFERENCES machine_captures(id) ON DELETE CASCADE,
                source_name TEXT NOT NULL,
                material TEXT NOT NULL,
                thickness_mm TEXT,
                description TEXT,
                operation TEXT,
                settings_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_material_presets_capture ON material_presets(capture_id);
            """
        )


def record_job(template_id: str, jig_id: str | None, machine_id: str | None,
               manifest: list[dict], rows: list[dict[str, str]], metadata: dict) -> str:
    job_id = str(uuid.uuid4())
    with connect() as con:
        con.execute(
            "INSERT INTO engraving_jobs(id,created_at,template_id,jig_id,machine_id,record_count,status,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
            (job_id, _utcnow(), template_id, jig_id, machine_id, len(manifest), "exported", json.dumps(metadata, ensure_ascii=False)),
        )
        for m in manifest:
            row = rows[int(m["row_index"])]
            con.execute(
                "INSERT INTO engraving_marks(job_id,slot_index,asset_key,physical_id,status,template_id,payload_json) VALUES(?,?,?,?,?,?,?)",
                (
                    job_id,
                    int(m["slot_index"]),
                    str(m.get("id") or ""),
                    str(m.get("physical_id") or ""),
                    "exported",
                    template_id,
                    json.dumps(row, ensure_ascii=False),
                ),
            )
    return job_id


def verify_mark(asset_key: str, scanned: str) -> dict:
    with connect() as con:
        row = con.execute(
            "SELECT * FROM engraving_marks WHERE asset_key=? ORDER BY id DESC LIMIT 1", (asset_key,)
        ).fetchone()
        if not row:
            return {"updated": False, "reason": "asset_not_found"}
        con.execute(
            "UPDATE engraving_marks SET status='verified',verified_at=?,verified_scan=? WHERE id=?",
            (_utcnow(), scanned, row["id"]),
        )
        return {"updated": True, "mark_id": row["id"], "job_id": row["job_id"]}


def history(limit: int = 100) -> list[dict]:
    with connect() as con:
        rows = con.execute(
            """
            SELECT m.id,m.job_id,m.slot_index,m.asset_key,m.physical_id,m.status,m.template_id,
                   m.verified_at,m.verified_scan,j.created_at,j.jig_id,j.machine_id
            FROM engraving_marks m JOIN engraving_jobs j ON j.id=m.job_id
            ORDER BY m.id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def record_machine_capture(source_type: str, source_name: str, sha256: str, summary: dict, settings: dict,
                           material_presets: list[dict], warnings: list[str], machine_profile_id: str | None = None) -> dict:
    """Persist a read-only snapshot imported from LightBurn/GRBL.

    Duplicate file hashes are allowed because the same export may intentionally be
    associated with another machine profile, but the returned record makes hashes
    visible for audit and comparison.
    """
    with connect() as con:
        cur = con.execute(
            "INSERT INTO machine_captures(created_at,source_type,source_name,machine_profile_id,sha256,summary_json,settings_json,warnings_json) VALUES(?,?,?,?,?,?,?,?)",
            (_utcnow(), source_type, source_name, machine_profile_id, sha256,
             json.dumps(summary, ensure_ascii=False), json.dumps(settings, ensure_ascii=False),
             json.dumps(warnings, ensure_ascii=False)),
        )
        capture_id = int(cur.lastrowid)
        preset_ids = []
        for preset in material_presets:
            pcur = con.execute(
                "INSERT INTO material_presets(capture_id,source_name,material,thickness_mm,description,operation,settings_json) VALUES(?,?,?,?,?,?,?)",
                (capture_id, str(preset.get("source") or source_name), str(preset.get("material") or ""),
                 None if preset.get("thickness_mm") is None else str(preset.get("thickness_mm")),
                 str(preset.get("description") or ""), str(preset.get("operation") or ""),
                 json.dumps(preset.get("settings") or {}, ensure_ascii=False)),
            )
            preset_ids.append(int(pcur.lastrowid))
    return {"capture_id": capture_id, "material_preset_ids": preset_ids}


def machine_captures(limit: int = 100) -> list[dict]:
    with connect() as con:
        rows = con.execute(
            "SELECT id,created_at,source_type,source_name,machine_profile_id,sha256,summary_json,warnings_json FROM machine_captures ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result=[]
        for r in rows:
            item=dict(r)
            item["summary"]=json.loads(item.pop("summary_json"))
            item["warnings"]=json.loads(item.pop("warnings_json"))
            result.append(item)
        return result


def material_presets(limit: int = 1000) -> list[dict]:
    with connect() as con:
        rows = con.execute(
            "SELECT id,capture_id,source_name,material,thickness_mm,description,operation,settings_json FROM material_presets ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result=[]
        for r in rows:
            item=dict(r)
            item["settings"]=json.loads(item.pop("settings_json"))
            result.append(item)
        return result


def material_preset_by_id(preset_id: int) -> dict | None:
    with connect() as con:
        r=con.execute(
            "SELECT id,capture_id,source_name,material,thickness_mm,description,operation,settings_json FROM material_presets WHERE id=?",
            (preset_id,),
        ).fetchone()
        if not r:
            return None
        item=dict(r)
        item["settings"]=json.loads(item.pop("settings_json"))
        return item


def record_shop_material_preset(*, name: str, machine_profile_id: str, material: str,
                                surface_or_model: str, operation: str, speed_mm_min: float,
                                power_percent: float, passes: int, interval_mm: float | None,
                                focus_reference_mm: float | None, laser_mode: str,
                                validated_on_exact_machine_surface: bool, notes: str) -> dict:
    """Persist an operator-entered shop baseline through the same audited capture model.

    Reusing ``machine_captures`` + ``material_presets`` means batch jobs can select
    these trusted local settings exactly like an imported LightBurn/LaserGRBL preset.
    """
    payload = {
        "name": name,
        "surface_or_model": surface_or_model,
        "speed_mm_min": speed_mm_min,
        "power_percent": power_percent,
        "passes": passes,
        "interval_mm": interval_mm,
        "focus_reference_mm": focus_reference_mm,
        "laser_mode": laser_mode,
        "validated_on_exact_machine_surface": validated_on_exact_machine_surface,
        "notes": notes,
    }
    digest = __import__('hashlib').sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    status = "VALIDADO EN ÁREA" if validated_on_exact_machine_surface else "BORRADOR / POR VALIDAR"
    preset = {
        "source": "Marking Studio / captura del área",
        "material": material,
        "thickness_mm": None,
        "description": f"{name} · {surface_or_model} · {status}".strip(" ·"),
        "operation": operation,
        "settings": payload,
    }
    return record_machine_capture(
        source_type="shop_manual_validated" if validated_on_exact_machine_surface else "shop_manual_draft",
        source_name=name,
        sha256=digest,
        summary={"status": status, "material": material, "surface_or_model": surface_or_model},
        settings={"authoritative_local_baseline": validated_on_exact_machine_surface},
        material_presets=[preset],
        warnings=[] if validated_on_exact_machine_surface else ["Preset guardado como borrador; no debe tratarse como ajuste aprobado de producción."],
        machine_profile_id=machine_profile_id,
    )
