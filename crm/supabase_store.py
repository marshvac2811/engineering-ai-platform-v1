from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import CRMDeal


class SupabaseCRMStore:
    def __init__(self, client: Any, *, deals_table: str = "crm_deals") -> None:
        self.client = client
        self.deals_table = deals_table

    def save(self, deal: CRMDeal) -> CRMDeal:
        row = {
            "deal_id": deal.deal_id,
            "tenant_id": deal.tenant_id,
            "name": deal.name,
            "category": deal.category,
            "stakeholder": deal.stakeholder,
            "contact": deal.contact,
            "company": deal.company,
            "value": deal.value,
            "stage": deal.stage,
            "next_follow_up": deal.next_follow_up,
            "notes": deal.notes,
            "engineering_job_id": deal.engineering_job_id,
            "hubspot_object_id": deal.hubspot_object_id,
            "created_at": deal.created_at,
            "updated_at": deal.updated_at,
        }

        self.client.table(self.deals_table).upsert(
            row,
            on_conflict="deal_id",
        ).execute()

        return deal

    def get(self, tenant_id: str, deal_id: str) -> Optional[CRMDeal]:
        response = (
            self.client.table(self.deals_table)
            .select("*")
            .eq("deal_id", deal_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )

        rows = getattr(response, "data", None) or []
        if not rows:
            return None

        return self._hydrate(rows[0])

    def list(self, tenant_id: str) -> List[CRMDeal]:
        response = (
            self.client.table(self.deals_table)
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=False)
            .execute()
        )

        rows = getattr(response, "data", None) or []
        return [self._hydrate(row) for row in rows]

    def delete(self, tenant_id: str, deal_id: str) -> bool:
        existing = self.get(tenant_id, deal_id)
        if not existing:
            return False

        response = (
            self.client.table(self.deals_table)
            .delete()
            .eq("deal_id", deal_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )

        return bool(getattr(response, "data", None))

    def _hydrate(self, row: Dict[str, Any]) -> CRMDeal:
        return CRMDeal(
            tenant_id=str(row["tenant_id"]),
            name=row["name"],
            category=row.get("category", "Project Sales"),
            stakeholder=row.get("stakeholder", "Other"),
            contact=row.get("contact", ""),
            company=row.get("company", ""),
            value=float(row.get("value") or 0),
            stage=row.get("stage", "budgetary"),
            next_follow_up=row.get("next_follow_up"),
            notes=row.get("notes", ""),
            engineering_job_id=(
                str(row["engineering_job_id"])
                if row.get("engineering_job_id")
                else None
            ),
            hubspot_object_id=row.get("hubspot_object_id"),
            deal_id=str(row["deal_id"]),
            created_at=row.get("created_at") or "",
            updated_at=row.get("updated_at") or "",
        )


def build_supabase_crm_store_from_env() -> Optional[SupabaseCRMStore]:
    import os

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
    return SupabaseCRMStore(client)
