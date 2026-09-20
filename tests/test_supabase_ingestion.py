from typing import Any

from ingestion.models import Attachment
from ingestion.service import IngestionService
from ingestion.storage import SupabaseAttachmentRepository, SupabaseAttachmentStore


class FakeBucket:
    def __init__(self):
        self.files = {}
        self.calls = []

    def upload(self, *, path, file, file_options=None):
        self.calls.append(("upload", path, file_options or {}))
        self.files[path] = bytes(file)
        return {"path": path}

    def download(self, path):
        return self.files.get(path)


class FakeStorage:
    def __init__(self):
        self.bucket = FakeBucket()

    def from_(self, bucket):
        self.bucket_name = bucket
        return self.bucket


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.filters = []

    def upsert(self, rows, on_conflict=None):
        if isinstance(rows, dict):
            rows = [rows]
        self.db.setdefault(self.name, []).extend(rows)
        return self

    def update(self, values):
        self.update_values = values
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def execute(self):
        rows = self.db.setdefault(self.name, [])
        if hasattr(self, "update_values"):
            for row in rows:
                if all(row.get(k) == v for k, v in self.filters):
                    row.update(self.update_values)
        return FakeResponse(rows)


class FakeClient:
    def __init__(self):
        self.storage = FakeStorage()
        self.db = {}

    def table(self, name):
        return FakeTable(self.db, name)


def test_supabase_storage_roundtrip_preserves_mime_type():
    client = FakeClient()
    store = SupabaseAttachmentStore(client, bucket="engineering-attachments")
    key = "tenant/job/file.txt"
    store.put(key, b"hello", mime_type="text/plain")
    assert client.storage.bucket.calls[0][2]["content-type"] == "text/plain"
    assert store.get(key) == b"hello"


def test_supabase_attachment_repository_persists_metadata_and_chunks():
    client = FakeClient()
    repo = SupabaseAttachmentRepository(client)
    service = IngestionService(
        store=SupabaseAttachmentStore(client),
        repository=repo,
    )
    attachment = service.register(
        tenant_id="11111111-1111-1111-1111-111111111111",
        job_id="22222222-2222-2222-2222-222222222222",
        filename="notes.txt",
        data=b"Airflow 3600 CFM\nVelocity 8 m/s",
        mime_type="text/plain",
    )
    result = service.extract(attachment)
    assert client.db["automation_attachments"][0]["storage_provider"] == "supabase_storage"
    assert client.db["automation_attachments"][0]["extraction_status"] == "extracted"
    assert len(client.db["automation_document_chunks"]) == len(result.chunks)


def test_storage_key_is_tenant_scoped():
    client = FakeClient()
    service = IngestionService(store=SupabaseAttachmentStore(client))
    attachment = service.register(
        tenant_id="tenant-a",
        job_id="job-1",
        filename="spec.pdf",
        data=b"data",
        mime_type="application/pdf",
    )
    assert attachment.storage_key.startswith("tenant-a/job-1/")
