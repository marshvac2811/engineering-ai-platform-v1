from jobs.supabase_store import SupabaseJobStore
from jobs.store import InMemoryJobStore
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from api.app import APIApp
import io, json


class _Resp:
    def __init__(self, data): self.data = data


class _Query:
    def __init__(self, rows): self.rows = rows
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self): return _Resp(self.rows)


class _Bucket:
    def create_signed_url(self, path, expires_in, options=None):
        return {"signedURL": f"https://files.example/{path}?dl={(options or {}).get('download')}", "signedUrl": None}


class _Storage:
    def from_(self, bucket): return _Bucket()


class _Client:
    def __init__(self, rows):
        self.rows = rows
        self.storage = _Storage()
    def table(self, name): return _Query(self.rows)


def _store(rows):
    store = SupabaseJobStore.__new__(SupabaseJobStore)
    store.client = _Client(rows)
    return store


ROW = {
    "job_id": "j1", "tenant_id": "t1", "version": 1,
    "pdf_storage_path": "t1/j1/v1/report.pdf", "pdf_filename": "report.pdf", "pdf_sha256": "aa",
    "xlsx_storage_path": "t1/j1/v1/evidence.xlsx", "xlsx_filename": "evidence.xlsx", "xlsx_sha256": "bb",
}


def test_download_link_for_pdf_and_xlsx():
    store = _store([ROW])
    pdf = store.get_artifact_download("j1", "pdf", tenant_id="t1")
    xlsx = store.get_artifact_download("j1", "xlsx", tenant_id="t1")
    assert pdf["filename"] == "report.pdf" and pdf["sha256"] == "aa"
    assert "t1/j1/v1/report.pdf" in pdf["url"] and "dl=report.pdf" in pdf["url"]
    assert xlsx["filename"] == "evidence.xlsx" and xlsx["sha256"] == "bb"


def test_download_link_missing_before_dispatch():
    assert _store([]).get_artifact_download("j1", "pdf", tenant_id="t1") is None
    row = dict(ROW, pdf_storage_path="")
    assert _store([row]).get_artifact_download("j1", "pdf", tenant_id="t1") is None


def test_download_link_rejects_unknown_kind():
    import pytest
    with pytest.raises(ValueError):
        _store([ROW]).get_artifact_download("j1", "exe", tenant_id="t1")


def _call(app, method, path, tenant="tenant-a"):
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": "2",
           "wsgi.input": io.BytesIO(b"{}"), "HTTP_X_TENANT_ID": tenant}
    out = {}
    body = b"".join(app(env, lambda s, h: out.update(status=s)))
    return out["status"], json.loads(body.decode())


def test_artifact_route_returns_helpful_404_when_not_generated():
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    payload = {"source": "t", "requested_skill_id": "duct_sizing", "inputs": {"airflow": 3600, "method": "velocity",
               "duct_type": "round", "target_velocity_ms": 8, "material": "gss"}}
    raw = json.dumps(payload).encode()
    env = {"REQUEST_METHOD": "POST", "PATH_INFO": "/v1/jobs", "CONTENT_LENGTH": str(len(raw)),
           "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": "tenant-a"}
    out = {}
    job = json.loads(b"".join(app(env, lambda s, h: out.update(status=s))).decode())
    status, body = _call(app, "GET", f"/v1/jobs/{job['job_id']}/artifacts/pdf")
    assert status.startswith("404") and "dispatch" in body["error"].lower()
    status, body = _call(app, "GET", f"/v1/jobs/{job['job_id']}/artifacts/exe")
    assert status.startswith("404")
