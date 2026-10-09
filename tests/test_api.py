from integrations.service import InMemoryIntegrationStore
from crm.store import InMemoryCRMStore
from jobs.store import InMemoryJobStore
import io, json
from api.app import APIApp
from ingestion.service import IngestionService


def call(app, method, path, body=None, tenant='tenant-a'):
    raw=json.dumps(body or {}).encode()
    env={
        'REQUEST_METHOD':method,
        'PATH_INFO':path,
        'CONTENT_LENGTH':str(len(raw)),
        'wsgi.input':io.BytesIO(raw),
        'HTTP_X_TENANT_ID':tenant,
    }
    result={}
    def start(status, headers): result['status']=status
    out=b''.join(app(env,start))
    return result['status'], json.loads(out.decode())


def test_health_and_job_lifecycle_api():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    status, body=call(app,'GET','/health')
    assert status.startswith('200') and body['status']=='ok'
    payload={'source':'api-test','requested_skill_id':'duct_sizing','inputs':{'airflow':3600,'method':'velocity','duct_type':'round','target_velocity_ms':8,'material':'gss'}}
    status, job=call(app,'POST','/v1/jobs',payload)
    assert status.startswith('201'); jid=job['job_id']
    status, job=call(app,'POST',f'/v1/jobs/{jid}/enqueue')
    assert job['status']=='queued'
    status, job=call(app,'POST',f'/v1/jobs/{jid}/process')
    assert job['status']=='human_review'
    assert job['report_id']
    status, job=call(app,'POST',f'/v1/jobs/{jid}/approve',{'reviewer':'eng-1','comment':'approved'})
    assert job['status']=='approved'
    status, job=call(app,'POST',f'/v1/jobs/{jid}/dispatch')
    assert job['status']=='completed'


def test_api_tenant_boundary():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    _, job=call(app,'POST','/v1/jobs',{'source':'api','requested_skill_id':'duct_sizing','inputs':{}},tenant='tenant-a')
    jid=job['job_id']
    status, _=call(app,'GET',f'/v1/jobs/{jid}',tenant='tenant-b')
    assert status.startswith('403')


def test_api_requires_tenant():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    raw=b'{}'
    env={'REQUEST_METHOD':'GET','PATH_INFO':'/v1/jobs/x','CONTENT_LENGTH':'0','wsgi.input':io.BytesIO(raw)}
    result={}
    out=b''.join(app(env,lambda s,h: result.setdefault('status',s)))
    body=json.loads(out.decode())
    assert result['status'].startswith('401') and 'Tenant-ID' in body['error']


def test_api_intake_degrades_gracefully_when_openai_provider_has_no_key(monkeypatch):
    monkeypatch.setenv("ENGINEERING_AI_INTENT_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    status, body=call(app,'POST','/v1/intake',{'message':'Please look into my building situation'})
    # Intake must stay usable when the optional AI provider is unavailable (commits e3d3786, 98f78f9):
    # it falls back to the audited deterministic router instead of returning 503, and never invents a skill.
    assert status.startswith('201'), body
    assert body['plan']['status'] == 'awaiting_information'
    assert not body['plan'].get('selected_skill_id')

def test_api_exposes_engineering_report_and_compliance():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    payload={'source':'api-test','requested_skill_id':'facade_u_factor','inputs':{
        'components':[{'name':'glass','area_m2':10,'u_factor':2.0}],
        'project_context':{'building_type':'office','location':'Delhi'}
    }}
    status, job=call(app,'POST','/v1/jobs',payload)
    assert status.startswith('201'); jid=job['job_id']
    status, _=call(app,'POST',f'/v1/jobs/{jid}/enqueue')
    status, job=call(app,'POST',f'/v1/jobs/{jid}/process')
    assert job['status']=='human_review'
    status, report=call(app,'GET',f'/v1/jobs/{jid}/report')
    assert status.startswith('200')
    assert report['report']['report_type']=='facade_u_factor_engineering'
    status, compliance=call(app,'GET',f'/v1/jobs/{jid}/compliance')
    assert status.startswith('200')
    assert compliance['count'] == 1
    assert compliance['checks'][0]['clause_reference']


def test_drawing_plan_api_requires_explicit_engineering_inputs():
    import json, io
    from api.app import APIApp
    from jobs.store import InMemoryJobStore
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore(), ingestion=IngestionService())
    body={"building":{"building_id":"B1","name":"Demo","floors":[{"floor_id":"L1","name":"Ground","rooms":[{"room_id":"R1","name":"Office","area_m2":20,"x_mm":100,"y_mm":100}]}]},"discipline":"HVAC","floor_id":"L1","room_inputs":{"R1":{"airflow_m3h":500}}}
    raw=json.dumps(body).encode(); env={"REQUEST_METHOD":"POST","PATH_INFO":"/v1/drawings/plan","CONTENT_LENGTH":str(len(raw)),"wsgi.input":io.BytesIO(raw),"HTTP_X_TENANT_ID":"tenant-a"}
    result={}; out=b"".join(app(env,lambda s,h: result.setdefault("status",s))); payload=json.loads(out.decode())
    assert result["status"].startswith("200") and payload["drawing"]["objects"][0]["kind"]=="air_terminal" and "preliminary" in payload["drawing"]["metadata"]["design_boundary"]

def test_drawing_coordinate_api_reports_cross_discipline_conflict():
    import json, io
    from api.app import APIApp
    from jobs.store import InMemoryJobStore
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore(), ingestion=IngestionService())
    body={"clearance_mm":100,"objects":[{"object_id":"A","discipline":"HVAC","kind":"duct","x_mm":10,"y_mm":10,"floor_id":"L1"},{"object_id":"B","discipline":"PLUMBING","kind":"pipe","x_mm":20,"y_mm":20,"floor_id":"L1"}]}
    raw=json.dumps(body).encode(); env={"REQUEST_METHOD":"POST","PATH_INFO":"/v1/drawings/coordinate","CONTENT_LENGTH":str(len(raw)),"wsgi.input":io.BytesIO(raw),"HTTP_X_TENANT_ID":"tenant-a"}
    result={}; out=b"".join(app(env,lambda s,h: result.setdefault("status",s))); payload=json.loads(out.decode())
    assert result["status"].startswith("200") and payload["count"]==1 and payload["human_review_required"]


def test_drawing_package_api_links_job_and_enforces_approval():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore(), ingestion=IngestionService())
    status, job=call(app,'POST','/v1/jobs',{
        'source':'drawing-api-test',
        'requested_skill_id':'duct_sizing',
        'inputs':{'airflow':3600,'method':'velocity','duct_type':'round','target_velocity_ms':8,'material':'gss'}
    })
    assert status.startswith('201')
    jid=job['job_id']
    body={
        'job_id':jid,
        'building':{'building_id':'B1','name':'Demo','sources':[{'source_id':'plan.pdf','page':1}],
                    'floors':[{'floor_id':'L1','name':'Ground','rooms':[{'room_id':'R1','name':'Office','area_m2':20,'x_mm':100,'y_mm':100}]}]},
        'drawings':[{'discipline':'HVAC','floor_id':'L1','room_inputs':{'R1':{'airflow_m3h':500,'source_calculation':'task-1'}},'revision':'A'}],
        'source_hashes':{'plan.pdf':'abc'}
    }
    status, package=call(app,'POST','/v1/drawings/package',body)
    assert status.startswith('201')
    assert package['package']['issue_status']=='not_approved'
    assert package['package']['dispatch_allowed'] is False
    status, job=call(app,'POST',f'/v1/jobs/{jid}/enqueue')
    status, job=call(app,'POST',f'/v1/jobs/{jid}/process')
    assert job['status']=='human_review'
    status, job=call(app,'POST',f'/v1/jobs/{jid}/approve',{'reviewer':'eng-1','comment':'approved'})
    assert job['status']=='approved'
    status, package=call(app,'POST',f'/v1/drawings/package',body)
    assert status.startswith('201')
    assert package['package']['issue_status']=='approved_for_controlled_dispatch'
    assert package['package']['dispatch_allowed'] is True
