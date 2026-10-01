from integrations.service import InMemoryIntegrationStore
from crm.store import InMemoryCRMStore
from jobs.store import InMemoryJobStore
import io, json
from api.app import APIApp


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


def test_api_returns_503_when_openai_provider_is_selected_without_key(monkeypatch):
    monkeypatch.setenv("ENGINEERING_AI_INTENT_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    status, body=call(app,'POST','/v1/intake',{'message':'Size a round duct'})
    assert status.startswith('503')
    assert 'OPENAI_API_KEY' in body['error']

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
    assert report['report']['report_type']=='engineering_compliance_report'
    status, compliance=call(app,'GET',f'/v1/jobs/{jid}/compliance')
    assert status.startswith('200')
    assert compliance['count'] == 1
    assert compliance['checks'][0]['clause_reference']
