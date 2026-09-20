from __future__ import annotations
from typing import Any, Dict, Optional
from .hubspot import HubSpotAdapter
from .models import CRMDeal
from .store import InMemoryCRMStore


class CRMService:
    def __init__(self, store=None, *, tenant_id: Optional[str] = None, hubspot=None):
        self.store = store or InMemoryCRMStore()
        self.tenant_id = tenant_id
        self.hubspot = hubspot or HubSpotAdapter()

    def _require_tenant(self, tenant_id: Optional[str]) -> str:
        value = tenant_id or self.tenant_id
        if not value:
            raise ValueError("tenant_id is required")
        return value

    def create_deal(self, **kwargs: Any) -> CRMDeal:
        tenant_id = self._require_tenant(kwargs.pop("tenant_id", None))
        deal = CRMDeal(tenant_id=tenant_id, **kwargs)
        deal.validate()
        return self.store.save(deal)

    def get(self, deal_id: str) -> CRMDeal:
        deal = self.store.get(self._require_tenant(None), deal_id)
        if not deal:
            raise KeyError(f"Unknown CRM deal: {deal_id}")
        return deal

    def list(self):
        return self.store.list(self._require_tenant(None))

    def update(self, deal_id: str, **updates: Any) -> CRMDeal:
        deal = self.get(deal_id)
        allowed = {"name", "category", "stakeholder", "contact", "company", "value", "stage", "next_follow_up", "notes", "engineering_job_id", "hubspot_object_id"}
        for key, value in updates.items():
            if key in allowed:
                setattr(deal, key, value)
        deal.validate()
        return self.store.save(deal)

    def sync_hubspot(self, deal_id: str) -> Dict[str, Any]:
        deal = self.get(deal_id)
        return self.hubspot.sync(deal)

    def link_engineering_job(self, deal_id: str, job_id: str) -> CRMDeal:
        return self.update(deal_id, engineering_job_id=job_id)
