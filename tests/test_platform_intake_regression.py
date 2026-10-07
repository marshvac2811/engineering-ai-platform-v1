from orchestrator.intake import RuleBasedIntentProvider
from orchestrator.semantic_inputs import normalize_engineering_inputs
from skills.hvac.chiller_selection.source_calculator import calc as chiller_calc


CHILLER_REQUEST = """
We are planning to replace the existing chilled-water plant of a commercial building.
The existing plant has a total cooling requirement of approximately 600 TR. We are
considering a new chiller plant and want an engineering recommendation covering
suitable chiller arrangement, approximate efficiency, number of duty modules,
redundancy requirement, annual energy consumption, annual electricity cost and key
selection considerations. Known information: required cooling capacity approximately
600 TR; expected operating hours 5,000 hours/year; average operating load 70%;
electricity tariff ₹9/kWh; modular equipment preferred; the plant is critical and
should continue operating if one chiller is unavailable.
"""


def test_chiller_request_extracts_stated_operating_facts():
    facts = normalize_engineering_inputs(CHILLER_REQUEST)
    assert facts["load_factor_pct"] == 70
    assert facts["tariff_per_kwh"] == 9
    assert facts["redundancy_level"] == "N+1"


def test_chiller_selection_has_priority_over_broad_energy_language():
    selected, candidates, confidence = RuleBasedIntentProvider().route(CHILLER_REQUEST)
    assert selected == "chiller_selection_advisor"
    assert confidence >= 0.99
    assert candidates[0].skill_id == "chiller_selection_advisor"


def test_chiller_module_count_is_not_invented_when_no_module_basis_exists():
    result = chiller_calc({
        "total_load_tr": 600,
        "efficiency_kw_per_tr": 0.62,
        "annual_hours": 5000,
        "load_factor_pct": 70,
        "tariff_per_kwh": 9,
        "redundancy_level": "N+1",
    })
    assert result["duty_modules"] is None
    assert result["module_configuration_status"] == "PENDING_MODULE_CAPACITY_BASIS"
    assert result["redundancy_level"] == "N+1"

VFD_ACCEPTANCE_REQUEST = """
We have a 30 kW chilled-water pump in a commercial building operating about 5,500 hours per year.
It currently runs at fixed speed. We are considering a VFD and expect the average speed to reduce by 15%.
Electricity tariff is ₹9/kWh. Please assess annual electrical energy saving, annual cost saving and simple
payback. VFD installation cost is ₹3,00,000.
"""


def test_vfd_request_wins_over_broad_energy_payback_language():
    selected, candidates, confidence = RuleBasedIntentProvider().route(VFD_ACCEPTANCE_REQUEST)
    assert selected == "vfd_energy_savings"
    assert confidence >= 0.99
    assert candidates[0].skill_id == "vfd_energy_savings"


def test_vfd_acceptance_request_asks_only_for_static_head_fraction():
    from orchestrator.intake import build_plan

    plan = build_plan(VFD_ACCEPTANCE_REQUEST)
    assert plan.selected_skill_id == "vfd_energy_savings"
    assert "motor_kw" not in plan.missing_inputs
    assert "annual_hours" not in plan.missing_inputs
    assert "speed_reduction_pct" not in plan.missing_inputs
    assert "tariff_per_kwh" not in plan.missing_inputs
    assert "static_head_fraction" in plan.missing_inputs

def test_specific_capabilities_beat_broad_energy_terms():
    cases = [
        (
            "Calculate pump head for 25 m3/hr flow, 80 mm pipe, 120 m length and 12 m static head with 10% margin.",
            "pump_head",
        ),
        (
            "Size a rectangular supply air duct for 5000 m3/h at 7 m/s.",
            "duct_sizing",
        ),
        (
            "Select a new chiller plant for 600 TR with 5000 hours, 70% load, ₹9/kWh and N+1 redundancy; recommend arrangement and annual energy cost.",
            "chiller_selection_advisor",
        ),
        (
            "Assess a 30 kW chilled-water pump VFD retrofit for annual energy saving, cost saving and payback.",
            "vfd_energy_savings",
        ),
    ]
    for request, expected in cases:
        selected, _candidates, confidence = RuleBasedIntentProvider().route(request)
        assert selected == expected
        assert confidence >= 0.99


def test_vfd_subcapabilities_route_by_explicit_objective():
    cases = [
        (
            "Screen a 75 kW VFD installation for harmonic distortion and IEEE 519 compliance risk.",
            "harmonic_screening",
        ),
        (
            "Check VFD derating for a drive at 2500 m altitude and 45 C ambient temperature.",
            "vfd_derating",
        ),
        (
            "Assess VFD energy saving for a pump with 15% speed reduction, annual energy cost saving and payback.",
            "vfd_energy_savings",
        ),
    ]
    for request, expected in cases:
        selected, _candidates, confidence = RuleBasedIntentProvider().route(request)
        assert selected == expected
        assert confidence >= 0.99


def test_explicit_specific_objectives_beat_broad_energy_language():
    cases = [
        (
            "Size a rectangular supply air duct for 5000 m3/h at 7 m/s and consider energy efficiency.",
            "duct_sizing",
        ),
        (
            "Calculate pump head for a chilled-water pump and assess the energy efficiency implications.",
            "pump_head",
        ),
        (
            "Perform cooling tower sizing and include an energy efficiency assessment.",
            "cooling_tower",
        ),
        (
            "Size the refrigerant pipework and consider energy efficiency.",
            "refrigerant_pipe_sizing",
        ),
        (
            "Do VRF sizing and assess energy efficiency.",
            "vrf_sizing",
        ),
        (
            "Calculate the facade U-factor and assess energy efficiency.",
            "facade_u_factor",
        ),
    ]
    for request, expected in cases:
        selected, _candidates, confidence = RuleBasedIntentProvider().route(request)
        assert selected == expected
        assert confidence >= 0.99
