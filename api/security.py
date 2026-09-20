"""API-key issuance, hashing and lightweight usage metering."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import secrets
from typing import Dict, List, Optional, Set


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


@dataclass
class ApiKeyRecord:
    api_key_id: str
    tenant_id: str
    created_by: str
    role: str
    name: str
    key_prefix: str
    key_hash: str
    scopes: Set[str] = field(default_factory=set)
    created_at: str = field(default_factory=_now)
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None

    def to_public_dict(self) -> dict:
        return {
            "api_key_id": self.api_key_id,
            "tenant_id": self.tenant_id,
            "created_by": self.created_by,
            "role": self.role,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": sorted(self.scopes),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
        }


class InMemoryApiKeyStore:
    def __init__(self) -> None:
        self.records: Dict[str, ApiKeyRecord] = {}

    def issue(self, *, tenant_id: str, created_by: str, role: str, name: str, scopes: List[str], expires_at: Optional[str] = None) -> tuple[dict, str]:
        if not name.strip():
            raise ValueError("API key name is required")
        key_id = secrets.token_hex(12)
        secret = "eap_live_" + secrets.token_urlsafe(32)
        prefix = secret[:16]
        record = ApiKeyRecord(
            api_key_id=key_id,
            tenant_id=tenant_id,
            created_by=created_by,
            role=role,
            name=name.strip(),
            key_prefix=prefix,
            key_hash=hash_api_key(secret),
            scopes=set(scopes),
            expires_at=expires_at,
        )
        self.records[key_id] = record
        return record.to_public_dict(), secret

    def lookup(self, secret: str) -> Optional[dict]:
        digest = hash_api_key(secret)
        now = datetime.now(timezone.utc)
        for record in self.records.values():
            if record.key_hash != digest or record.revoked_at:
                continue
            if record.expires_at:
                try:
                    if datetime.fromisoformat(record.expires_at.replace("Z", "+00:00")) <= now:
                        continue
                except ValueError:
                    continue
            return {
                "tenant_id": record.tenant_id,
                "created_by": record.created_by,
                "role": record.role,
                "api_key_id": record.api_key_id,
                "scopes": sorted(record.scopes),
            }
        return None

    def revoke(self, tenant_id: str, api_key_id: str) -> dict:
        record = self.records.get(api_key_id)
        if not record or record.tenant_id != tenant_id:
            raise KeyError("Unknown API key")
        record.revoked_at = _now()
        return record.to_public_dict()

    def list(self, tenant_id: str) -> List[dict]:
        return [r.to_public_dict() for r in self.records.values() if r.tenant_id == tenant_id]


@dataclass
class UsageEvent:
    tenant_id: str
    user_id: str
    event_type: str
    units: float = 1.0
    job_id: Optional[str] = None
    skill_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "units": self.units,
            "job_id": self.job_id,
            "skill_id": self.skill_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class InMemoryUsageStore:
    def __init__(self) -> None:
        self.events: List[UsageEvent] = []

    def record(self, event: UsageEvent) -> UsageEvent:
        self.events.append(event)
        return event

    def summarize(self, tenant_id: str) -> dict:
        events = [e for e in self.events if e.tenant_id == tenant_id]
        by_type: Dict[str, float] = {}
        by_skill: Dict[str, float] = {}
        for event in events:
            by_type[event.event_type] = by_type.get(event.event_type, 0.0) + event.units
            if event.skill_id:
                by_skill[event.skill_id] = by_skill.get(event.skill_id, 0.0) + event.units
        return {
            "tenant_id": tenant_id,
            "total_units": sum(e.units for e in events),
            "event_count": len(events),
            "by_event_type": by_type,
            "by_skill": by_skill,
        }
