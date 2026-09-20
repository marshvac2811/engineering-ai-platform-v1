from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DocumentChunk:
    chunk_id: str
    attachment_id: str
    index: int
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    @classmethod
    def create(cls, *, attachment_id: str, index: int, text: str, metadata: Optional[Dict[str, Any]] = None) -> "DocumentChunk":
        return cls(uuid4().hex, attachment_id, index, text, metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionResult:
    status: str
    source_type: str
    mime_type: str
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    chunks: List[DocumentChunk] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "source_type": self.source_type,
            "mime_type": self.mime_type,
            "text": self.text,
            "metadata": self.metadata,
            "warnings": self.warnings,
            "errors": self.errors,
            "chunks": [c.to_dict() for c in self.chunks],
        }


@dataclass
class Attachment:
    attachment_id: str
    tenant_id: str
    job_id: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    source_type: str
    storage_key: Optional[str] = None
    storage_provider: str = "local"
    metadata: Dict[str, Any] = field(default_factory=dict)
    extraction_status: str = "pending"
    extraction_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        job_id: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        source_type: str,
        storage_key: Optional[str] = None,
        storage_provider: str = "local",
        metadata: Optional[Dict[str, Any]] = None,
        attachment_id: Optional[str] = None,
    ) -> "Attachment":
        return cls(
            attachment_id=attachment_id or str(uuid4()),
            tenant_id=tenant_id,
            job_id=job_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            source_type=source_type,
            storage_key=storage_key,
            storage_provider=storage_provider,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
