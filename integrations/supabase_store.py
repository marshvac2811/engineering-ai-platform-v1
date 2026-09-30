"""Supabase-backed integration connection and event store."""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional

from .models import IntegrationConnection, NormalizedIntegrationEvent
from .service import InMemoryIntegrationStore


class SupabaseIntegrationStore(InMemoryIntegrationStore):
    def __init__(
        self,
        client: Any,
        *,
        connections_table: str = "integration_connections",
        events_table: str = "integration_events",
    ) -> None:
        super().__init__()
        self.client = client
        self.connections_table = connections_table
        self.events_table = events_table

    def save_connection(self, connection: IntegrationConnection) -> IntegrationConnection:
        connection.validate()
        row = connection.to_dict()
        self.client.table(self.connections_table).upsert(
            row,
            on_conflict="tenant_id,provider",
        ).execute()
        return connection

    def list_connections(self, tenant_id: str) -> Iterable[IntegrationConnection]:
        response = (
            self.client.table(self.connections_table)
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=False)
            .execute()
        )
        return tuple(
            self._connection_from_row(row)
            for row in (getattr(response, "data", None) or [])
        )

    def get_connection(
        self,
        tenant_id: str,
        provider: str,
    ) -> Optional[IntegrationConnection]:
        response = (
            self.client.table(self.connections_table)
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("provider", provider)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return self._connection_from_row(rows[0]) if rows else None

    def record_event(
        self,
        event: NormalizedIntegrationEvent,
    ) -> tuple[NormalizedIntegrationEvent, bool]:
        existing_response = (
            self.client.table(self.events_table)
            .select("*")
            .eq("tenant_id", event.tenant_id)
            .eq("provider", event.provider)
            .eq("external_event_id", event.external_event_id)
            .limit(1)
            .execute()
        )
        existing_rows = getattr(existing_response, "data", None) or []

        if existing_rows:
            return self._event_from_row(existing_rows[0]), False

        row = {
            "tenant_id": event.tenant_id,
            "provider": event.provider,
            "event_type": event.event_type,
            "external_event_id": event.external_event_id,
            "source_message": event.source_message,
            "payload": event.payload,
            "received_at": event.received_at,
        }

        response = self.client.table(self.events_table).insert(row).execute()
        rows = getattr(response, "data", None) or []

        if rows:
            return self._event_from_row(rows[0]), True

        return event, True

    @staticmethod
    def _connection_from_row(row: Dict[str, Any]) -> IntegrationConnection:
        return IntegrationConnection(
            tenant_id=row["tenant_id"],
            provider=row["provider"],
            status=row.get("status", "configured"),
            external_account_id=row.get("external_account_id"),
            scopes=row.get("scopes") or [],
            metadata=row.get("metadata") or {},
            connection_id=row.get("connection_id") or "",
            created_at=row.get("created_at") or "",
            updated_at=row.get("updated_at") or "",
        )

    @staticmethod
    def _event_from_row(row: Dict[str, Any]) -> NormalizedIntegrationEvent:
        return NormalizedIntegrationEvent(
            tenant_id=row["tenant_id"],
            provider=row["provider"],
            event_type=row["event_type"],
            external_event_id=row["external_event_id"],
            payload=row.get("payload") or {},
            source_message=row.get("source_message"),
            received_at=row.get("received_at") or "",
        )


def build_supabase_integration_store_from_env() -> Optional[SupabaseIntegrationStore]:
    url = (os.getenv("SUPABASE_URL") or "").strip()
    if url and "://" not in url:
        url = f"https://{url}"
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        return None

    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set, "
            "but supabase-py is not installed"
        ) from exc

    client = create_client(url, key)
    return SupabaseIntegrationStore(client)
