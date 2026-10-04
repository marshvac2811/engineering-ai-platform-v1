from orchestrator.intake import build_plan


def test_attachment_values_are_used_before_missing_input_loop():
    plan = build_plan(
        "Calculate pump head from the supplied project data.",
        requested_skill_id="pump_head",
        project_context={
            "documents": [
                {
                    "filename": "pump-data.xlsx",
                    "extraction_status": "extracted",
                    "text": (
                        "Design water flow rate: 120 m3/hr\n"
                        "Pipe diameter: 200 mm\n"
                        "Straight pipe length: 80 m\n"
                        "Static head: 25 m\n"
                        "Design margin: 10 percent\n"
                        "Pipe material: GI"
                    ),
                    "chunks": [],
                }
            ]
        },
    )
    assert plan.extracted_inputs["flow_m3hr"] == 120.0
    assert plan.extracted_inputs["diameter_mm"] == 200.0
    assert plan.extracted_inputs["straight_length_m"] == 80.0
    assert plan.extracted_inputs["static_head_m"] == 25.0
    assert plan.extracted_inputs["margin_pct"] == 10.0
    assert plan.extracted_inputs["material"].lower() == "gi"
    assert plan.missing_inputs == []
    assert plan.status == "ready_for_execution"


def test_missing_input_question_contains_field_unit_and_reason():
    plan = build_plan(
        "Calculate pump head.",
        requested_skill_id="pump_head",
        provided_inputs={"flow_m3hr": 120},
    )
    questions = " ".join(plan.questions).lower()
    assert "diameter" in questions
    assert "mm" in questions
    assert "why:" in questions


def test_free_text_alone_resolves_inputs_without_attachment():
    plan = build_plan(
        "Calculate pump head. Design water flow rate is 120 m3/hr, pipe diameter is 200 mm, "
        "straight pipe length is 80 m, static head is 25 m, design margin is 10 percent, "
        "pipe material is GI.",
        requested_skill_id="pump_head",
    )
    assert plan.missing_inputs == []
    assert plan.status == "ready_for_execution"
    assert plan.extracted_inputs["flow_m3hr"] == 120.0
    assert plan.extracted_inputs["diameter_mm"] == 200.0


def test_free_text_and_attachment_can_be_combined():
    plan = build_plan(
        "Calculate pump head. Use a 120 m3/hr design flow.",
        requested_skill_id="pump_head",
        project_context={
            "documents": [{
                "filename": "layout.xlsx",
                "text": "Pipe diameter: 200 mm; straight pipe length: 80 m; static head: 25 m; design margin: 10 percent; pipe material: GI",
                "chunks": [],
            }]
        },
    )
    assert plan.missing_inputs == []
    assert plan.extracted_inputs["flow_m3hr"] == 120.0
    assert plan.extracted_inputs["diameter_mm"] == 200.0
