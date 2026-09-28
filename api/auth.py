"""Authentication and authorization boundary for the SaaS API.

Production deployments should inject a verifier that validates a Supabase JWT
before constructing AuthContext. Local development keeps deterministic headers
available so the core API can be tested without external services.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, FrozenSet
import os
import jwt
from jwt import PyJWKClient

from jobs.tenant import TenantContext


class AuthenticationError(PermissionError):
    """Authentication failed; callers should return HTTP 401."""


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    user_id: str
    role: str = "member"
    auth_method: str = "development"
    api_key_id: Optional[str] = None
    scopes: FrozenSet[str] = frozenset()

    def tenant_context(self) -> TenantContext:
        return TenantContext(tenant_id=self.tenant_id, user_id=self.user_id, role=self.role)

    def require_scope(self, scope: str) -> None:
        if self.auth_method == "development":
            return
        if scope not in self.scopes and "*" not in self.scopes:
            raise PermissionError(f"API key does not grant scope '{scope}'")

    def require_scope_role(self, required: str) -> None:
        allowed = {
            "review": {"owner", "admin", "engineer", "reviewer"},
            "dispatch": {"owner", "admin", "engineer"},
            "admin": {"owner", "admin"},
        }
        if self.role not in allowed.get(required, set()):
            raise PermissionError(f"Role '{self.role}' is not authorized for {required}")


class Authenticator:
    def authenticate(self, environ) -> AuthContext:  # pragma: no cover - interface
        raise NotImplementedError


class DevelopmentHeaderAuthenticator(Authenticator):
    """Deterministic local/test authenticator.

    Headers:
      X-Tenant-ID
      X-User-ID
      X-User-Role (optional; defaults to member)
    """

    def authenticate(self, environ) -> AuthContext:
        tenant_id = environ.get("HTTP_X_TENANT_ID")
        user_id = environ.get("HTTP_X_USER_ID")
        role = environ.get("HTTP_X_USER_ROLE", "owner")
        if not tenant_id:
            raise AuthenticationError("X-Tenant-ID is required")
        # Backward-compatible local default. Production should require a verified user id.
        user_id = user_id or f"local:{tenant_id}"
        if role not in {"owner", "admin", "engineer", "reviewer", "member"}:
            raise AuthenticationError("Invalid X-User-Role")
        return AuthContext(tenant_id=tenant_id, user_id=user_id, role=role, auth_method="development", scopes=frozenset({"*"}))


class SupabaseJWTAuthenticator(Authenticator):
    """Verify Supabase Auth access tokens using the project's JWKS endpoint."""

    def __init__(self) -> None:
        self.supabase_url = (os.getenv("SUPABASE_URL") or "https://vaxerlbgwwlfamncevdg.supabase.co").rstrip("/")
        if not self.supabase_url:
            raise RuntimeError("SUPABASE_URL is required for Supabase JWT authentication")
        self.issuer = f"{self.supabase_url}/auth/v1"
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self.jwks_client = PyJWKClient(self.jwks_url, cache_keys=True)

    def authenticate(self, environ) -> AuthContext:
        auth = environ.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer "):
            raise AuthenticationError("Bearer Supabase JWT required")

        token = auth[7:].strip()
        if not token:
            raise AuthenticationError("Supabase JWT is empty")

        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                issuer=self.issuer,
                options={"require": ["sub", "exp", "iss", "aud"]},
            )
        except Exception as exc:
            raise AuthenticationError(f"Invalid Supabase JWT: {exc}") from exc

        user_id = str(claims["sub"])
        tenant_id = str(claims.get("tenant_id") or "").strip()
        role = str(claims.get("app_role") or "member")
        raw_scopes = claims.get("scopes", [])

        if not tenant_id:
            raise AuthenticationError(
                "Supabase JWT is valid but tenant_id claim is missing"
            )

        if not isinstance(raw_scopes, (list, tuple, set)):
            raw_scopes = []

        scopes = frozenset(str(x) for x in raw_scopes)

        return AuthContext(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            auth_method="supabase_jwt",
            scopes=scopes,
        )


class ApiKeyAuthenticator(Authenticator):
    """API-key authenticator backed by an injected lookup callback."""

    def __init__(self, lookup: Callable[[str], Optional[dict]]) -> None:
        self.lookup = lookup

    def authenticate(self, environ) -> AuthContext:
        auth = environ.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer "):
            raise AuthenticationError("Bearer API key required")
        secret = auth[7:].strip()
        record = self.lookup(secret)
        if not record:
            raise AuthenticationError("Invalid or revoked API key")
        return AuthContext(
            tenant_id=record["tenant_id"],
            user_id=record["created_by"],
            role=record.get("role", "member"),
            auth_method="api_key",
            api_key_id=record.get("api_key_id"),
            scopes=frozenset(record.get("scopes", [])),
        )
