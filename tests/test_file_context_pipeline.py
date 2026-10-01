from ingestion.service import IngestionService
from jobs.models import JobStatus
from jobs.service import JobService
from jobs.store import InMemoryJobStore
from orchestrator.intake import IntentCandidate, OrchestrationPlan


def test_uploaded_project_document_becomes_ai_project_context():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant", ingestion_service=IngestionService())
    plan = OrchestrationPlan(
        status="awaiting_information",
        normalized_request="Calculate pump head for this project",
        selected_skill_id="pump_head",
        confidence=0.9,
        candidates=[IntentCandidate("pump_head", 900, ["test"])],
        extracted_inputs={},
        missing_inputs=["flow_m3hr"],
        questions=["Please provide the design water flow rate in m3/hr."],
    )
    job = service.create_from_plan(
        plan,
        attachments=[{
            "filename": "project_spec.txt",
            "mime_type": "text/plain",
            "content_base64": "UHJvamVjdCBzcGVjOiBwaXBlIGxlbmd0aCAxMjAgbS4=",
        }],
    )

    assert job.status == JobStatus.AWAITING_INFORMATION
    assert job.project_context["documents"][0]["filename"] == "project_spec.txt"
    assert "pipe length 120 m" in job.project_context["documents"][0]["text"]
    assert job.attachments[0]["extraction_status"] == "extracted"
