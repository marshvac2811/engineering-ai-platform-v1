from integrations.service import InMemoryIntegrationStore
from crm.store import InMemoryCRMStore
from jobs.store import InMemoryJobStore
import io, json
from api.app import APIApp


def call(app, method, path, body=None, tenant='t1', user='u1'):
    payload = json.dumps(body or {}).encode()
    result = {}
    def start_response(status, headers): result['status']=status
    env={'REQUEST_METHOD':method,'PATH_INFO':path,'CONTENT_LENGTH':str(len(payload)),'wsgi.input':io.BytesIO(payload), 'HTTP_X_TENANT_ID':tenant,'HTTP_X_USER_ID':user}
    out=b''.join(app(env,start_response))
    return result['status'], json.loads(out.decode())


def test_crm_api_create_list_and_sync():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    status,data=call(app,'POST','/v1/crm/deals', {'name':'Office Retrofit','category':'Retrofit Jobs','stakeholder':'End Client','value':500000,'stage':'quotation'})
    assert status=='201 Created'
    deal_id=data['deal_id']
    status,data=call(app,'GET','/v1/crm')
    assert status=='200 OK' and len(data['deals'])==1
    status,data=call(app,'POST',f'/v1/crm/deals/{deal_id}/sync-hubspot')
    assert status=='200 OK' and data['provider']=='hubspot'


def test_crm_api_tenant_isolation():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    status,data=call(app,'POST','/v1/crm/deals', {'name':'Tenant A'})
    deal_id=data['deal_id']
    status,data=call(app,'GET',f'/v1/crm/deals/{deal_id}',tenant='t2',user='u2')
    assert status=='404 Not Found'


def test_crm_delivery_revisions_and_payments_tracking():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    status,data=call(app,'POST','/v1/crm/deals', {'name':'Hotel retrofit','stage':'won','value':300000})
    deal_id=data['deal_id']
    assert data['delivery']['payment_status']=='not_invoiced'
    status,data=call(app,'PATCH',f'/v1/crm/deals/{deal_id}', {'delivery':{
        'delivered_on':'2026-12-01','final_submitted_on':'2026-12-20','invoice_no':'MES/001','invoice_amount':300000,
        'revisions':[{'date':'2026-12-05','note':'Client changed tariff'},{'date':'2026-12-10','note':'Added solar option'}],
        'payments':[{'date':'2026-12-22','amount':100000,'ref':'UTR1'}]}})
    assert status=='200 OK'
    d=data['delivery']
    assert [r['no'] for r in d['revisions']]==[1,2]
    assert d['paid_total']==100000 and d['outstanding']==200000 and d['payment_status']=='part_paid'
    status,data=call(app,'PATCH',f'/v1/crm/deals/{deal_id}', {'delivery':{'invoice_amount':300000,'payments':[{'date':'2026-12-30','amount':300000}]}})
    assert data['delivery']['payment_status']=='paid' and data['delivery']['outstanding']==0


def test_crm_delivery_rejects_bad_values_and_keeps_old_record():
    app=APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    status,data=call(app,'POST','/v1/crm/deals', {'name':'X','delivery':{'invoice_amount':1000}})
    deal_id=data['deal_id']
    status,data=call(app,'PATCH',f'/v1/crm/deals/{deal_id}', {'delivery':{'invoice_amount':-5}})
    assert status.startswith('4')
    status,data=call(app,'PATCH',f'/v1/crm/deals/{deal_id}', {'delivery':{'delivered_on':'not-a-date'}})
    assert status.startswith('4')
    status,data=call(app,'GET',f'/v1/crm/deals/{deal_id}')
    assert data['delivery']['invoice_amount']==1000
