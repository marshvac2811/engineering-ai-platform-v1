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


def test_pump_request_with_static_elevation_and_missing_material_uses_governed_assumption():
    text = (
        "Calculate the total dynamic head required for a water circulation pump. "
        "Design flow: 18 m3/h. Total pipe length: 180 m. Pipe diameter: 80 mm. "
        "Fittings: 12 x 90 degree elbows, 4 x tees, 6 x isolation valves, and 2 x check valves. "
        "Static elevation: 12 m. Pump efficiency: 70%. Water supply temperature: 7 C and return temperature: 12 C. "
        "Pipe material is not available from the client. Use the platform's governed preliminary assumption "
        "for a permissible minor missing input, disclose the assumption, perform the calculation, and route the result for human review."
    )
    plan = build_plan(text)
    assert plan.selected_skill_id == "pump_head"
    assert plan.extracted_inputs["flow_m3hr"] == 18
    assert plan.extracted_inputs["diameter_mm"] == 80
    assert plan.extracted_inputs["straight_length_m"] == 180
    assert plan.extracted_inputs["static_head_m"] == 12
    assert plan.extracted_inputs["material"] == "ms_cs"
    assert plan.status == "ready_for_execution"
    assert not any("static head" in q.lower() for q in plan.questions)
    assert any("assumption" in r.lower() for r in plan.rationale)
