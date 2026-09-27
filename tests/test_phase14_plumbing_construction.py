from engineering.standards.phase14_plumbing_construction import phase14_requirements

def test_phase14_has_plumbing_and_construction_scope():
    rows = phase14_requirements()
    disciplines = {r["discipline"] for r in rows}
    assert {"plumbing", "structural", "construction"} <= disciplines

def test_phase14_is_scope_only_not_false_compliance():
    assert all(r["type"] == "scope_reference" for r in phase14_requirements())
