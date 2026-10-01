def test_result_suppresses_ungated_compliance_claims():
    from orchestrator.result import build_workflow_result
    result = build_workflow_result(
        workflow={"status": "completed", "engineering_plan": {"tasks": []}},
        request_understanding={"compliance_claims": ["compliant with code"], "evidence_usage": ["gov:1"]},
        governance={"governed_knowledge": {"claim_gate": {"compliance_claim_allowed": False}}},
        inputs={}, assumptions={},
    )
    assert result["ai_reasoning"]["compliance_claims"] == []