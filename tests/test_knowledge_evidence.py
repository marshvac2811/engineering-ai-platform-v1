from knowledge.evidence import build_evidence_bundle, normalize_evidence


def test_unverified_reference_is_not_compliance_evidence():
    bundle = build_evidence_bundle(
        governance={"references": [{"authority": "ASHRAE", "reference": "source-id"}]}
    )
    assert bundle["counts"]["total"] == 1
    assert bundle["counts"]["verified"] == 0
    assert bundle["claim_gate"]["status"] == "evidence_required"


def test_verified_applicable_evidence_is_traceable():
    bundle = build_evidence_bundle(
        result_evidence=[{
            "source_type": "licensed_standard",
            "authority": "ASHRAE",
            "reference": "licensed-source-id",
            "location": "section 4.2",
            "content": "source excerpt",
            "verified": True,
            "applicability": "applicable",
        }]
    )
    record = bundle["records"][0]
    assert record["verified"] is True
    assert record["content_hash"]
    assert bundle["claim_gate"]["status"] == "evidence_available"


def test_malformed_evidence_is_ignored():
    records = normalize_evidence([None, 7, {"reference": "ok"}])
    assert len(records) == 1
    assert records[0]["reference"] == "ok"
