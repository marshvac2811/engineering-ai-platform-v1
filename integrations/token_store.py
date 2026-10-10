"""Durable, encrypted OAuth token storage for integrations (Supabase + Fernet).

Render's disk is ephemeral, so file-backed refresh tokens vanish on every redeploy and Gmail would
silently disconnect. Tokens are encrypted with ``GMAIL_TOKEN_ENCRYPTION_KEY`` (a Fernet key) before
they are written; Supabase only ever sees ciphertext. If no key is configured the caller must fall
back to the trial file store (fail closed: tokens are never stored in clear in the database).
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional


class TokenEncryptionError(RuntimeError):
    pass


def _fernet(key: str):
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        raise TokenEncryptionError("The 'cryptography' package is required for encrypted token storage") from exc
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise TokenEncryptionError("GMAIL_TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from exc


class EncryptedSupabaseTokenStore:
    """Same interface as ``TrialGmailTokenStore`` (save/get/delete) keyed by tenant."""

    def __init__(self, client: Any, *, provider: str = "gmail", key: Optional[str] = None, table: str = "integration_tokens") -> None:
        key = key or os.getenv("GMAIL_TOKEN_ENCRYPTION_KEY", "")
        if not key:
            raise TokenEncryptionError("GMAIL_TOKEN_ENCRYPTION_KEY is not configured")
        self._fernet = _fernet(key)
        self.client = client
        self.provider = provider
        self.table = table

    def save(self, tenant_id: str, token: dict[str, Any]) -> None:
        blob = self._fernet.encrypt(json.dumps(token).encode("utf-8")).decode("ascii")
        self.client.table(self.table).upsert(
            {"tenant_id": tenant_id, "provider": self.provider, "token_encrypted": blob},
            on_conflict="tenant_id,provider",
        ).execute()

    def get(self, tenant_id: str) -> dict[str, Any] | None:
        rows = (self.client.table(self.table).select("token_encrypted").eq("tenant_id", tenant_id)
                .eq("provider", self.provider).limit(1).execute().data) or []
        if not rows:
            return None
        try:
            return json.loads(self._fernet.decrypt(str(rows[0]["token_encrypted"]).encode("ascii")).decode("utf-8"))
        except Exception as exc:  # wrong key / corrupted row: force a reconnect instead of crashing
            raise TokenEncryptionError("Stored token could not be decrypted; reconnect the integration") from exc

    def delete(self, tenant_id: str) -> None:
        self.client.table(self.table).delete().eq("tenant_id", tenant_id).eq("provider", self.provider).execute()


def build_gmail_token_store(supabase_client: Any):
    """Encrypted Supabase store when a client and key exist; otherwise the ephemeral trial file store."""
    from integrations.providers.gmail import TrialGmailTokenStore
    if supabase_client is not None and os.getenv("GMAIL_TOKEN_ENCRYPTION_KEY", "").strip():
        return EncryptedSupabaseTokenStore(supabase_client)
    return TrialGmailTokenStore()
