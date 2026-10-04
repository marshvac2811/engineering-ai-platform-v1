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


def test_universal_semantic_normalizer_accepts_common_engineering_synonyms_and_units():
    text = (
        "Water circulation flow is 5 L/s; pipe dia is 80 mm; "
        "pipeline length is 590.55 ft; static elevation is 39.37 ft; "
        "design allowance is 10 percent."
    )
    facts = extract_facts(text)
    assert facts["flow_m3hr"] == 18
    assert facts["diameter_mm"] == 80
    assert round(facts["straight_length_m"], 2) == 180
    assert round(facts["static_head_m"], 2) == 12
    assert facts["margin_pct"] == 10


def test_universal_semantic_normalizer_supports_other_registered_domains():
    facts = extract_facts(
        "Motor rating is 15 kW, ambient temp is 45 C and site altitude is 1200 m."
    )
    assert facts["motor_kw"] == 15
    assert facts["ambient_temp_c"] == 45
    assert facts["altitude_m"] == 1200


def test_universal_semantic_normalizer_does_not_treat_plain_elevation_as_pump_head():
    facts = extract_facts("Site elevation above sea level is 1200 m.")
    assert "altitude_m" in facts
    assert "static_head_m" not in facts


def test_pump_language_does_not_misclassify_efficiency_temperature_or_static_elevation():
    from orchestrator.intake import extract_facts

    text = (
        "Pump head: static elevation 12 m. Pump efficiency 70%. "
        "Water supply temperature 7 C and return temperature 12 C."
    )
    result = extract_facts(text)
    assert result["static_head_m"] == 12
    assert "altitude_m" not in result
    assert "efficiency_kw_per_tr" not in result
    assert "ambient_temp_c" not in result
