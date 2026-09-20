from __future__ import annotations
import base64
import hashlib
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

from .extractors import detect_source_type, extract_bytes
from .models import Attachment, ExtractionResult


class AttachmentStore:
    provider_name = "local"
    def put(self, key: str, data: bytes, *, mime_type: Optional[str] = None) -> str:  # pragma: no cover - interface
        raise NotImplementedError
    def get(self, key: str) -> bytes:  # pragma: no cover - interface
        raise NotImplementedError


class LocalAttachmentStore(AttachmentStore):
    def __init__(self) -> None:
        self._data: Dict[str, bytes] = {}
    provider_name = "local"
    def put(self, key: str, data: bytes, *, mime_type: Optional[str] = None) -> str:
        self._data[key] = data
        return key
    def get(self, key: str) -> bytes:
        if key not in self._data:
            raise KeyError(f"Attachment storage key not found: {key}")
        return self._data[key]


class IngestionService:
    def __init__(self, store: Optional[AttachmentStore] = None, repository: Optional[Any] = None) -> None:
        self.store = store or LocalAttachmentStore()
        self.repository = repository

    def register(
        self,
        *,
        tenant_id: str,
        job_id: str,
        filename: str,
        data: bytes,
        mime_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Attachment:
        if not tenant_id or not job_id:
            raise ValueError("tenant_id and job_id are required")
        if not filename.strip():
            raise ValueError("filename is required")
        sha256 = hashlib.sha256(data).hexdigest()
        source_type = detect_source_type(filename, mime_type)
        key = f"{tenant_id}/{job_id}/{sha256}-{Path(filename).name}"
        self.store.put(key, data, mime_type=mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream")
        attachment = Attachment.create(
            tenant_id=tenant_id,
            job_id=job_id,
            filename=Path(filename).name,
            mime_type=mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            size_bytes=len(data),
            sha256=sha256,
            source_type=source_type,
            storage_key=key,
            storage_provider=getattr(self.store, "provider_name", "local"),
            metadata=metadata,
        )
        if self.repository is not None:
            self.repository.save_attachment(attachment)
        return attachment

    def extract(self, attachment: Attachment) -> ExtractionResult:
        if not attachment.storage_key:
            raise ValueError("Attachment has no storage key")
        data = self.store.get(attachment.storage_key)
        result = extract_bytes(data, filename=attachment.filename, mime_type=attachment.mime_type, attachment_id=attachment.attachment_id)
        if self.repository is not None:
            self.repository.save_extraction(attachment, result)
        return result

    @staticmethod
    def decode_base64(value: str) -> bytes:
        try:
            return base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError("content_base64 is not valid base64") from exc
