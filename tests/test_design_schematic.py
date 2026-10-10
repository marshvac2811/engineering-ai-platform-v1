import io

import ezdxf
import pytest

from engineering.drawing.design_schematic import build_design_schematic_dxf
from skills.hvac.design_package import design_package

ROOMS = [{"room_id": "R1", "name": "Open office", "area_m2": 120, "occupancy": 20},
         {"room_id": "R2", "name": "Meeting room", "area_m2": 30},
         {"room_id": "R3", "name": "Server room", "area_m2": 15}]


def _result():
    return design_package(building_type="office", climate_zone="hot_dry", rooms=ROOMS, diversity_factor_pct=90)


def test_dxf_is_valid_and_carries_the_numbers():
    res = _result()
    data = build_design_schematic_dxf(res, reference="job-1", project="Test Project")
    doc = ezdxf.read(io.StringIO(data.decode("utf-8")))
    assert doc.header["$INSUNITS"] == 4
    msp = doc.modelspace()
    rooms = [e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "A-ROOM"]
    assert len(rooms) == 3
    circles = list(msp.query("CIRCLE"))
    assert len(circles) == 3
    diameters = sorted(round(c.dxf.radius * 2) for c in circles)
    assert diameters == sorted(r["duct_diameter_mm"] for r in res["room_schedule"])
    texts = " ".join(t.dxf.text for t in msp.query("TEXT"))
    for needle in ("Open office", "SCHEMATIC ONLY - NOT A FLOOR PLAN", "Test Project", "PRELIMINARY", "BLOCK LOAD", "CHILLED WATER"):
        assert needle in texts
    assert doc.audit().has_errors is False


def test_room_box_area_is_proportional_to_room_area():
    res = _result()
    doc = ezdxf.read(io.StringIO(build_design_schematic_dxf(res).decode()))
    areas = []
    for e in doc.modelspace().query("LWPOLYLINE"):
        if e.dxf.layer == "A-ROOM":
            pts = list(e.get_points("xy"))
            (x0, y0), (x1, _), (_, y2) = pts[0], pts[1], pts[2]
            areas.append(abs(x1 - x0) * abs(y2 - y0) / 1e6)
    # the 120 m2 room is drawn at about 120 m2 (small rooms are clamped to a minimum legible size)
    assert any(a == pytest.approx(120, rel=0.01) for a in areas)


def test_deterministic_and_rejects_empty():
    res = _result()
    assert build_design_schematic_dxf(res, reference="x") == build_design_schematic_dxf(res, reference="x")
    with pytest.raises(ValueError):
        build_design_schematic_dxf({"room_schedule": []})


def test_api_design_dxf_after_dispatch_only():
    import base64, json
    from api.app import APIApp
    from crm.store import InMemoryCRMStore
    from integrations.service import InMemoryIntegrationStore
    from jobs.store import InMemoryJobStore
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())

    def call(method, path, body=None):
        raw = json.dumps(body or {}).encode()
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)),
               "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": "tenant-a"}
        out = {}
        data = b"".join(app(env, lambda s, h: out.update(status=s)))
        return out["status"], json.loads(data.decode() or "{}")

    inputs = {"building_type": "office", "climate_zone": "hot_dry", "rooms": ROOMS}
    s, j = call("POST", "/v1/intake", {"message": "Prepare the HVAC design package", "requested_skill_id": "hvac_design_package",
                                       "inputs": inputs, "project": "Acme Tower"})
    job_id = j["job"]["job_id"]
    s, e = call("GET", f"/v1/jobs/{job_id}/design-dxf")
    assert s.startswith("409"), (s, e)
    s, j = call("POST", f"/v1/jobs/{job_id}/approve", {"comment": "ok", "dispatch": True})
    assert s.startswith("200")
    s, d = call("GET", f"/v1/jobs/{job_id}/design-dxf")
    assert s.startswith("200"), (s, d)
    doc = ezdxf.read(io.StringIO(base64.b64decode(d["content_base64"]).decode()))
    assert "Acme Tower" in " ".join(t.dxf.text for t in doc.modelspace().query("TEXT"))
    assert d["filename"].endswith(".dxf") and len(d["sha256"]) == 64
