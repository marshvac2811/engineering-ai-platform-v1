"""Tenant-scoped helpers for the SaaS boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: Optional[str] = None
    role: str = "member"

    def require_user(self) -> str:
        if not self.user_id:
            raise PermissionError("Authenticated user is required")
        return self.user_id

    def can_review(self) -> bool:
        return self.role in {"owner", "admin", "engineer", "reviewer"}

    def can_dispatch(self) -> bool:
        return self.role in {"owner", "admin", "engineer"}
