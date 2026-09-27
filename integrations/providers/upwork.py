"""Upwork OAuth and normalized event boundary."""
from __future__ import annotations

import json
import os
import secrets
import stat
import time
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UPWORK_AUTHORIZE_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
UPWORK_TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"


class UpworkProviderError(RuntimeError):
    pass


class UpworkOAuthStateStore:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self._states: dict[str, tuple[str, float]] = {}

    def create(self, tenant_id: str) -> str:
        state = secrets.token_urlsafe(32)
        self._states[state] = (tenant_id, time.time() + self.ttl_seconds)
        return state

    def consume(self, state: str) -> str:
        record = self._states.pop(state, None)
        if not record:
            raise UpworkProviderError("Invalid or expired Upwork OAuth state")
        tenant_id, expires_at = record
        if time.time() > expires_at:
            raise UpworkProviderError("Expired Upwork OAuth state")
        return tenant_id


class TrialUpworkTokenStore:
    """Local/staging token store. Production should use encrypted tenant storage."""
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or os.getenv("UPWORK_TOKEN_DIR") or (f"/tmp/engineering_ai/upwork_token_dir" if os.getenv("VERCEL") else ".tokens/upwork"))
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(stat.S_IRWXU)
        except OSError:
            pass

    def _path(self, tenant_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in tenant_id)
        return self.root / f"{safe}.json"

    def save(self, tenant_id: str, token: dict[str, Any]) -> None:
        path = self._path(tenant_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(token), encoding="utf-8")
        try:
            temp.chmod(stat.S_IRUSR | stat.S_IWUSR)
            temp.replace(path)
        except OSError:
            temp.unlink(missing_ok=True)
            raise

    def get(self, tenant_id: str) -> dict[str, Any] | None:
        path = self._path(tenant_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def authorization_url(client_id: str, redirect_uri: str, *, state: str, code_challenge: str | None = None) -> str:
    params = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri, "state": state}
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return UPWORK_AUTHORIZE_URL + "?" + urlencode(params)


def _http_json(url: str, *, data: dict[str, Any]) -> dict[str, Any]:
    payload = urlencode({k: v for k, v in data.items() if v is not None}).encode("utf-8")
    req = Request(url, data=payload, headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise UpworkProviderError(f"Upwork HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise UpworkProviderError(f"Upwork network error: {exc}") from exc


def exchange_code(*, client_id: str, client_secret: str, redirect_uri: str, code: str, code_verifier: str | None = None) -> dict[str, Any]:
    return _http_json(UPWORK_TOKEN_URL, data={
        "grant_type": "authorization_code", "client_id": client_id, "client_secret": client_secret,
        "code": code, "redirect_uri": redirect_uri, "code_verifier": code_verifier,
    })


def refresh_access_token(*, client_id: str, client_secret: str, refresh_token: str) -> dict[str, Any]:
    return _http_json(UPWORK_TOKEN_URL, data={
        "grant_type": "refresh_token", "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token,
    })


def normalize_event(*, tenant_id: str, event: Dict[str, Any], event_type: str = "message.received") -> Dict[str, Any]:
    external_id = str(event.get("id") or event.get("room_id") or event.get("contract_id") or event.get("proposal_id") or "unknown")
    payload = dict(event)
    return {"tenant_id": tenant_id, "provider": "upwork", "event_type": event_type,
            "external_event_id": external_id, "payload": payload, "source_message": external_id}
