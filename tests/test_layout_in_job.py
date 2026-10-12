import base64, io, json
from api.app import APIApp
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore
from engineering.plan.samples import office_plan_dxf


def _app():
    return APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())


def _call(app, method, path, body=None):
    raw = json.dumps(body or {}).encode()
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": "t"}
    out = {}
    data = b"".join(app(env, lambda s, h: out.update(status=s)))
    return out["status"], json.loads(data.decode() or "{}")


def test_plan_attached_to_job_gives_layout_after_dispatch():
    app = _app()
    att = {"filename": "plan.dxf", "content_base64": base64.b64encode(office_plan_dxf(units="mm")).decode()}
    s, j = _call(app, "POST", "/v1/intake", {"message": "Design HVAC for a 120 m2 open office and a 30 m2 meeting room in Delhi.", "attachments": [att]})
    assert s.startswith("201"), j
    jid = j["job"]["job_id"]
    s, _ = _call(app, "GET", f"/v1/jobs/{jid}/layout-dxf")
    assert s.startswith("409")
    s, j2 = _call(app, "POST", f"/v1/jobs/{jid}/approve", {"comment": "ok", "dispatch": True})
    assert s.startswith("200"), j2
    s, lay = _call(app, "GET", f"/v1/jobs/{jid}/layout-dxf")
    assert s.startswith("200"), lay
    assert lay["plan_file"] == "plan.dxf" and lay["summary"]["diffusers"] > 0 and lay["summary"]["sprinklers"] == 0
    assert base64.b64decode(lay["content_base64"])


def test_job_without_plan_has_no_layout():
    app = _app()
    s, j = _call(app, "POST", "/v1/intake", {"message": "Design HVAC for a 120 m2 open office in Delhi."})
    jid = j["job"]["job_id"]
    _call(app, "POST", f"/v1/jobs/{jid}/approve", {"comment": "ok", "dispatch": True})
    s, _ = _call(app, "GET", f"/v1/jobs/{jid}/layout-dxf")
    assert s.startswith("404")
