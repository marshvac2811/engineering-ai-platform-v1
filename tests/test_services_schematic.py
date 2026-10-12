import re

from engineering.drawing.services_schematic import build_fire_schematic_dxf, build_water_schematic_dxf
from skills.common import SkillRequest
from skills.calculators.catalogue import BY_ID, make_skill_class


def _texts(data: bytes) -> str:
    return data.decode("utf-8")


def _sprinkler():
    return make_skill_class(BY_ID["sprinkler_demand"])().run(SkillRequest(skill_id="sprinkler_demand", inputs={"hazard_class": "ordinary_1"})).to_dict()["engineering_result"]


def test_fire_schematic_uses_real_numbers_and_is_deterministic():
    res = _sprinkler()
    a = build_fire_schematic_dxf(res, reference="20261012010500001", project="Test")
    b = build_fire_schematic_dxf(res, reference="20261012010500001", project="Test")
    assert a == b
    text = _texts(a)
    assert "FIRE WATER TANK" in text and "1,794 L/min" in text and "107.6 m3" in text
    assert "SCHEMATIC ONLY" in text and "20261012010500001" in text
    assert "not determined here" in text


def test_water_schematic_from_tank_and_fixture_results():
    res = {"underground_tank_l": 4500.0, "overhead_tank_l": 1500.0, "daily_demand_l": 4500.0,
           "design_demand_lpm": 90.0, "design_demand_m3hr": 5.4,
           "fixture_rows": [{"fixture_type": "wc", "count": 10.0, "flow_lpm": 6.0}]}
    text = _texts(build_water_schematic_dxf(res, reference="R1"))
    assert "UNDERGROUND TANK" in text and "4,500 L" in text and "1,500 L" in text and "5.40 m3/h" in text
    assert "wc x10" in text


def test_builders_refuse_empty_results():
    import pytest
    with pytest.raises(ValueError):
        build_fire_schematic_dxf({})
    with pytest.raises(ValueError):
        build_water_schematic_dxf({})


def test_dispatched_sprinkler_job_serves_fire_dxf_through_api():
    import base64
    import io
    import json
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
        data = b"".join(app(env, lambda st, h: out.update(status=st)))
        return out["status"], json.loads(data.decode() or "{}")

    s, j = call("POST", "/v1/intake", {"message": "Sprinkler demand for an ordinary hazard group 1 building", "requested_skill_id": "sprinkler_demand", "inputs": {"hazard_class": "ordinary_1"}})
    assert s.startswith("201") and j["job"]["status"] == "human_review", j
    job_id = j["job"]["job_id"]
    s, j = call("POST", f"/v1/jobs/{job_id}/approve", {"comment": "ok", "dispatch": True})
    assert s.startswith("200"), j
    s, out = call("GET", f"/v1/jobs/{job_id}/design-dxf")
    assert s.startswith("200"), out
    assert out["filename"].startswith("fire-water-schematic-")
    assert b"FIRE WATER TANK" in base64.b64decode(out["content_base64"])
