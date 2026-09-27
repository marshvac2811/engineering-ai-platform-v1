from pathlib import Path
from code_engine.registry import CodeRegistry
from code_engine.universal import (
    requirement_applicable,
    find_applicable_requirements,
    evaluate_registered_requirements,
    compliance_gate,
)

ROOT = Path(__file__).resolve().parents[1]


def registry():
    return CodeRegistry.from_yaml(ROOT / 'standards' / 'registry.yaml')


def test_registry_requirement_is_selected_only_when_context_matches():
    r = registry()
    req = r.get_requirement('ecbc2017_vertical_fenestration_u_factor')
    assert requirement_applicable(req, {'building_type':'commercial','component':'vertical_fenestration'})
    assert not requirement_applicable(req, {'building_type':'residential','component':'vertical_fenestration'})
    rows = find_applicable_requirements(r, discipline='facade', parameter='u_factor', context={'building_type':'commercial','component':'vertical_fenestration'})
    assert [x.requirement_id for x in rows] == ['ecbc2017_vertical_fenestration_u_factor']


def test_universal_executor_produces_clause_backed_pass_and_fail():
    r = registry()
    context = {'building_type':'commercial','component':'vertical_fenestration'}
    passed = evaluate_registered_requirements(r, discipline='facade', parameter='u_factor', input_value=2.72, context=context)
    failed = evaluate_registered_requirements(r, discipline='facade', parameter='u_factor', input_value=3.20, context=context)
    assert passed[0]['status'] == 'PASS'
    assert failed[0]['status'] == 'FAIL'
    assert '4.3.3 / Table 4-10' in passed[0]['clause_reference']
    assert compliance_gate(passed) == 'COMPLIANT'
    assert compliance_gate(failed) == 'NON_COMPLIANT'


def test_universal_executor_does_not_invent_requirement_for_uncovered_parameter():
    r = registry()
    rows = evaluate_registered_requirements(r, discipline='pump', parameter='head_m', input_value=42, context={'building_type':'commercial'})
    assert rows == []
    assert compliance_gate(rows) == 'NO_GOVERNED_REQUIREMENT'
