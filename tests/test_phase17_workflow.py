import io, json, os
from api.app import APIApp
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore
from workflow.store import InMemoryWorkflowTaskStore
from workflow.service import WorkflowTaskService

TENANT = "00000000-0000-0000-0000-000000000001"


def call(app, method, path, payload=None, query=""):
    body = json.dumps(payload or {}).encode()
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
           "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body),
           "HTTP_X_TENANT_ID": TENANT, "HTTP_X_USER_ID": "user-1", "HTTP_X_ROLE": "admin",
           "HTTP_X_SCOPES": "integrations:read integrations:write jobs:read jobs:write workflow:read workflow:write"}
    captured = {}
    def start(status, headers): captured["status"] = status
    result = json.loads(b"".join(app(env, start)))
    return captured["status"], result


def test_task_state_machine_and_linkage():
    store = InMemoryWorkflowTaskStore()
    service = WorkflowTaskService(store, tenant_id=TENANT)
    task = service.create(source="upwork", external_id="u-1", title="HVAC load", requirement="Calculate cooling load")
    assert task.status == "NEW"
    service.transition(task.task_id, "TRIAGE")
    service.transition(task.task_id, "READY_FOR_ENGINEERING")
    service.link_job(task.task_id, "job-123")
    assert service.get(task.task_id).status == "ENGINEERING"
    assert service.get(task.task_id).engineering_job_id == "job-123"


def test_task_external_event_is_idempotent():
    store = InMemoryWorkflowTaskStore()
    service = WorkflowTaskService(store, tenant_id=TENANT)
    a, created_a = service.create_from_event(source="upwork", external_id="msg-1", payload={"subject":"Pump head", "body_text":"Please calculate head"})
    b, created_b = service.create_from_event(source="upwork", external_id="msg-1", payload={"subject":"duplicate", "body_text":"ignore"})
    assert created_a is True
    assert created_b is False
    assert a.task_id == b.task_id


def test_upwork_event_creates_task_and_engineering_job():
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore(), workflow_task_store=InMemoryWorkflowTaskStore())
    status, body = call(app, "POST", "/v1/integrations/upwork/events", {
        "external_event_id": "up-100",
        "event_type": "message.received",
        "payload": {"subject": "Cooling load calculation", "body_text": "Need preliminary HVAC load calculation for office."},
    })
    assert status == "201 Created"
    assert body["task_created"] is True
    assert body["job_created"] is True
    assert body["task"]["source"] == "upwork"
    assert body["task"]["engineering_job_id"] == body["job"]["job_id"]
