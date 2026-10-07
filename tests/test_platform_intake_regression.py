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
