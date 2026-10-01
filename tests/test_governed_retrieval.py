from knowledge.governed_retrieval import retrieve_governed_knowledge


def test_project_evidence_is_traceable_and_compliance_remains_gated():
    ctx = {"documents": [{"attachment_id": "a1", "filename": "hvac.txt", "sha256": "abc", "source_type": "client_document", "chunks": [{"chunk_id": "c1", "chunk_index": 0, "text": "Hospital HVAC duct ventilation design", "metadata": {}}]}]}
    result = retrieve_governed_knowledge(query="hospital HVAC duct ventilation", project_context=ctx, jurisdiction="IN", skill_id="duct_sizing", disciplines=["HVAC"])
    assert result["candidate_sources"]
    assert result["verified_evidence"]
    assert result["verified_evidence"][0]["evidence_id"] == "project:a1:c1"
    assert result["claim_gate"]["compliance_claim_allowed"] is False


def test_verified_governance_source_can_open_gate_when_applicability_is_established():
    result = retrieve_governed_knowledge(query="energy audit", jurisdiction="IN", skill_id="energy_audit", disciplines=["energy"], standards_context={"legal_applicability_established": True, "verified_sources": [{"reference": "BEE/ECBC", "verified": True, "applicability": "confirmed"}]})
    assert result["claim_gate"]["compliance_claim_allowed"] is True
    assert result["claim_gate"]["required_evidence_ids"]
