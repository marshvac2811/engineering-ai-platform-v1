from __future__ import annotations
from typing import Dict, List, Optional
from .models import CRMDeal


class InMemoryCRMStore:
    def __init__(self):
        self._deals: Dict[str, CRMDeal] = {}

    def save(self, deal: CRMDeal) -> CRMDeal:
        deal.updated_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        self._deals[deal.deal_id] = deal
        return deal

    def get(self, tenant_id: str, deal_id: str) -> Optional[CRMDeal]:
        deal = self._deals.get(deal_id)
        return deal if deal and deal.tenant_id == tenant_id else None

    def list(self, tenant_id: str) -> List[CRMDeal]:
        return [d for d in self._deals.values() if d.tenant_id == tenant_id]

    def delete(self, tenant_id: str, deal_id: str) -> bool:
        deal = self.get(tenant_id, deal_id)
        if not deal:
            return False
        del self._deals[deal_id]
        return True
