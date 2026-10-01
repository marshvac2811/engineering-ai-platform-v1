from jobs.models import JobStatus
from jobs.service import JobService
from jobs.store import InMemoryJobStore
from orchestrator.intake import build_plan
from reports.service import ReportService
from reports.store import InMemoryReportStore

TENANT = "tenant-a"


def test_ready_pump_job_generates_report_with_skill_profile_and_trace():
    job_store = InMemoryJobStore()
    report_service = ReportService(InMemoryReportStore(), tenant_id=TENANT)
    service = JobService(job_store, tenant_id=TENANT, report_service=report_service)
    plan = build_plan(
        "Calculate pump head for 20 m3/hr, 80 mm pipe, roughness 0.045 mm, "
        "60 m straight length, 8 m static head and 10% margin"
    )
    job = service.create_job(
        tenant_id=TENANT, source="test", requested_skill_id="pump_head",
        inputs=plan.extracted_inputs, project_context=plan.project_context,
        standards_context=plan.standards_context, assumptions_context=plan.assumptions_context,
        orchestration=plan.to_dict(),
    )
    service.enqueue(job.job_id)
    processed = service.process(job.job_id)
    report = report_service.get(processed.result["report_id"], include_content=True)
    assert processed.status == JobStatus.HUMAN_REVIEW
    assert report.report["work_items"][0]["skill_id"] == "pump_head"
    assert report.report["work_items"][0]["result"]["engineering_result"]["calculation_trace"]
    assert report.report["report_type"] == "pump_head_calculation"
    assert "unsupported_scope" in report.report
    assert report.report["human_review"]["required"] is True


def test_compound_plan_keeps_supported_items_and_marks_unsupported_scope():
    plan = build_plan(
        "Calculate pump head for 20 m3/hr and size BMS controllers for 2 AHUs; "
        "also design structural glazing for 150 km/h wind"
    )
    assert {item.skill_id for item in plan.work_items} == {"pump_head", "bms_controller_sizing"}
    assert plan.unsupported_scope == ["design structural glazing for 150 km/h wind"]
