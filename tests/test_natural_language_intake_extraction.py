from orchestrator.intake import build_plan, extract_facts


def test_extract_facts_accepts_natural_engineering_phrasing():
    text = (
        "Calculate the pump head required for a chilled-water circulation system. "
        "Design water flow is 25 m³/hr. Pipe internal diameter is 80 mm. "
        "Total straight pipe length is 120 m. Static/elevation head is 12 m. "
        "Use 10% design margin. Pipe material is GI steel."
    )
    facts = extract_facts(text)
    assert facts["flow_m3hr"] == 25
    assert facts["diameter_mm"] == 80
    assert facts["straight_length_m"] == 120
    assert facts["static_head_m"] == 12
    assert facts["margin_pct"] == 10
    assert facts["material"] == "gi"


def test_pump_head_natural_language_request_is_ready():
    text = (
        "Calculate pump head for chilled-water circulation. "
        "Design water flow is 25 m³/hr, pipe internal diameter is 80 mm, "
        "total straight pipe length is 120 m, static/elevation head is 12 m, "
        "use 10% design margin, pipe material is GI steel."
    )
    plan = build_plan(text)
    assert plan.selected_skill_id == "pump_head"
    assert plan.status == "ready_for_execution"
    assert plan.missing_inputs == []
    assert plan.extracted_inputs["flow_m3hr"] == 25
    assert plan.extracted_inputs["diameter_mm"] == 80
    assert plan.extracted_inputs["straight_length_m"] == 120
    assert plan.extracted_inputs["static_head_m"] == 12
    assert plan.extracted_inputs["margin_pct"] == 10
    assert plan.extracted_inputs["material"] == "gi"
