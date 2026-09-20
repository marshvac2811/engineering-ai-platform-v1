"""Integration registry and normalized-event router."""
from __future__ import annotations

from typing import Any, Dict, Optional
from .models import IntegrationConnection, NormalizedIntegrationEvent


class InMemoryIntegrationStore:
    def __init__(self) -> None:
        self.connections: Dict[str, IntegrationConnection] = {}
        self.events: Dict[tuple[str, str, str], NormalizedIntegrationEvent] = {}

    def save_connection(self, connection: IntegrationConnection) -> IntegrationConnection:
        connection.validate()
        self.connections[connection.connection_id] = connection
        return connection

    def list_connections(self, tenant_id: str):
        return [c for c in self.connections.values() if c.tenant_id == tenant_id]

    def get_connection(self, tenant_id: str, provider: str) -> Optional[IntegrationConnection]:
        matches = [c for c in self.connections.values() if c.tenant_id == tenant_id and c.provider == provider]
        return matches[-1] if matches else None

    def record_event(self, event: NormalizedIntegrationEvent) -> tuple[NormalizedIntegrationEvent, bool]:
        key = (event.tenant_id, event.provider, event.external_event_id)
        existing = self.events.get(key)
        if existing:
            return existing, False
        self.events[key] = event
        return event, True


class IntegrationService:
    def __init__(self, store=None, *, tenant_id: Optional[str] = None):
        self.store = store or InMemoryIntegrationStore()
        self.tenant_id = tenant_id

    def _require_tenant(self, tenant_id: Optional[str] = None) -> str:
        value = tenant_id or self.tenant_id
        if not value:
            raise ValueError("tenant_id is required")
        return value

    def configure(self, *, provider: str, status: str = "configured", external_account_id: Optional[str] = None, scopes=None, metadata=None) -> IntegrationConnection:
        tenant_id = self._require_tenant()
        existing = self.store.get_connection(tenant_id, provider)
        if existing:
            existing.status = status
            existing.external_account_id = external_account_id or existing.external_account_id
            existing.scopes = list(scopes or existing.scopes)
            existing.metadata = dict(metadata or existing.metadata)
            return self.store.save_connection(existing)
        return self.store.save_connection(IntegrationConnection(
            tenant_id=tenant_id,
            provider=provider,
            status=status,
            external_account_id=external_account_id,
            scopes=list(scopes or []),
            metadata=dict(metadata or {}),
        ))

    def list(self):
        return self.store.list_connections(self._require_tenant())

    def ingest(self, *, provider: str, event_type: str, external_event_id: str, payload: Dict[str, Any], source_message: Optional[str] = None) -> tuple[NormalizedIntegrationEvent, bool]:
        tenant_id = self._require_tenant()
        event = NormalizedIntegrationEvent(
            tenant_id=tenant_id,
            provider=provider,
            event_type=event_type,
            external_event_id=external_event_id,
            payload=payload,
            source_message=source_message,
        )
        return self.store.record_event(event)
