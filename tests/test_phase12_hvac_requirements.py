from pathlib import Path
from code_engine.registry import CodeRegistry
from code_engine.universal import evaluate_registered_requirements, compliance_gate

ROOT = Path(__file__).resolve().parents[1]


def registry():
    return CodeRegistry.from_yaml(ROOT / 'standards' / 'registry.yaml')


def test_water_cooled_chiller_cop_is_clause_backed():
    r = registry()
    context = {
        'building_type': 'commercial',
        'ecbc_level': 'ECBC',
        'chiller_type': 'water_cooled',
        'chiller_capacity_band': '530_to_lt_1050',
    }
    rows = evaluate_registered_requirements(
        r, discipline='hvac', parameter='chiller_cop', input_value=5.6, context=context
    )
    assert rows[0]['status'] == 'PASS'
    assert rows[0]['required_value'] == 5.4
    assert '5.2.2.1 / Table 5-1' in rows[0]['clause_reference']


def test_water_cooled_chiller_cop_failure_is_clause_backed():
    r = registry()
    context = {
        'building_type': 'commercial',
        'ecbc_level': 'ECBC',
        'chiller_type': 'water_cooled',
        'chiller_capacity_band': 'lt_260',
    }
    rows = evaluate_registered_requirements(
        r, discipline='hvac', parameter='chiller_cop', input_value=4.2, context=context
    )
    assert rows[0]['status'] == 'FAIL'
    assert compliance_gate(rows) == 'NON_COMPLIANT'


def test_hvac_requirement_is_not_selected_without_ecbc_applicability_context():
    r = registry()
    rows = evaluate_registered_requirements(
        r, discipline='hvac', parameter='chiller_cop', input_value=5.0,
        context={'building_type': 'commercial', 'chiller_type': 'water_cooled', 'chiller_capacity_band': 'lt_260'}
    )
    assert rows == []
    assert compliance_gate(rows) == 'NO_GOVERNED_REQUIREMENT'
