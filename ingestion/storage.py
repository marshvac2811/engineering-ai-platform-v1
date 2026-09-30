from __future__ import annotations

from typing import Any, Optional


class SupabaseAttachmentStore:
    """Supabase Storage adapter using the official Python client shape.

    The supplied client is intentionally duck-typed so this module remains
    testable without requiring supabase-py in the default local environment.
    """

    provider_name = "supabase_storage"

    def __init__(self, client: Any, *, bucket: str = "engineering-attachments") -> None:
        self.client = client
        self.bucket = bucket

    def _bucket(self) -> Any:
        return self.client.storage.from_(self.bucket)

    def put(self, key: str, data: bytes, *, mime_type: Optional[str] = None) -> str:
        options = {"upsert": "false"}
        if mime_type:
            options["content-type"] = mime_type
        self._bucket().upload(path=key, file=data, file_options=options)
        return key

    def get(self, key: str) -> bytes:
        value = self._bucket().download(key)
        if value is None:
            raise KeyError(f"Attachment storage key not found: {key}")
        return bytes(value)


class AttachmentRepository:
    """Durable metadata/chunk persistence interface."""

    def save_attachment(self, attachment: Any) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def save_extraction(self, attachment: Any, result: Any) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class SupabaseAttachmentRepository(AttachmentRepository):
    """Persists attachment metadata and extracted chunks in Postgres."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def save_attachment(self, attachment: Any) -> None:
        row = {
            "attachment_id": attachment.attachment_id,
            "tenant_id": attachment.tenant_id,
            "job_id": attachment.job_id,
            "filename": attachment.filename,
            "mime_type": attachment.mime_type,
            "source_type": attachment.source_type,
            "size_bytes": attachment.size_bytes,
            "sha256": attachment.sha256,
            "storage_provider": attachment.storage_provider,
            "storage_key": attachment.storage_key,
            "metadata": attachment.metadata,
            "extraction_status": attachment.extraction_status,
            "extraction_metadata": attachment.extraction_metadata,
            "created_at": attachment.created_at,
        }
        self.client.table("automation_attachments").upsert(
            row, on_conflict="attachment_id"
        ).execute()

    def save_extraction(self, attachment: Any, result: Any) -> None:
        update = {
            "extraction_status": result.status,
            "extraction_metadata": {
                **(result.metadata or {}),
                "warnings": result.warnings,
                "errors": result.errors,
                "chunk_count": len(result.chunks),
            },
        }
        self.client.table("automation_attachments").update(update).eq(
            "attachment_id", attachment.attachment_id
        ).execute()

        if result.chunks:
            rows = [
                {
                    "chunk_id": chunk.chunk_id,
                    "tenant_id": attachment.tenant_id,
                    "attachment_id": attachment.attachment_id,
                    "chunk_index": chunk.index,
                    "text_content": chunk.text,
                    "metadata": chunk.metadata,
                    "created_at": chunk.created_at,
                }
                for chunk in result.chunks
            ]
            self.client.table("automation_document_chunks").upsert(
                rows, on_conflict="attachment_id,chunk_index"
            ).execute()


def build_supabase_ingestion_service_from_env() -> Any:
    """Create a production ingestion service when Supabase server credentials exist."""
    import os

    url = (os.getenv("SUPABASE_URL") or "").strip()
    if url and "://" not in url:
        url = f"https://{url}"
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None

    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - optional production dependency
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set, but supabase-py is not installed"
        ) from exc

    from .service import IngestionService

    client = create_client(url, key)
    bucket = os.getenv("SUPABASE_ATTACHMENT_BUCKET", "engineering-attachments")
    store = SupabaseAttachmentStore(client, bucket=bucket)
    repo = SupabaseAttachmentRepository(client)
    return IngestionService(store=store, repository=repo)
