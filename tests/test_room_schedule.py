import pytest

from engineering.building.schedule import extract_dxf_candidate_rooms, extract_room_schedule


def test_text_formats_and_unit_conversion():
    text = """Room: Open office | Area: 120 m2 | Occupancy: 20
Room: Server room, area 15 sqm
R3  Conference  250 sqft  10 persons
Total  385 sqm
Room: Store | note only"""
    r = extract_room_schedule(text)
    by = {x["name"]: x for x in r["rooms"]}
    assert by["Open office"]["area_m2"] == 120 and by["Open office"]["occupancy"] == 20
    assert by["Server room"]["area_m2"] == 15
    assert by["Conference"]["area_m2"] == pytest.approx(250 * 0.09290304, abs=0.01) and by["Conference"]["occupancy"] == 10
    assert "Total" not in by and len(r["rooms"]) == 3
    assert any("Store" in s for s in r["skipped"])


def _dxf(units, polys, texts):
    out = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", str(units), "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for pts in polys:
        out += ["0", "LWPOLYLINE", "8", "ROOMS", "90", str(len(pts)), "70", "1"]
        for x, y in pts:
            out += ["10", str(x), "20", str(y)]
    for t, x, y in texts:
        out += ["0", "TEXT", "8", "LABEL", "10", str(x), "20", str(y), "1", t]
    out += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(out).encode()


def test_dxf_closed_polyline_with_one_label_is_candidate_room_in_mm():
    sq = [(0, 0), (5000, 0), (5000, 4000), (0, 4000)]           # 5 m x 4 m = 20 m2
    other = [(6000, 0), (9000, 0), (9000, 3000), (6000, 3000)]   # no label
    r = extract_dxf_candidate_rooms(_dxf(4, [sq, other], [("MEETING", 2500, 2000)]))
    assert r["rooms"] == [{"name": "MEETING", "area_m2": 20.0, "inferred": True, "review_required": True,
                           "basis": r["rooms"][0]["basis"]}]
    assert any("no text label" in w for w in r["warnings"])


def test_dxf_without_units_produces_nothing():
    sq = [(0, 0), (5, 0), (5, 4), (0, 4)]
    r = extract_dxf_candidate_rooms(_dxf(0, [sq], [("A", 2, 2)]))
    assert r["rooms"] == [] and any("units" in w.lower() for w in r["warnings"])


def test_dxf_two_labels_in_one_polyline_is_ambiguous():
    sq = [(0, 0), (5000, 0), (5000, 4000), (0, 4000)]
    r = extract_dxf_candidate_rooms(_dxf(4, [sq], [("A", 1000, 1000), ("B", 3000, 3000)]))
    assert r["rooms"] == [] and any("more than one" in w for w in r["warnings"])


def test_design_package_accepts_pasted_room_schedule_through_intake():
    import io, json
    from api.app import APIApp
    from crm.store import InMemoryCRMStore
    from integrations.service import InMemoryIntegrationStore
    from jobs.store import InMemoryJobStore
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    raw = json.dumps({"message": "Prepare the HVAC design package", "requested_skill_id": "hvac_design_package",
                      "inputs": {"building_type": "office", "climate_zone": "hot_dry",
                                 "rooms_text": "Room: Open office | Area: 120 m2 | Occupancy: 20\nRoom: Meeting | Area: 30 m2"}}).encode()
    env = {"REQUEST_METHOD": "POST", "PATH_INFO": "/v1/intake", "CONTENT_LENGTH": str(len(raw)),
           "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": "tenant-a"}
    out = {}
    j = json.loads(b"".join(app(env, lambda s, h: out.update(status=s))).decode())
    assert out["status"].startswith("201") and j["job"]["status"] == "human_review", j


def test_interpreter_returns_design_rooms_and_flags_dxf_candidates():
    from engineering.building.interpreter import interpret_building_source
    t = interpret_building_source(source_type="pdf", text="Room: Lobby | Area: 40 m2 | Occupancy: 8", filename="a.pdf")
    assert t["design_rooms"] == [{"room_id": "R1", "name": "Lobby", "area_m2": 40.0, "occupancy": 8}]
    assert t["design_rooms_need_confirmation"] is False
    d = interpret_building_source(source_type="dxf", line_geometry=[{"x": 1}], candidate_rooms=[{"name": "MEETING", "area_m2": 20.0, "basis": "b"}])
    assert d["design_rooms_need_confirmation"] is True and d["design_rooms"][0]["name"] == "MEETING"
