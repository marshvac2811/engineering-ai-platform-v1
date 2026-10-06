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



def test_natural_language_hvac_plant_energy_request_routes_without_skill_id():
    text = (
        "Assess an existing 250 TR HVAC plant for energy savings and optimisation. "
        "Identify efficiency improvement opportunities, asset-life impact and a practical "
        "decarbonisation roadmap using the available plant data."
    )
    plan = build_plan(text)
    assert plan.selected_skill_id == "hvac_decarbonisation"
    assert plan.status == "awaiting_information"
    assert plan.engineering_plan["status"] in {"awaiting_information", "ready_for_execution"}
    assert any("hvac" in q.lower() or "energy" in q.lower() for q in plan.questions)


def test_energy_payback_request_stays_on_payback_capability_when_explicit():
    plan = build_plan(
        "Evaluate the retrofit economics and payback of replacing an existing HVAC plant."
    )
    assert plan.selected_skill_id == "energy_payback"


def test_broad_hvac_energy_audit_request_routes_to_hvac_decarbonisation():
    plan = build_plan(
        "Audit this hospital for energy savings, assess HVAC optimization, rooftop solar "
        "and BESS options, and prepare a decarbonization roadmap using applicable standards."
    )
    assert plan.selected_skill_id == "hvac_decarbonisation"
    assert plan.status in {"awaiting_information", "ready_for_execution"}
