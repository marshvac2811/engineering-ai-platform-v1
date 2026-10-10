from orchestrator.intake import build_plan
from orchestrator.engine import registered_skills
from api.app import APIApp
import io, json


def call(app, method, path, body=None, tenant='00000000-0000-0000-0000-000000000001'):
    raw=json.dumps(body or {}).encode()
    env={'REQUEST_METHOD':method,'PATH_INFO':path,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw),'HTTP_X_TENANT_ID':tenant}
    result={}
    out=b''.join(app(env, lambda s,h: result.setdefault('status',s)))
    return result['status'], json.loads(out.decode())


def test_natural_language_routes_duct_request_and_extracts_inputs():
    plan=build_plan('Size a round duct for 8000 CFM using velocity at 7 m/s')
    assert plan.selected_skill_id=='duct_sizing'
    assert plan.extracted_inputs['airflow']==8000
    assert plan.extracted_inputs['target_velocity_ms']==7
    assert plan.extracted_inputs['duct_type']=='round'
    assert plan.extracted_inputs['method']=='velocity'
    assert plan.status=='ready_for_execution'
    assert plan.missing_inputs==[]



def test_natural_language_pump_request_extracts_material_and_percent_margin():
    plan=build_plan('Calculate pump head. Flow 20 m3/hr, diameter 80 mm, straight length 60 m, static head 8 m, margin 10 percent. Use GI pipe.')
    assert plan.selected_skill_id=='pump_head'
    assert plan.extracted_inputs['flow_m3hr']==20
    assert plan.extracted_inputs['diameter_mm']==80
    assert plan.extracted_inputs['straight_length_m']==60
    assert plan.extracted_inputs['static_head_m']==8
    assert plan.extracted_inputs['margin_pct']==10
    assert plan.extracted_inputs['material']=='gi'
    assert plan.status=='ready_for_execution'
    assert plan.missing_inputs==[]

def test_natural_language_routes_pump_request():
    plan=build_plan('Calculate pump head for 20 m3/hr, 80 mm pipe, 60 m straight length, 8 m static head and 10% margin', provided_inputs={'roughness_mm':0.0015})
    assert plan.selected_skill_id=='pump_head'
    assert plan.extracted_inputs['flow_m3hr']==20
    assert plan.extracted_inputs['diameter_mm']==80
    assert plan.extracted_inputs['static_head_m']==8
    assert plan.status=='ready_for_execution'
    assert plan.missing_inputs==[]


def test_explicit_skill_overrides_ambiguous_language():
    plan=build_plan('Need an estimate', requested_skill_id='preliminary_load_estimation', provided_inputs={'building_type':'office','area_sqft':10000,'climate_zone':'composite'}, project_context={'site':'Delhi'})
    assert plan.selected_skill_id=='preliminary_load_estimation'
    assert plan.status=='ready_for_execution'
    assert plan.confidence==1.0
    assert plan.project_context['site']=='Delhi'


def test_api_intake_creates_awaiting_information_job():
    app=APIApp()
    status, body=call(app,'POST','/v1/intake',{'message':'Size a round duct for 8000 CFM using velocity at 7 m/s'})
    assert status.startswith('201')
    assert body['plan']['selected_skill_id']=='duct_sizing'
    assert body['plan']['status']=='ready_for_execution'
    assert body['job']['status']=='human_review'


def test_api_intake_full_request_can_be_queued_and_processed():
    app=APIApp()
    payload={
        'message':'Size a round duct for 8000 CFM using velocity at 7 m/s',
        'inputs':{'material':'gss'},
    }
    status, body=call(app,'POST','/v1/intake',payload)
    assert status.startswith('201')
    jid=body['job']['job_id']
    assert body['job']['status']=='human_review'


def test_registered_skill_count_matches_expected_executable_batch():
    assert len(registered_skills())==42


def test_natural_language_missing_engineering_input_is_asked():
    plan=build_plan('Size a duct')
    assert plan.selected_skill_id=='duct_sizing'
    assert plan.status=='awaiting_information'
    assert 'airflow' in plan.missing_inputs
    assert plan.questions



def test_minor_pump_inputs_are_auto_assumed_and_disclosed():
    plan = build_plan("Calculate pump head. Flow 20 m3/hr, diameter 80 mm, straight length 60 m, static head 8 m, margin 10 percent.")
    assert plan.selected_skill_id == "pump_head"
    assert plan.status == "ready_for_execution"
    assert plan.missing_inputs == []
    assert plan.extracted_inputs["material"] == "ms_cs"
    assert plan.extracted_inputs["margin_pct"] == 10
    assert any("governed preliminary assumptions" in r for r in plan.rationale)
