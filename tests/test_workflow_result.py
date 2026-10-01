from orchestrator.result import build_workflow_result

def test_workflow_result_exposes_qa_and_trace():
    workflow = {
        "status": "completed",
        "engineering_plan": {"tasks": [
            {"task_id": "task-1", "status": "completed", "capability_id": "pump_head", "depends_on": []}
        ]},
        "engineering_results": [{
            "task_id": "task-1", "capability_id": "pump_head", "status": "completed",
            "engineering_result": {"assumptions": ["Test assumption"], "warnings": ["Test warning"]}
        }],
        "task_outputs": {},
        "execution_trace": [{"task_id": "task-1", "capability_id": "pump_head", "status": "completed"}],
        "calculation_authority": "registered_engineering_capability",
        "blockers": [],
    }
    result = build_workflow_result(
        workflow=workflow,
        request_understanding={"objective": "Test"},
        governance={"standards": ["test"]},
        inputs={"flow_m3hr": 10},
        assumptions={},
    )
    assert result["qa"]["status"] == "ready_for_human_review"
    assert result["qa"]["all_tasks_completed"] is True
    assert result["human_review"]["required"] is True
    assert result["execution_trace"][0]["task_id"] == "task-1"
    assert "Test assumption" in result["assumptions"]
    assert "Test warning" in result["risks_warnings"]

def test_workflow_result_blocks_incomplete_plan():
    workflow = {
        "status": "awaiting_information",
        "engineering_plan": {"tasks": [
            {"task_id": "task-1", "status": "awaiting_information", "capability_id": "pump_head", "depends_on": []}
        ]},
        "engineering_results": [], "execution_trace": [], "blockers": ["missing flow"],
        "calculation_authority": "registered_engineering_capability",
    }
    result = build_workflow_result(
        workflow=workflow, request_understanding={}, governance={}, inputs={}, assumptions={}
    )
    assert result["qa"]["status"] == "not_ready"
    assert result["human_review"]["status"] == "blocked"

def test_workflow_result_requires_trace_and_result_integrity():
    workflow = {
        "status": "completed",
        "engineering_plan": {"tasks": [{"task_id": "task-1", "status": "completed", "capability_id": "pump_head", "depends_on": []}]},
        "engineering_results": [],
        "execution_trace": [],
        "blockers": [],
        "calculation_authority": "registered_engineering_capability",
    }
    result = build_workflow_result(workflow=workflow, request_understanding={}, governance={}, inputs={}, assumptions={})
    assert result["qa"]["status"] == "not_ready"
    assert result["qa"]["trace_integrity"] is False
    assert result["qa"]["result_integrity"] is False