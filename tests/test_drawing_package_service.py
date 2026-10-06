from types import SimpleNamespace

import pytest

from engineering.building.ingest import ingest_structured_layout
from engineering.design.planner import plan_discipline_layout
from engineering.design.routing import route_calculation_outputs
from engineering.drawing.service import build_job_drawing_package, authorize_drawing_package_issue
from engineering.drawing.dispatch import build_drawing_dispatch_package


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


def test_fire_plumbing_calculation_outputs_flow_into_one_coordinated_package():
    building = _building()
    fire_route = route_calculation_outputs(
        building,
        discipline="FIRE",
        floor_id="F1",
        calculation_outputs=[{"room_id": "R1", "source_calculation": "fire-storage-task-1", "total_storage_m3": 132.0}],
    )
    plumbing_route = route_calculation_outputs(
        building,
        discipline="PLUMBING",
        floor_id="F1",
        calculation_outputs=[{"room_id": "R1", "source_calculation": "plumbing-demand-task-1", "design_demand_lpm": 20.0}],
    )
    assert fire_route["status"] == "ready"
    assert plumbing_route["status"] == "ready"
    fire = plan_discipline_layout(building, "FIRE", "F1", fire_route["room_inputs"])
    plumbing = plan_discipline_layout(building, "PLUMBING", "F1", plumbing_route["room_inputs"])
    job = SimpleNamespace(job_id="J-FP-1", tenant_id="T1", report_id="R-FP-1", result={"report_revision": 1})
    manifest = build_job_drawing_package(job, [fire, plumbing], source_hashes={"plan.pdf": "abc"})
    assert manifest["issue_status"] == "not_approved"
    assert manifest["dispatch_allowed"] is False
    assert set(manifest["drawings"][0]["source_calculations"] + manifest["drawings"][1]["source_calculations"]) == {"fire-storage-task-1", "plumbing-demand-task-1"}
    assert manifest["manifest_sha256"]


def test_controlled_drawing_dispatch_builds_watermarked_pdf_and_hashed_dxf_package():
    drawing = plan_discipline_layout(_building(), "FIRE", "F1", {
        "R1": {"total_storage_m3": 132.0, "source_calculation": "fire-storage-task-1"}
    })
    job = SimpleNamespace(job_id="J-DISPATCH-1", tenant_id="T1", report_id="R-DISPATCH-1", result={"report_revision": 1}, status=SimpleNamespace(value="approved"))
    manifest = build_job_drawing_package(job, [drawing], source_hashes={"plan.pdf": "abc"})
    issued = authorize_drawing_package_issue(manifest, job)
    built = build_drawing_dispatch_package(manifest=issued, drawings=issued["drawing_payloads"])
    assert built["pdf"]["bytes"].startswith(b"%PDF")
    assert b"PRELIMINARY" in built["pdf"]["bytes"]
    assert len(built["dxf_zip"]["bytes"]) > 100
    assert len(built["pdf"]["sha256"]) == 64
    assert len(built["dxf_zip"]["sha256"]) == 64
