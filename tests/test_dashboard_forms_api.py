"""The dashboard BOQ and energy forms post exactly these payloads; confirm they run intake -> review -> approve -> dispatch."""
import io
import json

import pytest

from api.app import APIApp
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore

BOQ = {"boq_csv": "item_no,description,unit,quantity\n1,Gypsum partition,sqm,100\n2,Chiller,nos,1"}
ENERGY = {"annual_consumption_kwh": 600000, "tariff_per_kwh": 8.5, "measures": [
    {"name": "Pump VFD", "type": "vfd", "investment": 250000, "motor_kw": 30, "speed_reduction_pct": 20, "static_head_fraction": 20, "annual_hours": 4000},
    {"name": "Solar", "type": "solar", "investment": 4500000, "annual_om": 40000, "capacity_kwp": 100}]}


@pytest.mark.parametrize("skill,inputs,message", [
    ("boq_takeoff", BOQ, "Prepare the preliminary BOQ material takeoff"),
    ("energy_optimisation_study", ENERGY, "Prepare the preliminary energy optimisation study for 2 measure(s)"),
])
def test_form_payload_runs_end_to_end(skill, inputs, message):
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())

    def call(path, body):
        raw = json.dumps(body).encode()
        env = {"REQUEST_METHOD": "POST", "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)),
               "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": "tenant-a"}
        out = {}
        data = b"".join(app(env, lambda s, h: out.update(status=s)))
        return out["status"], json.loads(data.decode() or "{}")

    s, j = call("/v1/intake", {"message": message, "requested_skill_id": skill, "inputs": inputs})
    assert s.startswith("201") and j["job"]["status"] == "human_review", j
    s, j = call(f"/v1/jobs/{j['job']['job_id']}/approve", {"comment": "ok", "dispatch": True})
    assert s.startswith("200") and j["status"] in ("dispatched", "completed"), j
