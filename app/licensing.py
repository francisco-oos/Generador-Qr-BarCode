"""Pluggable entitlement verification for standalone and future Server Oficina modes.

The standalone build verifies Ed25519-signed JSON using a distributed public key.
No private signing key is present in the application package.
"""

from __future__ import annotations

import base64
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .models import LicensePayload

ROOT = Path(__file__).resolve().parent.parent


class LicenseError(RuntimeError):
    pass


class LicenseProvider(ABC):
    @abstractmethod
    def status(self) -> dict:
        raise NotImplementedError


class StandaloneFileLicenseProvider(LicenseProvider):
    def __init__(self, license_path: Path | None = None, public_key_path: Path | None = None):
        self.license_path = license_path or ROOT / "license" / "license.local.json"
        self.public_key_path = public_key_path or ROOT / "license" / "public_key.pem"

    @staticmethod
    def _canonical(payload: dict) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def status(self) -> dict:
        if not self.license_path.exists() or not self.public_key_path.exists():
            return {"valid": False, "reason": "license_or_public_key_missing", "mode": "standalone"}
        raw = json.loads(self.license_path.read_text(encoding="utf-8"))
        payload_dict = raw.get("payload")
        signature_b64 = raw.get("signature")
        if not isinstance(payload_dict, dict) or not isinstance(signature_b64, str):
            return {"valid": False, "reason": "invalid_license_file", "mode": "standalone"}
        try:
            public_key = serialization.load_pem_public_key(self.public_key_path.read_bytes())
            if not isinstance(public_key, Ed25519PublicKey):
                raise LicenseError("public key is not Ed25519")
            public_key.verify(base64.b64decode(signature_b64), self._canonical(payload_dict))
            payload = LicensePayload.model_validate(payload_dict)
            expired = False
            if payload.expires_at:
                expires = datetime.fromisoformat(payload.expires_at.replace("Z", "+00:00"))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                expired = expires < datetime.now(timezone.utc)
            return {
                "valid": not expired,
                "reason": "expired" if expired else "ok",
                "mode": "standalone",
                "payload": payload.model_dump(),
            }
        except Exception as exc:  # verification errors must not leak key details
            return {"valid": False, "reason": f"verification_failed:{type(exc).__name__}", "mode": "standalone"}


class ServerOficinaLicenseProvider(LicenseProvider):
    """Future provider boundary.

    The current standalone release never reaches the network. When Server Oficina exposes
    an entitlement endpoint, this provider can exchange an installation identity/token and
    return the same status shape as the standalone provider without changing UI/core logic.
    """

    def status(self) -> dict:
        return {
            "valid": False,
            "reason": "server_provider_not_configured",
            "mode": "server_oficina",
            "ready_for_integration": True,
        }


def get_license_provider() -> LicenseProvider:
    mode = os.getenv("MARKING_STUDIO_LICENSE_MODE", "standalone").strip().lower()
    if mode == "server_oficina":
        return ServerOficinaLicenseProvider()
    return StandaloneFileLicenseProvider()
