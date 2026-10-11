from skill_framework.input_resolver import resolve_input_requirements
from skill_framework.registry import load_skill_registry
from governance.assumption_policy import resolve_input_assumptions

def test_pump_head_minor_missing_inputs_are_auto_assumed():
    registry = load_skill_registry("skill_registry/registry.yaml")
    definition = registry.get("pump_head")
    inputs = {
        "flow_m3hr": 25,
        "diameter_mm": 100,
        "straight_length_m": 50,
        "static_head_m": 20,
    }
    resolved, assumptions, blockers = resolve_input_assumptions("pump_head", inputs)
    assert not blockers
    assert resolved["material"] == "ms_cs"
    assert resolved["margin_pct"] == 10
    assert len(assumptions) == 2
    resolution = resolve_input_requirements(definition, resolved)
    assert resolution.missing_inputs == []

def test_auto_assumption_is_explicitly_marked_for_client_disclosure():
    resolved, assumptions, blockers = resolve_input_assumptions(
        "pump_head",
        {"flow_m3hr": 25, "diameter_mm": 100, "straight_length_m": 50, "static_head_m": 20},
    )
    assert not blockers
    assert all(a["status"] == "ASSUMED_DUE_TO_CLIENT_DATA_UNAVAILABLE" for a in assumptions)
    assert all(a["client_confirmation"] == "recommended" for a in assumptions)


def test_only_registered_minor_inputs_are_auto_assumed():
    # A genuinely required engineering input such as design flow must remain a blocker.
    inputs = {
        "diameter_mm": 100,
        "straight_length_m": 50,
        "static_head_m": 20,
    }
    resolved, assumptions, blockers = resolve_input_assumptions("pump_head", inputs)
    assert not blockers
    assert resolved["material"] == "ms_cs"
    assert resolved["margin_pct"] == 10
    assert "flow_m3hr" not in resolved
    assert len(assumptions) == 2


def test_unknown_skill_has_no_automatic_assumptions():
    resolved, assumptions, blockers = resolve_input_assumptions(
        "unknown_skill", {"flow_m3hr": 20}
    )
    assert resolved == {"flow_m3hr": 20}
    assert assumptions == []
    assert blockers == []


def test_layman_duct_request_proceeds_with_disclosed_assumptions():
    from orchestrator.intake import build_plan
    plan = build_plan("Please size a duct for 5000 CFM")
    assert plan.selected_skill_id == "duct_sizing"
    assert plan.status == "ready_for_execution"
    assert plan.extracted_inputs["method"] == "velocity"
    assert plan.extracted_inputs["target_velocity_ms"] == 7


def test_velocity_assumption_not_applied_for_equal_friction():
    resolved, applied, _ = resolve_input_assumptions(
        "duct_sizing", {"airflow": 5000, "method": "equal_friction", "duct_type": "round"})
    assert "target_velocity_ms" not in resolved
    assert applied == []


def test_airflow_is_never_assumed():
    resolved, _, _ = resolve_input_assumptions("duct_sizing", {})
    assert "airflow" not in resolved


def test_intake_assumptions_are_disclosed_in_result_and_pdf():
    import io
    from jobs.service import JobService
    from jobs.store import InMemoryJobStore
    from orchestrator.intake import build_plan
    st = InMemoryJobStore()
    svc = JobService(st, tenant_id="t")
    job = svc.create_from_plan(build_plan("Please size a duct for 5000 CFM"))
    params = {a.get("parameter"): a for a in job.result["assumptions"]}
    for name in ("method", "duct_type", "target_velocity_ms"):
        assert params[name]["status"] == "ASSUMED_DUE_TO_CLIENT_DATA_UNAVAILABLE"
    svc.approve(job.job_id, reviewer="x")
    svc.dispatch(job.job_id)
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(st.get_artifact_bytes(job.job_id, "pdf", tenant_id="t"))).pages)
    assert "ASSUMED_DUE_TO_CLIENT_DATA_UNAVAILABLE" in text


def test_tiny_constants_not_rounded_to_zero():
    from reports.formatting import format_value
    assert format_value(1.81e-05) == "1.81e-05"
