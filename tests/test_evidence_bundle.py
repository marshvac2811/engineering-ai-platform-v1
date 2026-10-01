from types import SimpleNamespace

from reports.evidence import build_evidence_bundle


def test_evidence_bundle_captures_task_outputs_and_hashes():
    job = SimpleNamespace(
        job_id="job-1",
        tenant_id="tenant-1",
        status=SimpleNamespace(value="human_review"),
        requested_skill_id="hvac_decarbonisation",
        source="dashboard",
        inputs={"annual_energy_kwh": 100000},
        project_context={"documents": [{"filename": "bill.csv"}]},
        standards_context={"standards": ["ASHRAE"]},
        assumptions_context={"grid_factor": 0.716},
        orchestration={"engineering_plan": {"tasks": [{"task_id": "task-1"}]}},
        attachments=[{
            "attachment_id": "att-1",
            "filename": "bill.csv",
            "mime_type": "text/csv",
            "sha256": "abc",
            "extraction_status": "completed",
            "extraction_warnings": [],
        }],
        events=[],
    )
    workflow = {
        "status": "completed",
        "blockers": [],
        "engineering_plan": {"tasks": [{"task_id": "task-1"}]},
        "engineering_results": [{
            "task_id": "task-1",
            "capability_id": "hvac_decarbonisation",
            "status": "completed",
            "objective": "Assess savings",
            "inputs": {"annual_energy_kwh": 100000},
            "engineering_result": {
                "annual_saving_kwh": 8000,
                "calculation_trace": ["baseline * efficiency_gain"],
                "assumptions": ["constant tariff"],
                "warnings": [],
            },
        }],
    }
    consolidated = {
        "status": "completed",
        "qa": {"status": "ready_for_human_review"},
        "governance": {"standards": ["ASHRAE"]},
    }

    bundle = build_evidence_bundle(job=job, workflow=workflow, consolidated=consolidated)

    assert bundle["manifest"]["schema_version"] == "engineering-evidence-v1"
    assert bundle["manifest"]["task_count"] == 1
    assert bundle["manifest"]["input_hash"]
    assert bundle["manifest"]["bundle_sha256"]
    assert bundle["manifest"]["source_evidence"][0]["sha256"] == "abc"
    assert bundle["tasks"][0]["engineering_result"]["annual_saving_kwh"] == 8000
    assert bundle["tasks"][0]["calculation_trace"] == ["baseline * efficiency_gain"]
