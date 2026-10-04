"""The hvac_fault_diagnosis skill's registered contract is rule_id + structured values,
not free text, so these tests lock in that realistic symptom sentences route to the
right skill, match the right rule, and extract values under the exact key names the
skill's rule engine (skills/hvac/fault_diagnosis/source_calculator.py RULES) expects.
"""
from orchestrator.intake import build_plan
from skills.hvac.fault_diagnosis import source_calculator as engine


CASES = [
    ("Chiller discharge pressure is 12 bar against a high pressure limit of 10 bar, "
     "and condenser water entering temperature is 35°C. What's wrong?",
     "chl_hp_trip", {"discharge_pressure": 12.0, "hp_limit": 10.0, "cw_entering_temp": 35.0}),
    ("Chiller is tripping on low pressure: suction pressure low, evaporator pressure low, "
     "high superheat observed.",
     "chl_lp_trip", {"suction_pressure_low": "yes", "evap_pressure_low": "yes", "superheat_high": "yes"}),
    ("AHU filter differential pressure is 350 Pa against a threshold of 250 Pa, fan speed is normal.",
     "ahu_dirty_filter", {"filter_dp": 350.0, "filter_dp_threshold": 250.0, "fan_speed_normal": "yes"}),
    ("Water leak sensor is on in the AHU and drain differential pressure is high.",
     "ahu_water_leak", {"leak_sensor_on": "yes", "drain_dp_high": "yes"}),
    ("A pump will not start even though the start command is given and breaker is on, no current is drawn.",
     "pump_motor_fault", {"start_command": "yes", "breaker_on": "yes", "no_current": "yes"}),
    ("Pump flow is normal but differential pressure across the pump is low.",
     "pump_bypass_open", {"flow_normal": "yes", "dp_low": "yes"}),
    ("Pump is vibrating heavily and making noise, suction pressure is low.",
     "pump_cavitation", {"high_vibration": "yes", "noise": "yes", "low_suction_pressure": "yes"}),
]


def test_symptom_sentences_route_directly_to_fault_diagnosis_ready_for_execution():
    for text, rule_id, values in CASES:
        plan = build_plan(text)
        assert plan.selected_skill_id == "hvac_fault_diagnosis", text
        assert plan.status == "ready_for_execution", (text, plan.missing_inputs)
        assert plan.extracted_inputs["rule_id"] == rule_id, text
        assert plan.extracted_inputs["values"] == values, text


def test_extracted_values_satisfy_the_skills_actual_rule_engine():
    # Guards against a key-name mismatch between the translator and RULES (e.g. the
    # earlier "high_superheat" vs "superheat_high" bug) ever silently reappearing: if the
    # keys didn't match, every boolean condition would read as unmet instead of erroring.
    for _text, rule_id, values in CASES:
        result = engine.evaluate_rule(rule_id, values)
        assert result["all_conditions_met"] is True, (rule_id, result)
        assert result["conclusion"] == engine.RULES[rule_id]["conclusion"]


def test_vague_symptom_with_no_matching_rule_asks_for_rule_id_and_values_explicitly():
    plan = build_plan("Chiller supply chilled water temperature is reading 9.5°C against a "
                       "setpoint of 6.5°C. Diagnose the likely fault.")
    assert plan.selected_skill_id == "hvac_fault_diagnosis"
    assert plan.status == "awaiting_information"
    assert set(plan.missing_inputs) == {"rule_id", "values"}


def test_partial_symptom_asks_only_for_the_specific_missing_reading():
    plan = build_plan("AHU filter differential pressure is 350 Pa, fan speed is normal.")
    assert plan.selected_skill_id == "hvac_fault_diagnosis"
    assert plan.status == "awaiting_information"
    # filter_dp_threshold wasn't mentioned. The structured missing-inputs list stays the
    # generic ["values"] (that's the skill's actual contract field), but the question
    # text shown to the person must name the specific reading, not just "values".
    assert plan.missing_inputs == ["values"]
    assert any("filter dp threshold" in q.lower() for q in plan.questions), plan.questions
