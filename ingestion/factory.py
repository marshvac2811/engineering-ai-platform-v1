from __future__ import annotations

import os
from typing import Optional

from .service import IngestionService
from .storage import build_supabase_ingestion_service_from_env


def build_ingestion_service() -> IngestionService:
    """Prefer Supabase Storage when production credentials are configured."""
    service = build_supabase_ingestion_service_from_env()
    if service is not None:
        return service
    return IngestionService()
