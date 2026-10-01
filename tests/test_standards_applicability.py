from knowledge.applicability import build_applicability_context, infer_domains
from knowledge.standards_catalog import candidate_sources


def test_india_hvac_discovers_sources_without_claiming_compliance():
    ctx = build_applicability_context(
        jurisdiction="IN",
        skill_id="duct_sizing",
        disciplines=["HVAC"],
        objective="size an HVAC duct",
    )
    assert "hvac" in ctx["domains"]
    assert ctx["candidate_sources"]
    assert ctx["compliance_claim_allowed"] is False
    assert ctx["status"] == "candidates_available"


def test_verified_source_and_applicability_open_compliance_gate():
    ctx = build_applicability_context(
        jurisdiction="IN",
        skill_id="energy_audit",
        disciplines=["energy"],
        supplied={
            "legal_applicability_established": True,
            "verified_sources": [{
                "source_id": "bee_ecbc",
                "verified": True,
            }],
        },
    )
    assert ctx["compliance_claim_allowed"] is True


def test_unknown_domain_requires_source():
    ctx = build_applicability_context(
        jurisdiction="IN",
        skill_id="specialized_unknown_capability",
        disciplines=["quantum_fluidics"],
    )
    assert ctx["status"] == "source_required"
    assert ctx["compliance_claim_allowed"] is False
