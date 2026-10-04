from skills.common import SkillRequest
from skills.hvac.pump_head.adapter import PumpHeadSkill
from orchestrator.engine import execute


def test_pump_head_source_equation_example():
    req = SkillRequest(
        skill_id="pump_head",
        inputs={
            "flow_m3hr": 20,
            "diameter_mm": 80,
            "material": "upvc_pvc",
            "straight_length_m": 60,
            "fittings":[{"name":"90° standard elbow","ld_ratio":30,"quantity":2}],
            "static_head_m": 8,
            "equipment_losses_m":[{"name":"AHU/FCU coil","loss_m":2}],
            "margin_pct": 10,
        },
    )
    result = PumpHeadSkill().run(req)
    assert result.status == "draft_ready"
    assert result.engineering_result["velocity_ms"] > 0
    assert result.engineering_result["total_dynamic_head_m"] > 10


def test_orchestrator_dispatches_pump_head():
    req = SkillRequest(
        skill_id="pump_head",
        inputs={
            "flow_m3hr": 20,
            "diameter_mm": 80,
            "roughness_mm": 0.0015,
            "straight_length_m": 10,
            "static_head_m": 0,
            "margin_pct": 0,
        },
    )
    result = execute(req)
    assert result.status == "draft_ready"
    assert result.skill_id == "pump_head"



def test_pump_head_intake_surfaces_either_or_inputs():
    from orchestrator.intake import build_plan

    plan = build_plan(
        "Calculate pump head for a water circulation system with 120 m pipe length, 25 mm pipe diameter, 20 m static head, 4 m/s flow velocity, and 6 fittings."
    )
    assert plan.status == "awaiting_information"
    assert "flow_m3hr" in plan.missing_inputs
    assert "margin_pct" not in plan.missing_inputs
    assert "roughness_mm" not in plan.missing_inputs
    assert "material" not in plan.missing_inputs
    assert len(plan.questions) == 1


def test_successful_retry_clears_stale_errors():
    from jobs import InMemoryJobStore, JobService, JobStatus

    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    job = service.create_job(
        tenant_id="test-tenant", source="test", requested_skill_id="pump_head",
        inputs={"flow_m3hr": 20, "diameter_mm": 80, "straight_length_m": 10, "static_head_m": 0, "margin_pct": 0},
    )
    service.enqueue(job.job_id)
    job = service.process(job.job_id)
    assert job.status == JobStatus.HUMAN_REVIEW
    assert job.errors == []
    assert job.orchestration.get("status") == "ready_for_execution"
