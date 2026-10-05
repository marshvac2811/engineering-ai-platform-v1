from engineering.building.dxf import extract_lines, supported_geometry_report

def test_ascii_dxf_line_geometry_is_deterministic():
    raw=b"0\\nSECTION\\n2\\nENTITIES\\n0\\nLINE\\n8\\nA-WALL\\n10\\n0\\n20\\n0\\n11\\n1000\\n21\\n0\\n0\\nENDSEC\\n0\\nEOF\\n"
    lines=extract_lines(raw); assert len(lines)==1; assert lines[0].start.x==0; assert lines[0].end.x==1000; assert lines[0].layer=="A-WALL"

def test_dxf_geometry_does_not_claim_architectural_semantics():
    raw=b"0\\nLINE\\n10\\n0\\n20\\n0\\n11\\n100\\n21\\n0\\n"
    report=supported_geometry_report(raw); assert report["semantic_interpretation"] is False; assert report["human_review_required"] is True

def test_binary_or_invalid_dxf_fails_explicitly():
    try: extract_lines(b"\\xff\\xfe")
    except UnicodeDecodeError: return
    assert False, "invalid DXF should fail rather than fabricate geometry"
