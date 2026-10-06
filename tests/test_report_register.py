import io
import json

from api.app import APIApp
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore
from reports.register import filter_rows, register_row, view_counts, rows_from_artifacts


def _app():
    return APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())


def _call(app, method, path, body=None, query=""):
    raw = json.dumps(body or {}).encode()
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query, "CONTENT_LENGTH": str(len(raw)),
           "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": "tenant-a", "HTTP_X_USER_ID": "u1"}
    out = {}
    data = b"".join(app(env, lambda s, h: out.update(status=s)))
    return out["status"], json.loads(data.decode() or "{}")


VFD = {"source": "t", "requested_skill_id": "vfd_energy_savings",
       "inputs": {"motor_kw": 75, "annual_hours": 6000, "tariff_per_kwh": 8.5, "speed_reduction_pct": 15, "static_head_fraction": 25}}


def _make_job(app, approve=False):
    _, job = _call(app, "POST", "/v1/jobs", VFD)
    jid = job["job_id"]
    _call(app, "POST", f"/v1/jobs/{jid}/enqueue")
    _call(app, "POST", f"/v1/jobs/{jid}/process")
    if approve:
        _call(app, "POST", f"/v1/jobs/{jid}/approve", {"reviewer": "Jane Reviewer", "comment": "ok"})
    return jid


def test_register_lists_reports_and_views():
    app = _app()
    pending = _make_job(app)
    approved = _make_job(app, approve=True)
    status, body = _call(app, "GET", "/v1/reports")
    assert status.startswith("200")
    ids = {r["job_id"] for r in body["reports"]}
    assert {pending, approved} <= ids
    assert body["views"]["all"] == 2 and body["views"]["pending_review"] == 1 and body["views"]["approved"] == 1
    row = next(r for r in body["reports"] if r["job_id"] == approved)
    assert row["reviewed_by"] == "Jane Reviewer" and row["approved_at"] and row["skill_id"] == "vfd_energy_savings"
    assert row["revision"] == 1 and row["report_id"]

    _, only = _call(app, "GET", "/v1/reports", query="view=pending_review")
    assert [r["job_id"] for r in only["reports"]] == [pending]
    _, found = _call(app, "GET", "/v1/reports", query="q=jane")
    assert [r["job_id"] for r in found["reports"]] == [approved]
    _, none = _call(app, "GET", "/v1/reports", query="skill=duct_sizing")
    assert none["total"] == 0


def test_register_rejects_unknown_view():
    status, body = _call(_app(), "GET", "/v1/reports", query="view=nonsense")
    assert status.startswith("400") and "views" in body


def test_audit_trail_endpoint_lists_events():
    app = _app()
    jid = _make_job(app, approve=True)
    status, body = _call(app, "GET", f"/v1/jobs/{jid}/audit")
    assert status.startswith("200") and body["job_id"] == jid
    statuses = [e["status"] for e in body["events"]]
    assert "received" in statuses and "human_review" in statuses and "approved" in statuses
    assert _call(app, "GET", "/v1/jobs/does-not-exist/audit")[0].startswith("404")


def test_register_row_merges_artifact_and_job():
    artifact = {"report_id": "r1", "job_id": "j1", "version": 2, "status": "approved", "title": "T", "skill_id": "duct_sizing",
                "reviewer": "a@b.com", "created_at": "2026-10-02T06:00:00+00:00", "approved_at": "2026-10-02T07:00:00+00:00",
                "pdf_storage_path": "p/x.pdf", "pdf_sha256": "aa", "xlsx_storage_path": None, "drawing_artifact_id": "d1", "drawing_status": "dispatched", "drawing_manifest_sha256": "mm", "drawing_pdf_sha256": "dp", "drawing_dxf_zip_sha256": "dx", "drawing_pdf_storage_path": "draw.pdf", "drawing_dxf_zip_storage_path": "draw.zip"}
    row = register_row(artifact, {"status": "completed", "source": "dashboard", "request": "Size a duct"})
    assert row["revision"] == 2 and row["status"] == "completed" and row["request"] == "Size a duct"
    assert row["pdf_available"] is True and row["xlsx_available"] is False


def test_filters_and_counts():
    rows = rows_from_artifacts(
        [{"report_id": "r1", "job_id": "j1", "created_at": "2026-10-01", "skill_id": "pump_head"},
         {"report_id": "r2", "job_id": "j2", "created_at": "2026-10-02", "skill_id": "duct_sizing"}],
        {"j1": {"status": "human_review"}, "j2": {"status": "completed"}})
    assert [r["report_id"] for r in rows] == ["r2", "r1"]  # newest first
    counts = view_counts(rows)
    assert counts["all"] == 2 and counts["pending_review"] == 1 and counts["completed"] == 1
    assert [r["report_id"] for r in filter_rows(rows, view="completed")] == ["r2"]
    assert [r["report_id"] for r in filter_rows(rows, skill="pump_head")] == ["r1"]


class _Resp:
    def __init__(self, data): self.data = data


class _Q:
    def __init__(self, rows): self.rows = rows
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self): return _Resp(self.rows)


class _TableClient:
    def __init__(self, tables): self.tables = tables
    def table(self, name): return _Q(self.tables[name])


def test_supabase_store_register_merges_artifacts_with_jobs():
    from jobs.supabase_store import SupabaseJobStore
    store = SupabaseJobStore.__new__(SupabaseJobStore)
    store.jobs_table = "automation_jobs"
    store.client = _TableClient({
        "engineering_report_artifacts": [
            {"report_id": "r1", "job_id": "j1", "version": 1, "status": "approved", "skill_id": "vfd_energy_savings",
             "reviewer": "jane@example.com", "created_at": "2026-10-02T06:00:00+00:00", "approved_at": "2026-10-02T06:10:00+00:00",
             "pdf_storage_path": "t/j1/v1/r.pdf", "pdf_sha256": "aa", "xlsx_storage_path": "t/j1/v1/e.xlsx"}],
        "engineering_drawing_artifacts": [{"drawing_artifact_id": "d1", "job_id": "j1", "report_id": "r1", "report_revision": 1, "status": "dispatched", "manifest_sha256": "mm", "pdf_sha256": "dp", "pdf_storage_path": "t/j1/v1/d.pdf", "dxf_zip_sha256": "dx", "dxf_zip_storage_path": "t/j1/v1/d.zip"}],
        "automation_jobs": [{"job_id": "j1", "status": "completed", "source": "dashboard", "skill_id": "vfd_energy_savings",
                             "requested_skill_id": "vfd_energy_savings", "created_at": "2026-10-02T05:59:00+00:00",
                             "request": "Calculate VFD savings"}],
    })
    rows = store.list_report_register(tenant_id="t")
    assert len(rows) == 1
    r = rows[0]
    assert r["status"] == "completed" and r["reviewed_by"] == "jane@example.com" and r["pdf_available"] and r["xlsx_available"]
    assert r["request"] == "Calculate VFD savings"
    assert r["drawing_status"] == "dispatched" and r["drawing_manifest_sha256"] == "mm"
    assert r["drawing_pdf_available"] and r["drawing_dxf_available"]
