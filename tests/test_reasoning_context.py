from knowledge.reasoning_context import build_reasoning_context

def test_reasoning_context_separates_evidence_and_preserves_claim_gate():
    result = build_reasoning_context({
        "verified_evidence": [
            {"evidence_id": "project:a1:c1", "source_type": "project_document", "excerpt": "Design flow 25 m3/hr", "verified": True},
            {"evidence_id": "gov:1", "source_type": "governance_reference", "reference": "BEE/ECBC", "verified": True, "applicability": "confirmed"},
        ],
        "candidate_sources": [{"reference": "BIS NBC 2016", "verification_required": True}],
        "applicability": {"status": "verified_source_available"},
        "claim_gate": {"compliance_claim_allowed": True, "required_evidence_ids": ["gov:1"]},
    })
    assert result["project_evidence"][0]["evidence_id"] == "project:a1:c1"
    assert result["governance_evidence"][0]["evidence_id"] == "gov:1"
    assert result["candidate_sources"][0]["verification_required"] is True
    assert result["claim_gate"]["compliance_claim_allowed"] is True
    assert any("candidate source" in x.lower() for x in result["instructions"])