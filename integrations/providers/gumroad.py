"""Gumroad API/webhook normalization boundary."""
from __future__ import annotations

from typing import Any, Dict

GUMROAD_API_BASE = "https://api.gumroad.com/v2"
GUMROAD_RESOURCE_TYPES = {
    "sale",
    "refund",
    "dispute",
    "dispute_won",
    "cancellation",
    "subscription_updated",
    "subscription_ended",
    "subscription_restarted",
}


def normalize_event(*, tenant_id: str, event: Dict[str, Any], event_type: str | None = None) -> Dict[str, Any]:
    event_name = event_type or str(event.get("resource_name") or event.get("event") or "sale")
    external_id = str(event.get("id") or event.get("sale_id") or event.get("subscription_id") or event.get("product_id") or "unknown")
    return {
        "tenant_id": tenant_id,
        "provider": "gumroad",
        "event_type": event_name,
        "external_event_id": external_id,
        "payload": dict(event),
        "source_message": external_id,
    }
