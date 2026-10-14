from types import SimpleNamespace as NS
import io, json
from api.app import APIApp
from crm.linker import CRMLinker, client_from_context, deal_name_from_context
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore


def _job(**ctx):
    return NS(job_id="j1", tenant_id="t1", source="gmail", requested_skill_id="retrofit_study", project_context=dict(ctx))


def test_client_and_name_derivation():
    assert client_from_context({"client": "Hotel ABC"}) == "Hotel ABC"
    assert client_from_context({"from": "Ravi Mehta <ravi@skyline-developers.in>"}) == "Ravi Mehta"
    assert client_from_context({"from": "<info@skyline-developers.in>"}) == "Skyline Developers"
    assert client_from_context({"from": "someone@gmail.com"}) == ""
    assert deal_name_from_context({"subject": "Re: FWD: HVAC BOQ for Tower B"}, "boq_takeoff") == "HVAC BOQ for Tower B"
    assert deal_name_from_context({}, "boq_takeoff") == "Boq Takeoff"


def test_job_creates_one_deal_and_follows_rework_and_dispatch():
    store = InMemoryCRMStore(); link = CRMLinker(store)
    j = _job(project="Tower B HVAC", client="Skyline")
    assert link.handle("created", j) is True
    deals = store.list("t1"); assert len(deals) == 1
    d = deals[0]
    assert d.stage == "budgetary" and d.category == "Retrofit Jobs" and d.engineering_job_id == "j1" and d.next_follow_up
    assert j.project_context["crm_deal_id"] == d.deal_id
    # a second job for the same client + project reuses the deal
    j2 = _job(project="Tower B HVAC", client="skyline"); j2.job_id = "j2"
    link.handle("created", j2); assert len(store.list("t1")) == 1
    # a job that is already linked is left alone
    assert link.handle("created", j) is False
    link.handle("rework", j, comment="Client changed the tariff")
    link.handle("dispatched", j)
    got = store.get("t1", d.deal_id).delivery
    assert got["revisions"][0]["note"] == "Client changed the tariff" and got["revisions"][0]["no"] == 1
    assert got["delivered_on"] and got["final_submitted_on"] and got["payment_status"] == "not_invoiced"


def test_crm_failure_never_breaks_job_creation():
    class Boom:
        def handle(self, *a, **k): raise RuntimeError("crm down")
    from jobs.service import JobService
    svc = JobService(InMemoryJobStore(), tenant_id="t1"); svc.observers.append(Boom())
    job = svc.create_job(source="api", requested_skill_id="duct_sizing", inputs={}, project_context={})
    assert job.job_id


def test_api_job_creation_appears_in_crm_without_manual_entry():
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    def call(method, path, body=None):
        payload = json.dumps(body or {}).encode(); res = {}
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'CONTENT_LENGTH': str(len(payload)), 'wsgi.input': io.BytesIO(payload), 'HTTP_X_TENANT_ID': 't1', 'HTTP_X_USER_ID': 'u1'}
        out = b''.join(app(env, lambda s, h: res.update(status=s)))
        return res['status'], json.loads(out.decode())
    st, job = call('POST', '/v1/jobs', {"requested_skill_id": "duct_sizing", "inputs": {}, "project": "Hotel ABC Retrofit", "client": "Hotel ABC Pvt Ltd"})
    assert st == '201 Created'
    st, data = call('GET', '/v1/crm')
    assert len(data['deals']) == 1 and data['deals'][0]['company'] == 'Hotel ABC Pvt Ltd' and data['deals'][0]['engineering_job_id'] == job['job_id']
