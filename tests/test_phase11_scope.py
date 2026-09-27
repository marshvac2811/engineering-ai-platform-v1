from code_engine.scope import audit_scope_coverage, scope_references_for_skill

EXECUTABLE_SKILLS = [
    "preliminary_load_estimation", "duct_sizing", "pump_head", "hvac_fault_diagnosis",
    "cooling_tower", "refrigerant_pipe_sizing", "vrf_sizing", "cleanroom_ach",
    "duct_leakage", "chiller_selection_advisor", "bms_points_generation",
    "bms_controller_sizing", "bms_cost_estimation", "bms_alarm_evaluation",
    "vfd_energy_savings", "vfd_derating", "harmonic_screening", "hvac_decarbonisation",
    "energy_payback", "hvac_boq", "deviation_statement", "facade_u_factor",
]


def test_all_executable_skills_have_governed_scope_references():
    audit = audit_scope_coverage(EXECUTABLE_SKILLS)
    assert audit["coverage_complete"] is True
    assert audit["uncovered"] == []


def test_facade_scope_includes_nbc_glass_glazing_and_ecbc_envelope():
    refs = scope_references_for_skill("facade_u_factor")
    pairs = {(r["standard_id"], r["reference"]) for r in refs}
    assert ("bis_nbc_2016", "Part 6, Section 8") in pairs
    assert ("bee_ecbc_2017", "ECBC 2017 - Building Envelope") in pairs


def test_scope_reference_is_not_a_compliance_requirement():
    ref = scope_references_for_skill("duct_sizing")[0]
    assert ref["reference_type"] == "SCOPE_REFERENCE"
    assert "required_value" not in ref
