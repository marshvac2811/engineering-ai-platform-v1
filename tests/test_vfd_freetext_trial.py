"""Regression: a plain-language VFD request must extract all five inputs, route to
vfd_energy_savings, calculate, reach human review, then approve and dispatch."""
import pytest

from jobs.models import JobStatus
from jobs.service import JobService
from jobs.store import InMemoryJobStore
from orchestrator.intake import build_plan
from reports.service import ReportService
from reports.store import InMemoryReportStore

TENANT = "tenant-a"

PROMPTS = [
    "Calculate VFD energy savings and economic impact for a 75 kW motor operating for 6000 hours "
    "per year, with a 15% speed reduction and 25% static-head fraction. Use an electricity tariff "
    "of ₹8.50/kWh. Provide the calculated annual energy savings and cost savings.",
    "VFD energy savings: motor 75 kW, speed reduction 15%, static head fraction 25%, "
    "6,000 annual hours, tariff Rs 8.5/kWh",
]


@pytest.mark.parametrize("prompt", PROMPTS)
def test_freetext_vfd_request_extracts_all_inputs(prompt):
    plan = build_plan(prompt)
    assert plan.selected_skill_id == "vfd_energy_savings"
    assert plan.missing_inputs == []
    assert plan.status == "ready_for_execution"
    got = plan.extracted_inputs
    assert (got["motor_kw"], got["speed_reduction_pct"], got["static_head_fraction"],
            got["annual_hours"], got["tariff_per_kwh"]) == (75, 15, 25, 6000, 8.5)


def test_build_plan_never_raises_unbound_project_context():
    # Regression for UnboundLocalError on project_context in the intake path.
    for kwargs in ({}, {"project_context": None}, {"project_context": {"client": "X"}}):
        build_plan("Calculate pump head for 20 m3/hr", **kwargs)
    build_plan("Calculate pump head for 20 m3/hr and size BMS controllers for 2 AHUs; also design glazing")


def test_vfd_trial_runs_to_human_review_and_dispatch():
    report_service = ReportService(InMemoryReportStore(), tenant_id=TENANT)
    service = JobService(InMemoryJobStore(), tenant_id=TENANT, report_service=report_service)
    plan = build_plan(PROMPTS[0])
    job = service.create_job(
        tenant_id=TENANT, source="test", requested_skill_id="vfd_energy_savings",
        inputs=plan.extracted_inputs, project_context=plan.project_context,
        standards_context=plan.standards_context, assumptions_context=plan.assumptions_context,
        orchestration=plan.to_dict(),
    )
    service.enqueue(job.job_id)
    processed = service.process(job.job_id)
    assert processed.status == JobStatus.HUMAN_REVIEW
    item = report_service.get(processed.result["report_id"], include_content=True).report["work_items"][0]
    assert item["skill_id"] == "vfd_energy_savings"
    assert item["calculation_trace"]
    flat = str(item)
    assert "130233" in flat.replace(",", "").replace(".0", "") or "130,233" in flat
    approved = service.approve(job.job_id, "reviewer@example.com", "ok")
    assert approved.status in (JobStatus.APPROVED, JobStatus.DISPATCHED, JobStatus.COMPLETED)


def test_api_intake_to_dispatch_with_no_ai_provider(monkeypatch):
    """/v1/intake must work with no AI provider configured, then approve+dispatch must
    complete (regression: undefined provider/project_context and document_status)."""
    import io, json
    from api.app import APIApp
    from crm.store import InMemoryCRMStore
    from integrations.service import InMemoryIntegrationStore

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())

    def call(method, path, body=None):
        raw = json.dumps(body or {}).encode()
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)),
               "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": TENANT}
        out = {}
        data = b"".join(app(env, lambda s, h: out.update(status=s)))
        return out["status"], json.loads(data.decode() or "{}")

    status, body = call("POST", "/v1/intake", {"message": PROMPTS[0], "project": "P1", "client": "C1"})
    assert status.startswith("201"), body
    assert body["job"]["status"] == "human_review"
    jid = body["job"]["job_id"]
    status, job = call("POST", f"/v1/jobs/{jid}/approve", {"comment": "ok", "dispatch": True})
    assert status.startswith("200") and job["status"] in ("dispatched", "completed"), job.get("status")
