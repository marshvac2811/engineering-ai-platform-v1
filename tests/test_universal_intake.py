from orchestrator.intake import build_plan


def test_build_plan_routes_recipe_request_to_generic_quantity_takeoff():
    plan = build_plan("Please prepare 1000 sqft gypsum partition with material quantities")
    assert plan.selected_skill_id == "quantity_takeoff"
    assert plan.status == "ready_for_execution"
    assert plan.extracted_inputs["request_text"].startswith("Please prepare")
    assert plan.scope_analysis["recipe_count"] == 1


def test_build_plan_identifies_new_vertical_without_fabricating_calculation():
    plan = build_plan("We need a life safety audit for a 12 floor hotel")
    assert plan.selected_skill_id is None
    assert plan.status == "awaiting_information"
    assert plan.scope_analysis["verticals"][0]["id"] == "lsg_audit"
