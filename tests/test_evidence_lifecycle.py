from types import SimpleNamespace

from reports.evidence import refresh_evidence_bundle


def test_refresh_evidence_bundle_captures_delivery_and_approval():
    job = SimpleNamespace(
        job_id="job-refresh-1",
        tenant_id="tenant-1",
        status=SimpleNamespace(value="approved"),
        requested_skill_id="hvac_decarbonisation",
        source="dashboard",
        inputs={"annual_energy_kwh": 100000},
        project_context={},
        standards_context={},
        assumptions_context={},
        orchestration={"engineering_plan": {"tasks": []}},
        attachments=[],
        events=[],
        dispatch_result={"artifacts": {"pdf": {"sha256": "pdf123"}}},
        result={
            "status": "completed",
            "engineering_result": {"task_results": []},
            "qa": {"status": "ready_for_human_review"},
            "governance": {},
        },
    )
    bundle = refresh_evidence_bundle(job=job)
    assert bundle["review"]["status"] == "approved"
    assert bundle["delivery"]["artifacts"]["pdf"]["sha256"] == "pdf123"
    assert bundle["manifest"]["bundle_sha256"]
