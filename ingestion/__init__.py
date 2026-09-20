"""Document/file ingestion for engineering jobs."""
from .models import Attachment, ExtractionResult, DocumentChunk
from .extractors import extract_bytes, detect_source_type
from .service import IngestionService, LocalAttachmentStore

__all__ = [
    "Attachment",
    "ExtractionResult",
    "DocumentChunk",
    "extract_bytes",
    "detect_source_type",
    "IngestionService",
    "LocalAttachmentStore",
]
