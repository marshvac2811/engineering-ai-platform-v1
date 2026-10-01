from orchestrator.intake import build_plan

def test_unknown_engineering_request_is_not_converted_to_recipe_takeoff():
    plan = build_plan("Audit the fire pump room and identify life-safety deficiencies from the attached inspection notes.")
    assert plan.selected_skill_id is None
    assert plan.status == "awaiting_information"
    assert "quantity_takeoff" not in [c.skill_id for c in plan.candidates]
    assert plan.request_understanding == {}

def test_known_request_keeps_ai_governance_contract():
    plan = build_plan("Calculate pump head. Flow 25 m3/hr, diameter 80 mm, length 120 m, static head 12 m, margin 10%, roughness 0.15 mm.")
    assert plan.selected_skill_id == "pump_head"
    assert plan.standards_context["status"] == "governance_required"
    assert plan.standards_context["skill_id"] == "pump_head"
