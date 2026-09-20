from crm import CRMService, InMemoryCRMStore, HubSpotAdapter, PIPELINE_STAGES


def test_pipeline_stages_match_source():
    assert [x[0] for x in PIPELINE_STAGES] == [
        'budgetary','tendering','quotation','followup','negotiation','won','lost'
    ]


def test_create_and_update_crm_deal():
    service = CRMService(InMemoryCRMStore(), tenant_id='t1')
    deal = service.create_deal(name='Hospital HVAC', category='Project Sales', stakeholder='Consultant', value=2500000, stage='budgetary')
    updated = service.update(deal.deal_id, stage='quotation', engineering_job_id='job-1')
    assert updated.stage == 'quotation'
    assert updated.engineering_job_id == 'job-1'


def test_tenant_isolation():
    store = InMemoryCRMStore()
    CRMService(store, tenant_id='t1').create_deal(name='A')
    service2 = CRMService(store, tenant_id='t2')
    assert service2.list() == []


def test_hubspot_payload():
    service = CRMService(InMemoryCRMStore(), tenant_id='t1', hubspot=HubSpotAdapter())
    deal = service.create_deal(name='Energy Retrofit', category='Energy Optimization', stakeholder='End Client', value=125000, stage='negotiation')
    result = service.sync_hubspot(deal.deal_id)
    assert result['provider'] == 'hubspot'
    assert result['mode'] == 'prepared'
    assert result['payload']['properties']['dealname'] == 'Energy Retrofit'


def test_engineering_job_link():
    service = CRMService(InMemoryCRMStore(), tenant_id='t1')
    deal = service.create_deal(name='VRF Project')
    service.link_engineering_job(deal.deal_id, 'job-42')
    assert service.get(deal.deal_id).engineering_job_id == 'job-42'
