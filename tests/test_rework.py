import io
import json

from api.app import APIApp
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore
from reports.register import VIEWS, rows_from_artifacts

VFD = {"motor_kw": 75, "annual_hours": 6000, "tariff_per_kwh": 8.5, "speed_reduction_pct": 15, "static_head_fraction": 25}


def _app():
    return APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())


def _call(app, method, path, body=None):
    raw = json.dumps(body or {}).encode()
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)),
           "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": "tenant-a"}
    out = {}
    data = b"".join(app(env, lambda s, h: out.update(status=s)))
    return out["status"], json.loads(data.decode() or "{}")


def _savings(job):
    return job["result"]["engineering_result"]["results"][0]["engineering_result"]["annual_savings_kwh_corrected"]


def _job_in_review(app):
    _, job = _call(app, "POST", "/v1/jobs", {"source": "t", "requested_skill_id": "vfd_energy_savings", "inputs": dict(VFD)})
    jid = job["job_id"]
    _call(app, "POST", f"/v1/jobs/{jid}/enqueue")
    status, job = _call(app, "POST", f"/v1/jobs/{jid}/process")
    assert job["status"] == "human_review", job
    return jid, job


def test_rework_requires_a_comment_and_human_review():
    app = _app()
    jid, _ = _job_in_review(app)
    status, body = _call(app, "POST", f"/v1/jobs/{jid}/rework", {"comment": ""})
    assert status.startswith("400") and "comment" in body["error"].lower()
    status, job = _call(app, "POST", f"/v1/jobs/{jid}/rework", {"comment": "Tariff looks wrong, please verify"})
    assert status.startswith("200") and job["status"] == "rework"
    # cannot request rework twice, and cannot approve a job that is in rework
    status, _ = _call(app, "POST", f"/v1/jobs/{jid}/rework", {"comment": "again again"})
    assert status.startswith("400")
    status, _ = _call(app, "POST", f"/v1/jobs/{jid}/approve", {})
    assert status.startswith("400")


def test_resubmit_reruns_with_corrected_inputs_and_returns_to_review():
    app = _app()
    jid, first = _job_in_review(app)
    first_savings = _savings(first)
    _call(app, "POST", f"/v1/jobs/{jid}/rework", {"comment": "Motor rating should be 90 kW"})
    status, job = _call(app, "POST", f"/v1/jobs/{jid}/resubmit", {"inputs": {"motor_kw": "90"}, "note": "Nameplate corrected"})
    assert status.startswith("200"), job
    assert job["status"] == "human_review"
    assert job["inputs"]["motor_kw"] == 90
    assert _savings(job) > first_savings
    types = [e["event_type"] for e in job["events"]]
    assert "rework_resubmitted" in types
    assert any(e["status"] == "rework" for e in job["events"])  # history of the rework request is kept


def test_resubmit_needs_a_change_or_note_and_only_from_rework():
    app = _app()
    jid, _ = _job_in_review(app)
    status, _ = _call(app, "POST", f"/v1/jobs/{jid}/resubmit", {"inputs": {"motor_kw": 80}})
    assert status.startswith("400")  # not in rework
    _call(app, "POST", f"/v1/jobs/{jid}/rework", {"comment": "Please recheck inputs"})
    status, body = _call(app, "POST", f"/v1/jobs/{jid}/resubmit", {})
    assert status.startswith("400") and "change" in body["error"].lower()


def test_rework_jobs_appear_in_failed_rework_view_and_old_revisions_marked_superseded():
    assert "rework" in VIEWS["failed"]
    arts = [
        {"report_id": "r1", "job_id": "j1", "version": 1, "status": "draft", "created_at": "2026-10-02T01:00:00Z"},
        {"report_id": "r2", "job_id": "j1", "version": 2, "status": "approved", "created_at": "2026-10-02T02:00:00Z"},
        {"report_id": "r3", "job_id": "j2", "version": 1, "status": "draft", "created_at": "2026-10-02T03:00:00Z"},
    ]
    rows = {r["report_id"]: r for r in rows_from_artifacts(arts, {})}
    assert rows["r1"]["superseded"] is True
    assert rows["r2"]["superseded"] is False
    assert rows["r3"]["superseded"] is False


def test_approve_and_dispatch_in_one_call_for_reviewer_with_dispatch_rights():
    app = _app()
    jid, _ = _job_in_review(app)
    status, job = _call(app, "POST", f"/v1/jobs/{jid}/approve", {"comment": "ok", "dispatch": True})
    assert status.startswith("200"), job
    assert job["status"] in ("dispatched", "completed"), job["status"]


def test_approve_without_dispatch_flag_still_just_approves():
    app = _app()
    jid, _ = _job_in_review(app)
    status, job = _call(app, "POST", f"/v1/jobs/{jid}/approve", {"comment": "ok"})
    assert status.startswith("200") and job["status"] == "approved"
