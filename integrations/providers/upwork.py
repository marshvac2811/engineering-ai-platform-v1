"""Upwork OAuth and event normalization boundary."""
from __future__ import annotations

from urllib.parse import urlencode
from typing import Any, Dict

UPWORK_AUTHORIZE_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
UPWORK_TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"


def authorization_url(client_id: str, redirect_uri: str, *, state: str, use_pkce: bool = True, code_challenge: str | None = None) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if use_pkce and code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return UPWORK_AUTHORIZE_URL + "?" + urlencode(params)


def normalize_event(*, tenant_id: str, event: Dict[str, Any], event_type: str = "message.received") -> Dict[str, Any]:
    external_id = str(event.get("id") or event.get("room_id") or event.get("contract_id") or event.get("proposal_id") or "unknown")
    payload = dict(event)
    return {
        "tenant_id": tenant_id,
        "provider": "upwork",
        "event_type": event_type,
        "external_event_id": external_id,
        "payload": payload,
        "source_message": external_id,
    }
