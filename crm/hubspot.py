from __future__ import annotations
from typing import Any, Dict
from .models import CRMDeal


class HubSpotAdapter:
    """Provider-neutral outbound adapter.

    V1 deliberately prepares a canonical HubSpot-ready payload without making a
    network call. The real connector can be attached when the user's HubSpot
    account is connected.
    """

    provider = "hubspot"

    def deal_payload(self, deal: CRMDeal) -> Dict[str, Any]:
        return {
            "properties": {
                "dealname": deal.name,
                "amount": str(deal.value),
                "dealstage": deal.stage,
                "description": deal.notes,
                "mep_category": deal.category,
                "stakeholder_type": deal.stakeholder,
                "contact_name": deal.contact,
                "company_name": deal.company,
                "engineering_job_id": deal.engineering_job_id or "",
                "next_follow_up": deal.next_follow_up or "",
            },
        }

    def sync(self, deal: CRMDeal) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "mode": "prepared",
            "deal_id": deal.deal_id,
            "payload": self.deal_payload(deal),
            "message": "HubSpot connector not connected; outbound payload prepared for sync.",
        }
