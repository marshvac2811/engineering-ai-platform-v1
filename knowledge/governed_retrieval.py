from knowledge.applicability import build_applicability_context
from knowledge.evidence import normalize_evidence
from knowledge.retrieval import retrieve_relevant_chunks


def retrieve_governed_knowledge(*, query, project_context=None, jurisdiction=None, skill_id=None, disciplines=None, objective="", standards_context=None, max_chunks=12):
    project_context = dict(project_context or {})
    standards_context = dict(standards_context or {})
    applicability = build_applicability_context(
        jurisdiction=jurisdiction or project_context.get("jurisdiction"),
        skill_id=skill_id, disciplines=disciplines, objective=objective or query,
        supplied=standards_context,
    )
    chunks = retrieve_relevant_chunks(query, project_context, max_chunks=max_chunks)
    evidence = []
    for item in chunks:
        evidence.append({
            "evidence_id": f"project:{item.get('attachment_id')}:{item.get('chunk_id')}",
            "source_type": "project_document", "verified": True,
            "applicability": "project_context", "reference": item.get("filename"),
            "location": item.get("chunk_id"), "content_hash": item.get("sha256"),
            "excerpt": item.get("text"),
            "metadata": {"retrieval_method": item.get("retrieval_method"), "score": item.get("score")},
        })
    for item in normalize_evidence(standards_context.get("verified_sources"), default_source_type="verified_governance_source"):
        item = dict(item)
        item["evidence_id"] = item.get("reference") or item.get("content_hash")
        evidence.append(item)
    return {
        "query": query,
        "applicability": applicability,
        "candidate_sources": applicability["candidate_sources"],
        "verified_evidence": evidence,
        "claim_gate": {
            "status": "verified_evidence_available" if evidence and applicability["compliance_claim_allowed"] else "evidence_or_applicability_required",
            "compliance_claim_allowed": applicability["compliance_claim_allowed"],
            "required_evidence_ids": [x["evidence_id"] for x in evidence if x.get("verified")],
        },
        "retrieval": {"method": "project_document_lexical_v1", "returned_chunks": len(chunks)},
    }
