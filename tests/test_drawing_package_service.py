from types import SimpleNamespace

import pytest

from engineering.building.ingest import ingest_structured_layout
from engineering.design.planner import plan_discipline_layout
from engineering.drawing.service import build_job_drawing_package, authorize_drawing_package_issue


def _building():
    return ingest_structured_layout({
        "building_id": "B1",
        "name": "Test Building",
        "sources": [{"source_id": "plan.pdf", "page": 1, "location": "A1"}],
        "floors": [{"floor_id": "F1", "name": "Ground", "rooms": [
            {"room_id": "R1", "name": "Office", "area_m2": 20, "x_mm": 100, "y_mm": 200}
        ]}],
    })


def test_drawing_package_links_job_and_remains_unissued():
    drawing = plan_discipline_layout(_building(), "HVAC", "F1", {
        "R1": {"airflow_m3h": 500, "source_calculation": "task-1"}
    })
    job = SimpleNamespace(job_id="J1", tenant_id="T1", report_id="R1", result={"report_revision": 2})
    manifest = build_job_drawing_package(job, [drawing], source_hashes={"plan.pdf": "abc"})
    assert manifest["job_id"] == "J1"
    assert manifest["report_revision"] == 2
    assert manifest["issue_status"] == "not_approved"
    assert manifest["dispatch_allowed"] is False
    assert manifest["drawings"][0]["source_calculations"] == ["task-1"]
    assert manifest["drawing_artifact_id"]
    assert manifest["manifest_sha256"]
    assert manifest["drawing_payloads"][0]["drawing_id"] == "HVAC-F1-001"


def test_drawing_package_issue_requires_approved_job():
    drawing = plan_discipline_layout(_building(), "HVAC", "F1", {"R1": {"airflow_m3h": 500}})
    job = SimpleNamespace(job_id="J1", tenant_id="T1", report_id=None, result={},
                          status=SimpleNamespace(value="human_review"))
    manifest = build_job_drawing_package(job, [drawing])
    with pytest.raises(ValueError, match="approved engineering job"):
        authorize_drawing_package_issue(manifest, job)


def test_drawing_package_issue_is_explicitly_controlled():
    drawing = plan_discipline_layout(_building(), "HVAC", "F1", {"R1": {"airflow_m3h": 500}})
    job = SimpleNamespace(job_id="J1", tenant_id="T1", report_id=None, result={},
                          status=SimpleNamespace(value="approved"))
    manifest = build_job_drawing_package(job, [drawing])
    issued = authorize_drawing_package_issue(manifest, job)
    assert issued["dispatch_allowed"] is True
    assert issued["issue_status"] == "approved_for_controlled_dispatch"
