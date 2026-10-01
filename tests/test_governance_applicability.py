from governance.engine import build_governance_context


def test_governance_exposes_candidate_sources_without_false_compliance():
    ctx = build_governance_context(
        skill_id="duct_sizing",
        project_context={"jurisdiction": "IN"},
        standards_context={"disciplines": ["HVAC"]},
        methodology={"objective": "size an HVAC duct"},
    )
    ids = {x["source_id"] for x in ctx["candidate_sources"]}
    assert "ashrae_standards" in ids
    assert "ishrae_standards" in ids
    assert "bis_nbc_2016" in ids
    assert ctx["applicability"]["compliance_claim_allowed"] is False
