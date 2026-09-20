from .models import CRMDeal, PIPELINE_STAGES
from .service import CRMService
from .store import InMemoryCRMStore
from .hubspot import HubSpotAdapter

__all__ = ["CRMDeal", "PIPELINE_STAGES", "CRMService", "InMemoryCRMStore", "HubSpotAdapter"]

from .supabase_store import SupabaseCRMStore
