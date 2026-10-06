from engineering.building.interpreter import interpret_building_source


def test_text_interpretation_keeps_only_explicit_room_area_facts():
    result = interpret_building_source(
        source_type="pdf",
        text="Room: Office | Area: 24 m2\nRoom: AHU Room | Area: 8 m2",
        metadata={"pages": 1, "pages_with_text": 1},
        attachment_id="a1",
        filename="plan.pdf",
    )
    assert result["status"] == "partial"
    assert [x["name"] for x in result["facts"]["rooms"]] == ["Office", "AHU Room"]
    assert [x["area_m2"] for x in result["facts"]["rooms"]] == [24.0, 8.0]
    assert result["human_review_required"] is True


def test_dxf_interpretation_does_not_claim_architectural_semantics():
    result = interpret_building_source(
        source_type="dxf",
        metadata={"supported_line_geometry_count": 1},
        line_geometry=[{"start": {"x_mm": 0, "y_mm": 0}, "end": {"x_mm": 1000, "y_mm": 0}, "layer": "WALL"}],
    )
    assert result["facts"]["supported_line_geometry_count"] == 1
    assert result["semantic_interpretation"] is False
    assert any("semantics" in w for w in result["warnings"])


def test_scanned_pdf_is_blocked_without_ocr():
    result = interpret_building_source(
        source_type="pdf",
        text="",
        metadata={"pages": 2, "pages_with_text": 0},
    )
    assert result["status"] == "blocked"
    assert any("OCR" in b for b in result["blockers"])
