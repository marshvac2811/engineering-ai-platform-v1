"""Provider-neutral external integration models."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SUPPORTED_PROVIDERS = {"gmail", "upwork", "fiverr", "gumroad", "hubspot"}


@dataclass
class IntegrationConnection:
    tenant_id: str
    provider: str
    status: str = "configured"
    external_account_id: Optional[str] = None
    scopes: list[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    connection_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def validate(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported integration provider: {self.provider}")
        if self.status not in {"configured", "connected", "error", "disabled"}:
            raise ValueError(f"Unsupported connection status: {self.status}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NormalizedIntegrationEvent:
    tenant_id: str
    provider: str
    event_type: str
    external_event_id: str
    payload: Dict[str, Any]
    source_message: Optional[str] = None
    source_account_id: Optional[str] = None
    received_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return asdict(self)
