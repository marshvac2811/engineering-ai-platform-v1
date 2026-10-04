from orchestrator.intake import build_plan


def test_build_plan_does_not_route_material_quantity_requests_to_a_recipe_library():
    plan = build_plan("Please prepare 1000 sqft gypsum partition with material quantities")
    assert plan.selected_skill_id is None
    assert plan.status == "awaiting_information"
    assert "quantity_takeoff" not in [c.skill_id for c in plan.candidates]
    assert plan.engineering_plan["status"] == "capability_required"


def test_build_plan_identifies_new_vertical_without_fabricating_calculation():
    plan = build_plan("We need a life safety audit for a 12 floor hotel")
    assert plan.selected_skill_id is None
    assert plan.status == "awaiting_information"
    assert plan.engineering_plan["status"] == "capability_required"
    assert plan.scope_analysis["status"] == "ai_interpretation_pending"



def test_extractor_maps_static_elevation_to_static_head():
    from orchestrator.extraction import extract_facts

    result = extract_facts("Calculate pump head. Static elevation: 12 m.")

    assert result.values["static_head_m"] == 12
