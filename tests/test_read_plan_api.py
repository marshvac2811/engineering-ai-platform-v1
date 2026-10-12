import base64, io, json
from api.app import APIApp
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore
from engineering.plan.samples import office_plan_dxf, office_plan_pdf


def _call(body):
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    raw = json.dumps(body).encode()
    env = {"REQUEST_METHOD": "POST", "PATH_INFO": "/v1/drawings/read-plan", "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw), "HTTP_X_TENANT_ID": "t"}
    out = {}
    data = b"".join(app(env, lambda s, h: out.update(status=s)))
    return out["status"], json.loads(data.decode())


def test_dxf_upload_reads_rooms_and_returns_layout():
    s, j = _call({"filename": "p.dxf", "content_base64": base64.b64encode(office_plan_dxf(units="mm")).decode(), "generate_layout": True, "services": ["hvac", "fire"]})
    assert s.startswith("200") and len(j["rooms"]) == 7 and j["governance"]["human_review_required"]
    assert j["layout"]["summary"]["sprinklers"] > 0 and base64.b64decode(j["layout"]["content_base64"])


def test_pdf_upload_and_unsupported_and_bad_base64():
    s, j = _call({"filename": "p.pdf", "content_base64": base64.b64encode(office_plan_pdf()).decode(), "generate_layout": True})
    assert s.startswith("200") and len(j["rooms"]) == 7 and "layout" in j
    s, j = _call({"filename": "p.dwg", "content_base64": base64.b64encode(b"AC1018xxxx").decode()})
    assert s.startswith("200") and j["status"] in ("unsupported", "failed") and "layout" not in j
    s, j = _call({"filename": "p.dxf", "content_base64": "@@@"})
    assert s.startswith("400")
