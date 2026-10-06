import io
import json
import zipfile

from engineering.drawing.dispatch import build_drawing_dispatch_package, build_drawing_dxf, build_drawing_pdf


def _drawing():
    return {
        "drawing_id": "HVAC-F1-001",
        "title": "Preliminary HVAC Layout",
        "discipline": "HVAC",
        "floor_id": "F1",
        "revision": "1",
        "objects": [
            {"object_id": "D1", "kind": "SUPPLY_AIR", "x_mm": 100, "y_mm": 120, "attributes": {}},
        ],
        "annotations": [{"text": "PRELIMINARY", "x_mm": 100, "y_mm": 150}],
    }


def test_dxf_is_deterministic_and_ascii():
    payload = _drawing()
    first = build_drawing_dxf(payload)
    second = build_drawing_dxf(payload)
    assert first == second
    assert b"SECTION" in first and b"ENTITIES" in first and first.endswith(b"0\nEOF\n")


def test_pdf_contains_controlled_drawing_content():
    manifest = {"package_type": "preliminary_engineering_drawing_package"}
    data = build_drawing_pdf(manifest=manifest, drawings=[_drawing()])
    assert data.startswith(b"%PDF")
    assert len(data) > 1000


def test_dispatch_package_contains_pdf_dxf_and_manifest():
    manifest = {"package_type": "preliminary_engineering_drawing_package", "manifest_sha256": "abc"}
    result = build_drawing_dispatch_package(manifest=manifest, drawings=[_drawing()])
    assert result["pdf"]["sha256"]
    assert result["dxf_zip"]["sha256"]
    with zipfile.ZipFile(io.BytesIO(result["dxf_zip"]["bytes"])) as z:
        names = set(z.namelist())
    assert {"drawing-package.pdf", "HVAC-F1-001.dxf", "manifest.json"} <= names
