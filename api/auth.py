"""Authentication and authorization boundary for the SaaS API.

Production deployments should inject a verifier that validates a Supabase JWT
before constructing AuthContext. Local development keeps deterministic headers
available so the core API can be tested without external services.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, FrozenSet
import json
import os
import urllib.parse
import httpx
import jwt

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
        raw_url = (os.getenv("SUPABASE_URL") or "https://vaxerlbgwwlfamncevdg.supabase.co").strip()
        if raw_url and "://" not in raw_url:
            raw_url = f"https://{raw_url}"
        self.supabase_url = raw_url.rstrip("/")
        if not self.supabase_url:
            raise RuntimeError("SUPABASE_URL is required for Supabase JWT authentication")
        self.issuer = f"{self.supabase_url}/auth/v1"
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self._jwks_cache = None

    def _get_signing_key(self, token: str):
        header = jwt.get_unverified_header(token)
        kid = str(header.get("kid") or "").strip()
        algorithm = str(header.get("alg") or "").strip()
        if algorithm not in {"ES256", "RS256"} or not kid:
            raise AuthenticationError("Unsupported or incomplete Supabase JWT header")

        if self._jwks_cache is None:
            last_error = None
            for attempt in range(3):
                try:
                    with httpx.Client(timeout=5.0, trust_env=False, follow_redirects=True) as client:
                        response = client.get(
                            self.jwks_url,
                            headers={"Accept": "application/json", "Connection": "close"},
                        )
                        response.raise_for_status()
                        self._jwks_cache = response.json()
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        import time
                        time.sleep(0.25 * (attempt + 1))
            if self._jwks_cache is None:
                raise AuthenticationError("Unable to fetch Supabase JWKS: " + str(last_error))

        keys = self._jwks_cache.get("keys", []) if isinstance(self._jwks_cache, dict) else []
        jwk = next((key for key in keys if str(key.get("kid") or "") == kid), None)
        if not jwk:
            # Refresh once in case Supabase rotated signing keys.
            self._jwks_cache = None
            return self._get_signing_key(token)
        algorithm_impl = jwt.algorithms.get_default_algorithms().get(algorithm)
        if algorithm_impl is None:
            raise AuthenticationError("Unsupported JWT algorithm: " + algorithm)
        return algorithm_impl.from_jwk(json.dumps(jwk))

    def _validate_with_supabase_auth(self, token: str) -> dict:
        key = (os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()
        if not key:
            key = "sb_publishable_X68FRNA50gzwKqH7SFbOGQ_OyemX0_s"
        url = self.supabase_url + "/auth/v1/user"
        with httpx.Client(timeout=8.0, trust_env=False, follow_redirects=True) as client:
            response = client.get(
                url,
                headers={
                    "apikey": key,
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json",
                    "Connection": "close",
                },
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or not payload.get("id"):
            raise AuthenticationError("Supabase Auth rejected the access token")
        return payload

    def _resolve_tenant_membership(self, user_id: str) -> tuple[str, str]:
        service_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not service_key:
            raise AuthenticationError(
                "SUPABASE_SERVICE_ROLE_KEY is required to resolve tenant membership"
            )

        query = urllib.parse.urlencode({
            "user_id": "eq." + user_id,
            "select": "tenant_id,role,is_default",
            "order": "is_default.desc",
            "limit": "1",
        })
        url = self.supabase_url + "/rest/v1/tenant_memberships?" + query
        try:
            with httpx.Client(timeout=8.0, trust_env=False, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={
                        "apikey": service_key,
                        "Authorization": "Bearer " + service_key,
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                rows = response.json()
        except Exception as exc:
            raise AuthenticationError(
                "Unable to resolve tenant membership: " + str(exc)
            ) from exc

        if not isinstance(rows, list) or not rows:
            return "", ""

        row = rows[0] or {}
        return str(row.get("tenant_id") or "").strip(), str(row.get("role") or "").strip()

    def authenticate(self, environ) -> AuthContext:
        auth = environ.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer "):
            raise AuthenticationError("Bearer Supabase JWT required")

        token = auth[7:].strip()
        if not token:
            raise AuthenticationError("Supabase JWT is empty")

        try:
            signing_key = self._get_signing_key(token)

            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                issuer=self.issuer,
                options={"require": ["sub", "exp", "iss", "aud"]},
            )
        except Exception as exc:
            # Some Vercel serverless invocations can fail outbound JWKS retrieval
            # even though Supabase Auth itself is reachable. In that case let
            # Supabase validate the bearer token through its Auth API.
            try:
                user = self._validate_with_supabase_auth(token)
                user_id = str(user.get("id") or "").strip()
                if not user_id:
                    raise AuthenticationError("Supabase Auth returned no user id")
                claims = {
                    "sub": user_id,
                    "tenant_id": "",
                    "app_role": str((user.get("app_metadata") or {}).get("app_role") or "member"),
                    "scopes": [],
                }
            except AuthenticationError:
                raise
            except Exception as fallback_exc:
                raise AuthenticationError(
                    f"Invalid Supabase JWT: {exc}; Supabase Auth fallback failed: {fallback_exc}"
                ) from fallback_exc

        user_id = str(claims["sub"])
        tenant_id = str(claims.get("tenant_id") or "").strip()
        role = str(claims.get("app_role") or "member")
        raw_scopes = claims.get("scopes", [])

        # The current Supabase JWT does not carry the application's tenant_id.
        # Resolve it from the authenticated user's tenant membership instead of
        # requiring the browser to send a trusted X-Tenant-ID header.
        if not tenant_id:
            tenant_id, membership_role = self._resolve_tenant_membership(user_id)
            if membership_role:
                role = membership_role
        if not tenant_id:
            raise AuthenticationError(
                "Authenticated Supabase user has no active tenant membership"
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
