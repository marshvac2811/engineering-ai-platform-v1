"""Fiverr adapter boundary.

As of the current platform documentation checked for this build, Fiverr's public
platform API integration page advertises API integration as "coming soon". The
trial therefore uses a provider-neutral intake path (typically notification email
or an imported event) until Fiverr exposes the required freelancer-side API.
"""
from __future__ import annotations

from typing import Any, Dict
from .common import parse_rfc822


def normalize_notification_email(*, tenant_id: str, raw_rfc822: bytes) -> Dict[str, Any]:
    parsed = parse_rfc822(raw_rfc822)
    event_key = parsed.get("subject") or parsed.get("from") or "notification"
    return {
        "tenant_id": tenant_id,
        "provider": "fiverr",
        "event_type": "notification.received",
        "external_event_id": str(abs(hash((parsed.get("from", ""), parsed.get("subject", ""), parsed.get("body_text", ""))))),
        "payload": parsed,
        "source_message": event_key,
    }


def normalize_event(*, tenant_id: str, event: Dict[str, Any], event_type: str = "notification.received") -> Dict[str, Any]:
    external_id = str(event.get("id") or event.get("order_id") or event.get("message_id") or "unknown")
    return {
        "tenant_id": tenant_id,
        "provider": "fiverr",
        "event_type": event_type,
        "external_event_id": external_id,
        "payload": dict(event),
        "source_message": external_id,
    }
