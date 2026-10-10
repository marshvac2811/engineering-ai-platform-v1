"""Gmail OAuth/API boundary and message normalization.

The engineering layer never calls Gmail directly. This module handles provider
HTTP/OAuth concerns and returns normalized messages to the integration service.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import stat
import time
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .common import decode_b64url, message_headers

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
GMAIL_READ_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_SEND_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
# Drafts and sending both need compose; keep readonly so the same grant can still sync the inbox.
GMAIL_COMPOSE_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.compose"]


class GmailProviderError(RuntimeError):
    """Raised when Gmail OAuth/API operations fail."""


class GmailOAuthStateStore:
    """Process-local OAuth state store for the trial callback.

    Production should replace this with a tenant-scoped server-side session/state
    store. State values are short-lived and single-use.
    """

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
            raise GmailProviderError("Invalid or expired Gmail OAuth state")
        tenant_id, expires_at = record
        if time.time() > expires_at:
            raise GmailProviderError("Expired Gmail OAuth state")
        return tenant_id


class TrialGmailTokenStore:
    """File-backed token store for local/staging trial only.

    Refresh tokens are written with restrictive file permissions. Replace this
    with encrypted tenant-scoped persistence before commercial production.
    """

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or os.getenv("GMAIL_TOKEN_DIR") or (f"/tmp/engineering_ai/gmail_token_dir" if os.getenv("VERCEL") else ".tokens/gmail"))
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

    def delete(self, tenant_id: str) -> None:
        self._path(tenant_id).unlink(missing_ok=True)


def authorization_url(*, client_id: str, redirect_uri: str, state: str,
                      scopes: Iterable[str] | None = None, login_hint: str | None = None) -> str:
    requested_scopes = list(scopes or GMAIL_READ_SCOPES)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(requested_scopes),
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    if login_hint:
        params["login_hint"] = login_hint
    return GMAIL_AUTH_URL + "?" + urlencode(params)


def _http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
               data: dict[str, Any] | None = None, json_body: Any = None) -> dict[str, Any]:
    payload = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if json_body is not None:
        payload = json.dumps(json_body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    if data is not None:
        payload = urlencode({k: v for k, v in data.items() if v is not None}).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GmailProviderError(f"Gmail/Google HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise GmailProviderError(f"Gmail/Google network error: {exc}") from exc


def exchange_code(*, client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict[str, Any]:
    return _http_json(GMAIL_TOKEN_URL, method="POST", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })


def refresh_access_token(*, client_id: str, client_secret: str, refresh_token: str) -> dict[str, Any]:
    return _http_json(GMAIL_TOKEN_URL, method="POST", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })


def _authorized_request(*, access_token: str, url: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    final_url = url
    if query:
        final_url += "?" + urlencode({k: v for k, v in query.items() if v is not None})
    return _http_json(final_url, headers={"Authorization": f"Bearer {access_token}"})


class GmailAPIClient:
    """Small REST client using only Python stdlib for trial portability."""

    def __init__(self, *, client_id: str, client_secret: str, token_store: TrialGmailTokenStore) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_store = token_store

    def _access_token(self, tenant_id: str) -> str:
        token = self.token_store.get(tenant_id)
        if not token:
            raise GmailProviderError("Gmail is not connected for this tenant")
        access_token = token.get("access_token")
        expiry = float(token.get("expires_at", 0) or 0)
        if access_token and time.time() < expiry - 60:
            return str(access_token)
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise GmailProviderError("Gmail credential has no refresh_token; reconnect Gmail")
        refreshed = refresh_access_token(
            client_id=self.client_id,
            client_secret=self.client_secret,
            refresh_token=str(refresh_token),
        )
        refreshed["refresh_token"] = refresh_token
        refreshed["expires_at"] = time.time() + float(refreshed.get("expires_in", 3600))
        self.token_store.save(tenant_id, refreshed)
        return str(refreshed["access_token"])

    def profile(self, tenant_id: str) -> dict[str, Any]:
        return _authorized_request(
            access_token=self._access_token(tenant_id),
            url=f"{GMAIL_API_BASE}/users/me/profile",
        )

    def list_message_ids(self, tenant_id: str, *, q: str = "", max_results: int = 20) -> list[dict[str, str]]:
        result = _authorized_request(
            access_token=self._access_token(tenant_id),
            url=f"{GMAIL_API_BASE}/users/me/messages",
            query={"q": q, "maxResults": min(max(1, int(max_results)), 500)},
        )
        return result.get("messages") or []

    def get_message(self, tenant_id: str, message_id: str) -> dict[str, Any]:
        return _authorized_request(
            access_token=self._access_token(tenant_id),
            url=f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
            query={"format": "full"},
        )

    def _post(self, tenant_id: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return _http_json(
            f"{GMAIL_API_BASE}{path}", method="POST",
            headers={"Authorization": f"Bearer {self._access_token(tenant_id)}"},
            json_body=body,
        )

    def create_draft(self, tenant_id: str, *, raw_b64url: str, thread_id: str | None = None) -> dict[str, Any]:
        message: dict[str, Any] = {"raw": raw_b64url}
        if thread_id:
            message["threadId"] = thread_id
        return self._post(tenant_id, "/users/me/drafts", {"message": message})

    def send_message(self, tenant_id: str, *, raw_b64url: str, thread_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"raw": raw_b64url}
        if thread_id:
            body["threadId"] = thread_id
        return self._post(tenant_id, "/users/me/messages/send", body)

    def get_attachment(self, tenant_id: str, message_id: str, attachment_id: str) -> bytes:
        result = _authorized_request(
            access_token=self._access_token(tenant_id),
            url=f"{GMAIL_API_BASE}/users/me/messages/{message_id}/attachments/{attachment_id}",
        )
        data = str(result.get("data", ""))
        return decode_b64url(data)


def build_reply_message(*, to: str, subject: str, body_text: str, in_reply_to: str | None = None,
                        attachments: Iterable[tuple[str, str, bytes]] = ()) -> str:
    """Build an RFC 822 reply and return it base64url-encoded for the Gmail API.

    ``attachments`` are ``(filename, mime_type, data)``. The recipient is reduced to the single bare
    address from the original sender so a display-name header cannot smuggle extra recipients.
    """
    _name, address = parseaddr(to)
    if not address or "@" not in address or len(getaddresses([to])) != 1:
        raise ValueError("A single valid reply address is required")
    clean_subject = " ".join(str(subject or "").split())
    if not clean_subject.lower().startswith("re:"):
        clean_subject = f"Re: {clean_subject}".strip()
    msg = EmailMessage()
    msg["To"] = address
    msg["Subject"] = clean_subject
    if in_reply_to:
        ref = " ".join(str(in_reply_to).split())
        msg["In-Reply-To"] = ref
        msg["References"] = ref
    msg.set_content(body_text)
    for filename, mime_type, data in attachments:
        maintype, _, subtype = (mime_type or "application/octet-stream").partition("/")
        msg.add_attachment(data, maintype=maintype or "application", subtype=subtype or "octet-stream", filename=filename)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


def _walk_parts(part: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield part
    for child in part.get("parts") or []:
        yield from _walk_parts(child)


def normalize_message(*, tenant_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
    payload = message.get("payload") or {}
    headers = message_headers(payload.get("headers") or [])
    body_parts: list[str] = []
    attachments: list[dict[str, Any]] = []

    for part in _walk_parts(payload):
        part_body = part.get("body") or {}
        filename = part.get("filename")
        mime_type = str(part.get("mimeType", ""))
        if filename:
            attachments.append({
                "filename": filename,
                "mime_type": mime_type,
                "attachment_id": part_body.get("attachmentId"),
                "size": int(part_body.get("size", 0) or 0),
            })
        data = part_body.get("data")
        if data and mime_type.startswith("text/"):
            body_parts.append(decode_b64url(data).decode("utf-8", errors="replace"))

    return {
        "tenant_id": tenant_id,
        "provider": "gmail",
        "event_type": "message.received",
        "external_event_id": str(message.get("id") or message.get("threadId") or "unknown"),
        "payload": {
            "subject": headers.get("subject", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "date": headers.get("date", ""),
            "body_text": "\n".join(x for x in body_parts if x).strip(),
            "attachments": attachments,
            "thread_id": message.get("threadId"),
            "message_id_header": headers.get("message-id", ""),
            "reply_to": headers.get("reply-to") or headers.get("from", ""),
            "label_ids": message.get("labelIds", []),
        },
        "source_message": str(message.get("id") or ""),
    }
