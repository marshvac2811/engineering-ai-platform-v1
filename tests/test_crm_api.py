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
    app=APIApp()
    status,data=call(app,'POST','/v1/crm/deals', {'name':'Office Retrofit','category':'Retrofit Jobs','stakeholder':'End Client','value':500000,'stage':'quotation'})
    assert status=='201 Created'
    deal_id=data['deal_id']
    status,data=call(app,'GET','/v1/crm')
    assert status=='200 OK' and len(data['deals'])==1
    status,data=call(app,'POST',f'/v1/crm/deals/{deal_id}/sync-hubspot')
    assert status=='200 OK' and data['provider']=='hubspot'


def test_crm_api_tenant_isolation():
    app=APIApp()
    status,data=call(app,'POST','/v1/crm/deals', {'name':'Tenant A'})
    deal_id=data['deal_id']
    status,data=call(app,'GET',f'/v1/crm/deals/{deal_id}',tenant='t2',user='u2')
    assert status=='404 Not Found'
