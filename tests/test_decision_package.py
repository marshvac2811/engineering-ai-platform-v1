from orchestrator.reasoning import build_decision_package

def test_decision_package_filters_unknown_evidence_and_claims():
    out = build_decision_package(
        {"objective": "Audit", "reasoning": {"basis": "supplied evidence"}, "evidence_usage": ["gov:1", "fake:2"], "missing_evidence": ["jurisdiction proof"], "compliance_claims": ["compliant"]},
        {"governed_knowledge": {"verified_evidence": [{"evidence_id": "gov:1"}], "claim_gate": {"compliance_claim_allowed": False}}},
    )
    assert out["evidence_used"] == ["gov:1"]
    assert out["compliance_claims"] == []
    assert out["status"] == "evidence_incomplete"
    assert out["human_review_required"] is True