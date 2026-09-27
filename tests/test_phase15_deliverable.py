from reports.upwork_deliverable import build_deliverable, render_markdown

def test_deliverable_preserves_traceability():
    d = build_deliverable(
        title="Facade U-Factor Calculation",
        client_request="Calculate the facade U-factor.",
        result={"status": "COMPLETED", "u_factor": 2.4, "unit": "W/m2.K"},
        standards=[{"code": "ECBC 2017", "clause": "§4.3.3 / Table 4-10"}],
        compliance=[{"status": "PASS", "required": 3.0, "actual": 2.4}],
        evidence=[{"source_type": "calculation", "reference": "trace-001"}],
        assumptions=["Preliminary area-weighted calculation."],
        limitations=["Not a certified NFRC/ISO product rating."],
        deliverables=["PDF engineering report"],
    )
    md = render_markdown(d)
    assert "ECBC 2017" in md
    assert "§4.3.3 / Table 4-10" in md
    assert "trace-001" in md
    assert "Not a certified NFRC/ISO product rating." in md
    assert d.sha256()

def test_empty_compliance_does_not_claim_compliance():
    d = build_deliverable(
        title="Test", client_request="Test", result={"status": "COMPLETED"}
    )
    md = render_markdown(d)
    assert "No governed compliance result supplied." in md
